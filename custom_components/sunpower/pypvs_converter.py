"""pypvs to Legacy dl_cgi Format Converter

Converts pypvs PVSData objects (new firmware LocalAPI format)
to legacy dl_cgi format (old firmware format) for compatibility
with existing data_processor.py logic.
"""

import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


def convert_pypvs_to_legacy(pvs_data, pvs_serial=None, flashwear_percent=0):
    """Convert pypvs PVSData object to legacy dl_cgi format

    pypvs uses structured models (pvs_data.inverters, pvs_data.meters, etc.)
    while our data_processor expects dl_cgi format: {"devices": [...]}

    This converter bridges the gap with minimal code changes.

    Args:
        pvs_data: PVSData object from pypvs.update() call
        pvs_serial: PVS serial number from pvs_object.serial_number

    Returns:
        dict: Legacy format {"devices": [device_dicts...]}
    """
    devices = []

    try:
        # Convert Gateway (PVS device)
        if hasattr(pvs_data, 'gateway') and pvs_data.gateway:
            gateway = pvs_data.gateway
            serial = pvs_serial or "Unknown"
            raw_model = getattr(gateway, 'model', 'PVS6')
            _LOGGER.debug("Gateway model from pypvs: '%s'", raw_model)

            # Match old dl_cgi MODEL format: "PV Supervisor PVS6"
            # pypvs returns sys_type which is "PV-only" for PVS6, need hardware model instead
            if hasattr(gateway, 'hardware_version'):
                # Extract model from hardware_version (e.g., "PVS6 6.02" -> "PVS6")
                hw_ver = gateway.hardware_version
                model_parts = hw_ver.split()
                model = model_parts[0] if model_parts else "PVS6"
            else:
                model = raw_model if raw_model != "PV-only" else "PVS6"

            # Prepend "PV Supervisor" to match old format
            if not model.startswith("PV Supervisor"):
                model = f"PV Supervisor {model}"

            _LOGGER.debug("Final PVS MODEL: '%s'", model)
            pvs_device = {
                "DEVICE_TYPE": "PVS",
                "SERIAL": serial,
                "MODEL": model,
                "SWVER": getattr(gateway, 'software_version', 'Unknown'),
                "HWVER": getattr(gateway, 'hardware_version', 'Unknown'),
                "STATE": "working",
                "STATEDESCR": "Working",
                "dl_uptime": str(int(float(getattr(gateway, 'uptime_s', 0)))),
                "dl_cpu_load": str(float(getattr(gateway, 'cpu_usage_percent', 0)) / 100),
                "dl_mem_used": "0",  # pypvs only provides ram_usage_percent, not actual KB
                "dl_flash_avail": "0",  # pypvs only provides flash_usage_percent, not actual KB
                "ram_usage_percent": str(int(float(getattr(gateway, 'ram_usage_percent', 0)))),
                "flash_usage_percent": str(int(float(getattr(gateway, 'flash_usage_percent', 0)))),
                "flashwear_percent": str(int(flashwear_percent)),
                "dl_err_count": "0",
                "dl_comm_err": "0",
                "dl_skipped_scans": "0",
                "dl_scan_time": "0",
                "dl_untransmitted": "0",
                "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
            }
            devices.append(pvs_device)
            _LOGGER.debug("Converted pypvs gateway to PVS device")

        # Convert Inverters - using EXACT pypvs field names from inverter.py model
        if hasattr(pvs_data, 'inverters') and pvs_data.inverters:
            _LOGGER.info("pypvs reports %d inverters available", len(pvs_data.inverters))
            for serial, inverter in pvs_data.inverters.items():
                inv_device = {
                    "DEVICE_TYPE": "Inverter",
                    "SERIAL": inverter.serial_number,
                    "MODEL": inverter.model or 'AC_Module_Type_E',
                    "DESCR": f"Inverter {inverter.serial_number}",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    # pypvs doesn't provide firmware/hardware - use placeholders until fixed
                    "SWVER": "pypvs",
                    "HWVER": inverter.model or 'AC_Module_Type_E',
                    # pypvs inverter fields mapped to dl_cgi field names for entity compatibility
                    "ltea_3phsum_kwh": str(inverter.lte_kwh),
                    "p_3phsum_kw": str(inverter.last_report_kw),
                    "vln_3phavg_v": str(inverter.last_report_voltage_v),
                    "i_3phsum_a": str(inverter.last_report_current_a),
                    "freq_hz": str(inverter.last_report_frequency_hz),
                    "t_htsnk_degc": str(inverter.last_report_temperature_c),
                    # MPPT data - pypvs doesn't separate MPPT, use same values
                    "p_mppt1_kw": str(inverter.last_report_kw),
                    "v_mppt1_v": str(inverter.last_report_voltage_v),
                    "i_mppt1_a": str(inverter.last_report_current_a),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(inv_device)
            _LOGGER.info("✅ Converted %d pypvs inverters to legacy format", len(pvs_data.inverters))
        else:
            _LOGGER.warning("⚠️ No inverters found in pypvs data - inverters may be offline (nighttime?)")

        # Convert Meters - using EXACT pypvs field names from meter.py model
        if hasattr(pvs_data, 'meters') and pvs_data.meters:
            for serial, meter in pvs_data.meters.items():
                # Determine meter type from model: 'p' suffix = production, 'c' suffix = consumption
                model = meter.model or 'PVS6M0400p'
                is_production = model.lower().endswith('p')
                meter_type = "PVS5-METER-P" if is_production else "PVS5-METER-C"

                meter_device = {
                    "DEVICE_TYPE": "Power Meter",
                    "SERIAL": meter.serial_number,
                    "MODEL": model,
                    "DESCR": f"Power Meter {meter.serial_number}",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "TYPE": meter_type,
                    # pypvs meter fields mapped to dl_cgi field names
                    "p_3phsum_kw": str(meter.power_3ph_kw),
                    "v12_v": str(meter.v12_v),
                    "freq_hz": str(meter.freq_hz),
                    "net_ltea_3phsum_kwh": str(meter.net_lte_kwh),
                    "ct_scl_fctr": str(int(meter.ct_scale_factor)),
                    "q_3phsum_kvar": str(meter.q3phsum_kvar),
                    "s_3phsum_kva": str(meter.s3phsum_kva),
                    "tot_pf_rto": str(meter.tot_pf_ratio),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }

                # Production meters: Add combined current (i_a) if available
                if is_production:
                    if hasattr(meter, 'current_3ph_a'):
                        meter_device["i_a"] = str(meter.current_3ph_a)
                # Consumption meters: Add per-leg data and bidirectional energy
                else:
                    # Bidirectional energy (consumption meters only)
                    if meter.neg_lte_kwh != 0:
                        meter_device["neg_ltea_3phsum_kwh"] = str(meter.neg_lte_kwh)
                    if meter.pos_lte_kwh != 0:
                        meter_device["pos_ltea_3phsum_kwh"] = str(meter.pos_lte_kwh)
                    # Per-leg data (consumption meters only)
                    if meter.p1_kw != 0:
                        meter_device["p1_kw"] = str(meter.p1_kw)
                    if meter.p2_kw != 0:
                        meter_device["p2_kw"] = str(meter.p2_kw)
                    if meter.i1_a != 0:
                        meter_device["i1_a"] = str(meter.i1_a)
                    if meter.i2_a != 0:
                        meter_device["i2_a"] = str(meter.i2_a)
                    if meter.v1n_v != 0:
                        meter_device["v1n_v"] = str(meter.v1n_v)
                    if meter.v2n_v != 0:
                        meter_device["v2n_v"] = str(meter.v2n_v)

                devices.append(meter_device)
            _LOGGER.debug("Converted %d pypvs meters", len(pvs_data.meters))

        # Convert ESS/Battery (if present)
        if hasattr(pvs_data, 'ess') and pvs_data.ess:
            for serial, ess in pvs_data.ess.items():
                ess_device = {
                    "DEVICE_TYPE": "Energy Storage System",
                    "SERIAL": ess.serial_number,
                    "MODEL": ess.model,
                    "DESCR": f"Energy Storage System {ess.serial_number}",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    # pypvs doesn't provide firmware/hardware - use placeholders until fixed
                    "SWVER": "pypvs",
                    "HWVER": ess.model,
                    # pypvs PVSESS fields mapped to dl_cgi-style field names
                    # pypvs provides SOC/SOH as decimals (0-1), convert to percentages (0-100)
                    "soc_val": str(ess.soc_val * 100),
                    "customer_soc_val": str(ess.customer_soc_val * 100),
                    "soh_val": str(ess.soh_val * 100),
                    "op_mode": ess.op_mode,
                    "power_3ph_kw": str(ess.power_3ph_kw),
                    "neg_lte_kwh": str(ess.neg_lte_kwh),
                    "pos_lte_kwh": str(ess.pos_lte_kwh),
                    "v1n_v": str(ess.v1n_v),
                    "v2n_v": str(ess.v2n_v),
                    "v_batt_v": str(ess.v_batt_v),
                    "t_invtr_degc": str(ess.t_invtr_degc),
                    "chrg_limit_pmax_kw": str(ess.chrg_limit_pmax_kw),
                    "dischrg_lim_pmax_kw": str(ess.dischrg_lim_pmax_kw),
                    "max_t_batt_cell_degc": str(ess.max_t_batt_cell_degc),
                    "min_t_batt_cell_degc": str(ess.min_t_batt_cell_degc),
                    "max_v_batt_cell_v": str(ess.max_v_batt_cell_v),
                    "min_v_batt_cell_v": str(ess.min_v_batt_cell_v),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(ess_device)
            _LOGGER.debug("Converted %d pypvs ESS devices", len(pvs_data.ess))

        # Convert Transfer Switches (if present)
        if hasattr(pvs_data, 'transfer_switches') and pvs_data.transfer_switches:
            for serial, ts in pvs_data.transfer_switches.items():
                ts_device = {
                    "DEVICE_TYPE": "Transfer Switch",
                    "SERIAL": ts.serial_number,
                    "MODEL": ts.model,
                    "DESCR": f"Transfer Switch {ts.serial_number}",
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    # pypvs doesn't provide firmware/hardware - use placeholders until fixed
                    "SWVER": "pypvs",
                    "HWVER": ts.model,
                    # pypvs PVSTransferSwitch fields mapped to dl_cgi field names
                    "mid_state": ts.mid_state,
                    "pvd1_state": ts.pvd1_state,
                    "temperature_c": str(ts.temperature_c),
                    "v1n_grid_v": str(ts.v1n_grid_v),
                    "v2n_grid_v": str(ts.v2n_grid_v),
                    "v1n_v": str(ts.v1n_v),
                    "v2n_v": str(ts.v2n_v),
                    "v_supply_v": str(ts.v_supply_v),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(ts_device)
            _LOGGER.debug("Converted %d pypvs transfer switches", len(pvs_data.transfer_switches))

        _LOGGER.debug("✅ pypvs → dl_cgi conversion: %d devices total", len(devices))
        return {"devices": devices}

    except Exception as e:
        _LOGGER.error("❌ Failed to convert pypvs data to legacy format: %s", e, exc_info=True)
        return {"devices": []}
