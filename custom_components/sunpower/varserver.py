"""Minimal varserver wrapper for ESS data - Enhanced SunPower Integration"""

import aiohttp
import asyncio
import base64
import logging
from typing import Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)


class VarserverError(Exception):
    """Base exception for varserver operations"""


class VarserverClient:
    """Minimal varserver client focused on ESS data extraction"""

    def __init__(self, host: str, username: str = "ssm_owner", password: str = None):
        """Initialize varserver client

        Args:
            host: PVS IP address or hostname
            username: Authentication username (default: ssm_owner)
            password: Authentication password (typically last 5 chars of PVS serial)
        """
        self.host = host
        self.username = username
        self.password = password
        self._session = None
        self._authenticated = False

        # Build auth header - use lowercase "basic" and utf-8 per pypvs standard
        if username and password:
            auth_string = f"{username}:{password}"
            auth_bytes = auth_string.encode('utf-8')
            self._auth_header = base64.b64encode(auth_bytes).decode('utf-8')
        else:
            self._auth_header = None

    async def _ensure_session(self):
        """Ensure we have an active session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._authenticated = False

    async def _authenticate(self):
        """Authenticate with the PVS using FCGI"""
        if not self._auth_header:
            return False

        await self._ensure_session()

        try:
            # Clear cookies before authentication (fixes pypvs issue #7)
            # Cookies are cached implicitly by aiohttp and can interfere with auth
            self._session.cookie_jar.clear()

            auth_url = f"https://{self.host}/auth?login"
            headers = {"Authorization": f"basic {self._auth_header}"}

            async with self._session.get(auth_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    self._authenticated = True
                    _LOGGER.debug("Varserver authentication successful")
                    return True
                else:
                    _LOGGER.warning("Varserver authentication failed: %s", response.status)
                    return False

        except Exception as e:
            _LOGGER.error("Varserver authentication error: %s", e)
            return False

    async def get_var(self, var_name: str) -> Optional[Any]:
        """Get a single variable from varserver"""
        await self._ensure_session()

        if not self._authenticated:
            if not await self._authenticate():
                raise VarserverError("Authentication failed")

        try:
            url = f"https://{self.host}/vars"
            params = {"name": var_name}

            async with self._session.post(url, params=params, ssl=False) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Re-authenticate and retry
                    if await self._authenticate():
                        async with self._session.post(url, params=params, ssl=False) as retry_response:
                            if retry_response.status == 200:
                                return await retry_response.json()
                    raise VarserverError("Authentication failed on retry")
                else:
                    raise VarserverError(f"HTTP {response.status}")

        except Exception as e:
            raise VarserverError(f"Variable fetch failed: {e}")

    async def get_vars(self, var_pattern: str) -> Dict[str, Any]:
        """Get multiple variables matching a pattern from varserver

        Args:
            var_pattern: Variable path pattern (e.g., "/sys/devices/ess/")
                        Returns all variables under this path

        Returns:
            Dictionary of variable paths to values
        """
        await self._ensure_session()

        if not self._authenticated:
            if not await self._authenticate():
                raise VarserverError("Authentication failed")

        try:
            url = f"https://{self.host}/vars"
            params = {"name": var_pattern}

            async with self._session.post(url, params=params, ssl=False) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Re-authenticate and retry
                    if await self._authenticate():
                        async with self._session.post(url, params=params, ssl=False) as retry_response:
                            if retry_response.status == 200:
                                return await retry_response.json()
                    raise VarserverError("Authentication failed on retry")
                else:
                    raise VarserverError(f"HTTP {response.status}")

        except Exception as e:
            raise VarserverError(f"Variables fetch failed: {e}")

    async def fetch_ess_data(self) -> Dict[str, Any]:
        """Fetch ESS data from varserver using efficient bulk query

        Queries /sys/devices/ess/* which returns ALL ESS variables in one request.
        Follows pypvs pattern for maximum efficiency.

        Returns:
            Dictionary with grouped ESS data by device index
        """
        try:
            # Get ALL ESS variables in one request - much more efficient!
            ess_vars = await self.get_vars("/sys/devices/ess/")

            if not ess_vars:
                _LOGGER.debug("No ESS devices found on varserver")
                return {}

            # Group variables by ESS device index
            # Path format: /sys/devices/ess/0/socVal -> index=0, param=socVal
            ess_grouped = {}

            for var_path, value in ess_vars.items():
                try:
                    parts = var_path.split("/")
                    if len(parts) >= 6:  # /sys/devices/ess/{index}/{param}
                        idx = int(parts[4])
                        param = parts[5]

                        if idx not in ess_grouped:
                            ess_grouped[idx] = {}

                        ess_grouped[idx][param] = value

                except (ValueError, IndexError) as e:
                    _LOGGER.debug("Skipping invalid ESS var path %s: %s", var_path, e)
                    continue

            _LOGGER.debug("Found %d ESS devices from varserver", len(ess_grouped))
            return ess_grouped

        except Exception as e:
            _LOGGER.error("Failed to fetch ESS data from varserver: %s", e)
            raise VarserverError(f"ESS data fetch failed: {e}")

    def convert_ess_to_legacy_format(self, ess_grouped: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert varserver ESS data to legacy dl_cgi ESS status format

        This maintains backward compatibility with existing battery sensor code.

        Args:
            ess_grouped: Grouped ESS data by device index from fetch_ess_data()

        Returns:
            Dictionary in legacy ess_report format compatible with battery_handler.py
        """
        if not ess_grouped:
            return {"ess_report": {"battery_status": [], "ess_status": [], "hub_plus_status": None}}

        battery_status = []
        ess_status = []

        for idx, ess_data in ess_grouped.items():
            try:
                # Extract serial number
                serial = ess_data.get("sn", f"ESS_{idx}")

                # Get battery metrics with safe float conversion
                soc = float(ess_data.get("socVal", 0))
                customer_soc = float(ess_data.get("customerSocVal", 0))
                battery_voltage = float(ess_data.get("vBattV", 0))
                temperature = float(ess_data.get("tInvtrDegc", 0))
                power_kw = float(ess_data.get("p3phsumKw", 0))

                # Calculate battery amperage from power and voltage
                battery_amperage = (power_kw * 1000 / battery_voltage) if battery_voltage > 0 else 0

                # Create battery_status entry (compatible with battery_handler.py)
                battery_entry = {
                    "serial_number": f"battery_{serial}",
                    "battery_amperage": {"value": battery_amperage},
                    "battery_voltage": {"value": battery_voltage},
                    "customer_state_of_charge": {"value": customer_soc},
                    "system_state_of_charge": {"value": soc},
                    "temperature": {"value": temperature}
                }
                battery_status.append(battery_entry)

                # Create ess_status entry (compatible with battery_handler.py)
                ess_entry = {
                    "serial_number": serial,
                    "enclosure_humidity": {"value": 0},  # Not available via varserver
                    "enclosure_temperature": {"value": temperature},
                    "ess_meter_reading": {
                        "agg_power": {"value": power_kw},
                        "meter_a": {"reading": {}},
                        "meter_b": {"reading": {}}
                    }
                }
                ess_status.append(ess_entry)

                _LOGGER.debug("Converted ESS device %s: SOC=%.1f%%, Power=%.2fkW, Voltage=%.1fV",
                             serial, soc, power_kw, battery_voltage)

            except Exception as e:
                _LOGGER.warning("Failed to convert ESS device %d: %s", idx, e)
                continue

        return {
            "ess_report": {
                "battery_status": battery_status,
                "ess_status": ess_status,
                "hub_plus_status": None  # Hub Plus not typically in varserver
            }
        }

    async def probe_capability(self) -> bool:
        """Test if varserver is available and responding

        Uses short timeout (10s) to avoid blocking startup on old firmware
        """
        try:
            # Create session with short timeout for probe
            if self._session is None or self._session.closed:
                probe_timeout = aiohttp.ClientTimeout(total=10)
                self._session = aiohttp.ClientSession(timeout=probe_timeout)
                self._authenticated = False

            # Try to get system info as a basic connectivity test
            info = await self.get_var("/sys/info/uptime")
            return info is not None

        except Exception as e:
            _LOGGER.debug("Varserver probe failed: %s", e)
            return False

    async def fetch_device_list(self) -> Dict[str, Any]:
        """Fetch device list from varserver - required for firmware 61840+

        Converts varserver data to dl_cgi DeviceList format for compatibility.
        Some diagnostic fields (dl_*) may be unavailable from varserver.
        """
        try:
            # Get all device data from varserver
            pvs_info_raw = await self.get_vars("/sys/info/")
            inverters_raw = await self.get_vars("/sys/devices/inverter/")
            meters_raw = await self.get_vars("/sys/devices/meter/")

            # Flatten responses
            pvs_info = self._flatten_response(pvs_info_raw)
            inverters = self._flatten_response(inverters_raw)
            meters = self._flatten_response(meters_raw)

            devices = []

            # Build PVS device
            if pvs_info:
                pvs_dev = {
                    "SERIAL": pvs_info.get("/sys/info/serialnum", "UNKNOWN"),
                    "TYPE": "PVS",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "MODEL": pvs_info.get("/sys/info/model", "PVS6"),
                    "HWVER": pvs_info.get("/sys/info/hwrev", ""),
                    "SWVER": pvs_info.get("/sys/info/sw_rev", ""),
                    "DEVICE_TYPE": "PVS",
                    "DATATIME": ""
                }
                devices.append(pvs_dev)

            # Build inverter devices
            inv_grouped = self._group_by_index(inverters, 4)
            for idx, inv_data in inv_grouped.items():
                serial = inv_data.get("sn", f"INV_{idx}")
                inv_dev = {
                    "SERIAL": serial,
                    "TYPE": "Inverter",
                    "STATE": inv_data.get("state", "working"),
                    "STATEDESCR": inv_data.get("state", "Working"),
                    "MODEL": inv_data.get("prodMdlNm", ""),
                    "DESCR": f"Inverter {serial}",
                    "HWVER": inv_data.get("hwVer", ""),
                    "SWVER": inv_data.get("swVer", ""),
                    "DEVICE_TYPE": "Inverter",
                    "DATATIME": inv_data.get("msmtEps", ""),
                    "ltea_3phsum_kwh": inv_data.get("ltea3phsumKwh", 0.0),
                    "p_3phsum_kw": inv_data.get("p3phsumKw", 0.0),
                    "vln_3phavg_v": inv_data.get("vln3phavgV", 0.0),
                    "freq_hz": inv_data.get("freqHz", 0.0),
                    "i_3phsum_a": inv_data.get("i3phsumA", 0.0),
                    "t_htsnk_degc": inv_data.get("tHtsnkDegc", 0.0)
                }
                devices.append(inv_dev)

            # Build meter devices
            meter_grouped = self._group_by_index(meters, 4)
            for idx, meter_data in meter_grouped.items():
                serial = meter_data.get("sn", f"METER_{idx}")
                meter_dev = {
                    "SERIAL": serial,
                    "TYPE": "Power Meter",
                    "STATE": meter_data.get("state", "working"),
                    "STATEDESCR": meter_data.get("state", "Working"),
                    "MODEL": meter_data.get("prodMdlNm", ""),
                    "DESCR": f"Power Meter {serial}",
                    "HWVER": meter_data.get("hwVer", ""),
                    "SWVER": meter_data.get("swVer", ""),
                    "DEVICE_TYPE": "Power Meter",
                    "DATATIME": meter_data.get("msmtEps", ""),
                    "net_ltea_3phsum_kwh": meter_data.get("netLtea3phsumKwh", 0.0),
                    "p_3phsum_kw": meter_data.get("p3phsumKw", 0.0),
                    "freq_hz": meter_data.get("freqHz", 0.0)
                }
                devices.append(meter_dev)

            _LOGGER.info("Fetched %d devices from varserver", len(devices))
            return {"devices": devices}

        except Exception as e:
            _LOGGER.error("Failed to fetch device list from varserver: %s", e)
            raise VarserverError(f"Device list fetch failed: {e}")

    def _flatten_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten varserver response from {values:[{name,value}]} to {name:value}"""
        if not response or "values" not in response:
            return {}
        return {item["name"]: item["value"] for item in response["values"]}

    def _group_by_index(self, flat_vars: Dict[str, Any], index_pos: int) -> Dict[int, Dict[str, Any]]:
        """Group variables by device index from path like /sys/devices/inverter/0/param"""
        grouped = {}
        for path, value in flat_vars.items():
            parts = path.split("/")
            if len(parts) > index_pos + 1:
                try:
                    idx = int(parts[index_pos])
                    param = parts[index_pos + 1]
                    if idx not in grouped:
                        grouped[idx] = {}
                    grouped[idx][param] = value
                except (ValueError, IndexError):
                    continue
        return grouped

    async def close(self):
        """Clean up session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None