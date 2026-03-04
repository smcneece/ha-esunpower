"""Direct varserver HTTP client for new-firmware PVS communication.

Replaces pypvs library dependency.  Authenticates to the PVS varserver API
and polls all device types, returning data in the existing legacy
{"devices": [...]} format that data_processor.py already understands.

Why this exists:
- pypvs probe() runs once at startup; if inverters are offline (nighttime restart)
  it sets a permanent flag and never re-probes.  Our implementation always
  queries every poll and handles empty responses gracefully.
- Eliminates an abandoned external dependency.
"""

import base64
import logging
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

# Varserver match patterns (same as pypvs const.py)
_MATCH_INVERTERS = "/sys/devices/inverter/"
_MATCH_METERS = "/sys/devices/meter/"
_MATCH_ESS = "/sys/devices/ess/"
_MATCH_TRANSFER_SWITCH = "/sys/devices/transfer_switch/"

# Individual gateway vars to fetch (matching pypvs gateway updater)
_GATEWAY_VARS = [
    "/sys/info/model",
    "/sys/info/hwrev",
    "/sys/info/sw_rev",
    "/sys/info/uptime",
    "/sys/info/ram_usage",
    "/sys/info/flash_usage",
    "/sys/info/cpu_usage",
]


def _iso_to_datatime(iso_str: str) -> str:
    """Convert ISO8601 timestamp to legacy DATATIME format 'YYYY,MM,DD,HH,MM,SS'."""
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return dt.strftime("%Y,%m,%d,%H,%M,%S")
    except Exception:
        return datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S")


class VarserverClient:
    """Direct HTTP client for PVS varserver API.

    Uses the same POST-based FCGI interface as pypvs but without the probe()
    pattern that causes inverters to disappear after a nighttime restart.
    """

    def __init__(self, session, host: str, password: str):
        self._session = session
        self._host = host
        self._password = password
        self._cookies = None

    async def authenticate(self) -> bool:
        """Authenticate to PVS and store session cookie.

        Returns True on success, False on failure.
        """
        auth_token = base64.b64encode(
            f"ssm_owner:{self._password}".encode("utf-8")
        ).decode()
        headers = {"Authorization": f"basic {auth_token}"}
        url = f"https://{self._host}/auth?login"

        try:
            async with self._session.get(
                url, headers=headers, ssl=False
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Varserver auth failed: HTTP %d", response.status
                    )
                    return False
                self._cookies = response.cookies
                _LOGGER.debug(
                    "Varserver authenticated to PVS at %s", self._host
                )
                return True
        except Exception as e:
            _LOGGER.error("Varserver auth request failed: %s", e)
            return False

    def _parse_response(self, data: dict) -> dict:
        """Convert varserver array-format response to {path: value} dict."""
        if not data or "values" not in data:
            return {}
        try:
            return {item["name"]: item["value"] for item in data["values"]}
        except (KeyError, TypeError):
            return {}

    async def _post_vars(self, params: dict) -> dict:
        """POST to /vars with params dict, return {path: value} dict.

        Matches pypvs pvs_fcgi.py POST behavior exactly.
        Handles reactive re-auth on 400/401/403/500 responses.
        """
        if self._cookies is None:
            if not await self.authenticate():
                _LOGGER.error("Cannot query vars - authentication failed")
                return {}

        url = f"https://{self._host}/vars"
        # Match pypvs payload format exactly (no & separator; always single param)
        payload_str = "".join(f"{k}={v}" for k, v in params.items())

        self._session.cookie_jar.clear()
        try:
            async with self._session.post(
                url, cookies=self._cookies, data=payload_str, ssl=False
            ) as response:
                if response.status == 400:
                    # Varserver returns 400 when no devices exist for the
                    # queried path (e.g., no physical meters, no ESS).
                    # Not an auth error — proactive re-auth every 600s
                    # keeps the session fresh.
                    _LOGGER.debug(
                        "Varserver returned 400 (no devices for this path)"
                    )
                    return {}
                if response.status in (401, 403, 500):
                    _LOGGER.warning(
                        "Varserver returned %d, re-authenticating",
                        response.status,
                    )
                    if await self.authenticate():
                        self._session.cookie_jar.clear()
                        async with self._session.post(
                            url,
                            cookies=self._cookies,
                            data=payload_str,
                            ssl=False,
                        ) as retry:
                            if retry.status != 200:
                                _LOGGER.error(
                                    "Varserver retry failed: %d", retry.status
                                )
                                return {}
                            return self._parse_response(
                                await retry.json(content_type=None)
                            )
                    return {}

                if response.status != 200:
                    _LOGGER.error(
                        "Varserver POST failed: HTTP %d", response.status
                    )
                    return {}

                return self._parse_response(
                    await response.json(content_type=None)
                )
        except Exception as e:
            _LOGGER.error("Varserver POST error: %s", e)
            return {}

    async def _request_var(self, name: str) -> str | None:
        """Fetch single variable value. Returns string value or None."""
        result = await self._post_vars({"name": name})
        return result.get(name)

    async def _request_vars(self, match: str) -> dict:
        """Fetch vars matching pattern. Returns {path: value} flat dict."""
        return await self._post_vars({"match": match})

    async def get_var(self, path: str) -> str | None:
        """Get a single variable value (public interface for callers)."""
        return await self._request_var(path)

    async def set_var(self, path: str, value: str) -> bool:
        """Set a variable value. Returns True if accepted."""
        result = await self._post_vars({"set": f"{path}={value}"})
        return bool(result)

    async def _group_devices(self, match: str) -> list[dict]:
        """Query match pattern and group flat vars by device index.

        Path format: /sys/devices/{type}/{idx}/{param}
        - parts[3] = device type (inverter, meter, ess, transfer_switch)
        - parts[4] = index
        - parts[5] = param name

        Returns list of param dicts sorted by index.
        Empty list if no devices found (not an error).
        """
        flat = await self._request_vars(match)
        if not flat:
            return []

        grouped: dict[int, dict] = {}
        for path, value in flat.items():
            parts = path.split("/")
            if len(parts) >= 6:
                try:
                    idx = int(parts[4])
                    param = parts[5]
                    if idx not in grouped:
                        grouped[idx] = {}
                    grouped[idx][param] = value
                except (ValueError, IndexError):
                    continue

        return [grouped[idx] for idx in sorted(grouped.keys())]

    async def get_all_data(self, pvs_serial: str) -> dict:
        """Poll all devices and return legacy {"devices": [...]} format.

        Empty inverter list at night is handled gracefully (not an error).
        Returns {"devices": []} on complete failure.
        """
        # Re-auth before every poll - PVS sessions expire in ~5 minutes,
        # which is shorter than a typical polling interval.
        await self.authenticate()

        devices = []

        # Gateway (PVS device) - always present
        gateway_device = await self._build_gateway(pvs_serial)
        if gateway_device:
            devices.append(gateway_device)

        # Inverters - empty list at night is normal, not an error
        inverter_devices = await self._build_inverters()
        inverter_count = len(inverter_devices)
        if inverter_count == 0:
            _LOGGER.debug(
                "No inverters in varserver data (may be nighttime - not an error)"
            )
        else:
            _LOGGER.info("Varserver: %d inverters", inverter_count)
        devices.extend(inverter_devices)

        # Meters
        meter_devices = await self._build_meters()
        devices.extend(meter_devices)

        # ESS/Battery - empty if no battery system
        ess_devices = await self._build_ess()
        devices.extend(ess_devices)

        # Transfer switches - empty if not present
        ts_devices = await self._build_transfer_switches()
        devices.extend(ts_devices)

        _LOGGER.debug(
            "Varserver poll complete: %d devices total", len(devices)
        )
        return {"devices": devices}

    async def _build_gateway(self, pvs_serial: str) -> dict | None:
        """Build PVS gateway device dict from /sys/info vars."""
        # Fetch flash wear percentage
        fw_pct = 0
        try:
            flashwear_raw = await self._request_var("/sys/pvs/flashwear_type_b")
            if flashwear_raw:
                if isinstance(flashwear_raw, str) and flashwear_raw.startswith("0x"):
                    fw_pct = int(flashwear_raw, 16) * 10
                else:
                    fw_pct = int(flashwear_raw) * 10
        except Exception as e:
            _LOGGER.debug("Could not fetch flashwear_type_b: %s", e)

        # Fetch gateway vars individually (matches pypvs gateway updater approach)
        info: dict = {}
        for var_name in _GATEWAY_VARS:
            val = await self._request_var(var_name)
            if val is not None:
                info[var_name] = val

        if not info:
            _LOGGER.error("No gateway info retrieved from varserver")
            return None

        model_raw = (info.get("/sys/info/model") or "PVS6").strip()
        hw_rev = (info.get("/sys/info/hwrev") or "").strip()
        model = f"PV Supervisor {model_raw}"
        hw_ver = f"{model_raw} {hw_rev}" if hw_rev else model_raw

        try:
            uptime_val = str(int(float(info.get("/sys/info/uptime", "0"))))
        except (ValueError, TypeError):
            uptime_val = "0"

        try:
            cpu_val = str(float(info.get("/sys/info/cpu_usage", "0")) / 100.0)
        except (ValueError, TypeError):
            cpu_val = "0"

        try:
            ram_val = str(int(float(info.get("/sys/info/ram_usage", "0"))))
        except (ValueError, TypeError):
            ram_val = "0"

        try:
            flash_val = str(int(float(info.get("/sys/info/flash_usage", "0"))))
        except (ValueError, TypeError):
            flash_val = "0"

        return {
            "DEVICE_TYPE": "PVS",
            "SERIAL": pvs_serial,
            "MODEL": model,
            "SWVER": info.get("/sys/info/sw_rev", "Unknown"),
            "HWVER": hw_ver,
            "STATE": "working",
            "STATEDESCR": "Working",
            "dl_uptime": uptime_val,
            "dl_cpu_load": cpu_val,
            "dl_mem_used": "0",
            "dl_flash_avail": "0",
            "ram_usage_percent": ram_val,
            "flash_usage_percent": flash_val,
            "flashwear_percent": str(int(fw_pct)),
            "dl_err_count": "0",
            "dl_comm_err": "0",
            "dl_skipped_scans": "0",
            "dl_scan_time": "0",
            "dl_untransmitted": "0",
            "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
        }

    async def _build_inverters(self) -> list[dict]:
        """Build inverter device dicts from varserver."""
        inverters_raw = await self._group_devices(_MATCH_INVERTERS)
        if not inverters_raw:
            return []

        devices = []
        for data in inverters_raw:
            try:
                sn = data.get("sn", "")
                if not sn:
                    continue

                model = data.get("prodMdlNm", "AC_Module_Type_E")
                datatime = _iso_to_datatime(
                    data.get("msmtEps", "1970-01-01T00:00:00Z")
                )

                p_kw = float(data.get("p3phsumKw", 0))
                v_v = float(data.get("vln3phavgV", 0))
                i_a = float(data.get("i3phsumA", 0))
                freq = float(data.get("freqHz", 0))
                temp = float(data.get("tHtsnkDegc", 0))
                lte = round(float(data.get("ltea3phsumKwh", 0)), 2)
                # MPPT fallback to AC values if DC not available
                p_mppt = float(data.get("pMppt1Kw", p_kw))
                v_mppt = float(data.get("vMppt1V", v_v))
                i_mppt = float(data.get("iMppt1A", i_a))

                devices.append({
                    "DEVICE_TYPE": "Inverter",
                    "SERIAL": sn,
                    "MODEL": model,
                    "DESCR": f"Inverter {sn}",
                    "HWVER": model,
                    "SWVER": "varserver",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "DATATIME": datatime,
                    "ltea_3phsum_kwh": str(lte),
                    "p_3phsum_kw": str(p_kw),
                    "vln_3phavg_v": str(v_v),
                    "i_3phsum_a": str(i_a),
                    "freq_hz": str(freq),
                    "t_htsnk_degc": str(temp),
                    "p_mppt1_kw": str(p_mppt),
                    "v_mppt1_v": str(v_mppt),
                    "i_mppt1_a": str(i_mppt),
                })
            except Exception as e:
                _LOGGER.debug("Error building inverter device: %s", e)

        return devices

    async def _build_meters(self) -> list[dict]:
        """Build power meter device dicts from varserver."""
        meters_raw = await self._group_devices(_MATCH_METERS)
        if not meters_raw:
            return []

        devices = []
        for data in meters_raw:
            try:
                sn = data.get("sn", "")
                if not sn:
                    continue

                model = data.get("prodMdlNm", "PVS6M0400p")
                is_production = model.lower().endswith("p")
                meter_type = "PVS5-METER-P" if is_production else "PVS5-METER-C"
                datatime = _iso_to_datatime(
                    data.get("msmtEps", "1970-01-01T00:00:00Z")
                )

                meter_device = {
                    "DEVICE_TYPE": "Power Meter",
                    "SERIAL": sn,
                    "MODEL": model,
                    "DESCR": f"Power Meter {sn}",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "TYPE": meter_type,
                    "DATATIME": datatime,
                    "p_3phsum_kw": str(float(data.get("p3phsumKw", 0))),
                    "v12_v": str(float(data.get("v12V", 0))),
                    "freq_hz": str(float(data.get("freqHz", 0))),
                    "net_ltea_3phsum_kwh": str(
                        round(float(data.get("netLtea3phsumKwh", 0)), 2)
                    ),
                    "ct_scl_fctr": str(int(float(data.get("ctSclFctr", 1)))),
                    "q_3phsum_kvar": str(float(data.get("q3phsumKvar", 0))),
                    "s_3phsum_kva": str(float(data.get("s3phsumKva", 0))),
                    "tot_pf_rto": str(float(data.get("totPfRto", 0))),
                }

                if is_production:
                    i3ph = float(data.get("i3phsumA", 0))
                    if i3ph:
                        meter_device["i_a"] = str(i3ph)
                else:
                    # Consumption meter: bidirectional energy and per-leg data
                    neg_lte = float(data.get("negLtea3phsumKwh", 0))
                    pos_lte = float(data.get("posLtea3phsumKwh", 0))
                    if neg_lte:
                        meter_device["neg_ltea_3phsum_kwh"] = str(
                            round(neg_lte, 2)
                        )
                    if pos_lte:
                        meter_device["pos_ltea_3phsum_kwh"] = str(
                            round(pos_lte, 2)
                        )
                    for vs_field, legacy_field in [
                        ("p1Kw", "p1_kw"),
                        ("p2Kw", "p2_kw"),
                        ("i1A", "i1_a"),
                        ("i2A", "i2_a"),
                        ("v1nV", "v1n_v"),
                        ("v2nV", "v2n_v"),
                    ]:
                        val = float(data.get(vs_field, 0))
                        if val:
                            meter_device[legacy_field] = str(val)

                devices.append(meter_device)
            except Exception as e:
                _LOGGER.debug("Error building meter device: %s", e)

        return devices

    async def _build_ess(self) -> list[dict]:
        """Build ESS/battery device dicts from varserver."""
        ess_raw = await self._group_devices(_MATCH_ESS)
        if not ess_raw:
            return []

        devices = []
        for data in ess_raw:
            try:
                sn = data.get("sn", "")
                if not sn:
                    continue

                model = data.get("prodMdlNm", "")
                datatime = _iso_to_datatime(
                    data.get("msmtEps", "1970-01-01T00:00:00Z")
                )

                # varserver returns SOC/SOH as 0-1 decimals; convert to 0-100
                soc_val = float(data.get("socVal", 0)) * 100.0
                customer_soc_val = float(data.get("customerSocVal", 0)) * 100.0
                soh_val = float(data.get("sohVal", 0)) * 100.0

                devices.append({
                    "DEVICE_TYPE": "Energy Storage System",
                    "SERIAL": sn,
                    "MODEL": model,
                    "DESCR": f"Energy Storage System {sn}",
                    "HWVER": model,
                    "SWVER": "varserver",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "DATATIME": datatime,
                    "soc_val": str(soc_val),
                    "customer_soc_val": str(customer_soc_val),
                    "soh_val": str(soh_val),
                    "op_mode": str(data.get("opMode", "")),
                    "power_3ph_kw": str(float(data.get("p3phsumKw", 0))),
                    "neg_lte_kwh": str(float(data.get("negLtea3phsumKwh", 0))),
                    "pos_lte_kwh": str(float(data.get("posLtea3phsumKwh", 0))),
                    "v1n_v": str(float(data.get("v1nV", 0))),
                    "v2n_v": str(float(data.get("v2nV", 0))),
                    "v_batt_v": str(float(data.get("vBattV", 0))),
                    "t_invtr_degc": str(float(data.get("tInvtrDegc", 0))),
                    "chrg_limit_pmax_kw": str(
                        float(data.get("chrgLimitPmaxKw", 0))
                    ),
                    "dischrg_lim_pmax_kw": str(
                        float(data.get("dischrgLimPmaxKw", 0))
                    ),
                    "max_t_batt_cell_degc": str(
                        float(data.get("maxTBattCellDegc", 0))
                    ),
                    "min_t_batt_cell_degc": str(
                        float(data.get("minTBattCellDegc", 0))
                    ),
                    "max_v_batt_cell_v": str(
                        float(data.get("maxVBattCellV", 0))
                    ),
                    "min_v_batt_cell_v": str(
                        float(data.get("minVBattCellV", 0))
                    ),
                })
            except Exception as e:
                _LOGGER.debug("Error building ESS device: %s", e)

        return devices

    async def _build_transfer_switches(self) -> list[dict]:
        """Build transfer switch device dicts from varserver."""
        ts_raw = await self._group_devices(_MATCH_TRANSFER_SWITCH)
        if not ts_raw:
            return []

        devices = []
        for data in ts_raw:
            try:
                sn = data.get("sn", "")
                if not sn:
                    continue

                model = data.get("prodMdlNm", "")
                datatime = _iso_to_datatime(
                    data.get("msmtEps", "1970-01-01T00:00:00Z")
                )

                devices.append({
                    "DEVICE_TYPE": "Transfer Switch",
                    "SERIAL": sn,
                    "MODEL": model,
                    "DESCR": f"Transfer Switch {sn}",
                    "HWVER": model,
                    "SWVER": "varserver",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "DATATIME": datatime,
                    "mid_state": str(data.get("midStEnum", "")),
                    "pvd1_state": str(data.get("pvd1StEnum", "")),
                    "temperature_c": str(float(data.get("tDegc", 0))),
                    "v1n_grid_v": str(float(data.get("v1nGridV", 0))),
                    "v2n_grid_v": str(float(data.get("v2nGridV", 0))),
                    "v1n_v": str(float(data.get("v1nV", 0))),
                    "v2n_v": str(float(data.get("v2nV", 0))),
                    "v_supply_v": str(float(data.get("vSpplyV", 0))),
                })
            except Exception as e:
                _LOGGER.debug("Error building transfer switch device: %s", e)

        return devices
