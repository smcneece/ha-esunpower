"""pypvs to Legacy dl_cgi Format Converter

Converts pypvs PVSData objects (new firmware LocalAPI format)
to legacy dl_cgi format (old firmware format) for compatibility
with existing data_processor.py logic.
"""

import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


def convert_pypvs_to_legacy(pvs_data):
    """Convert pypvs PVSData object to legacy dl_cgi format

    pypvs uses structured models (pvs_data.inverters, pvs_data.meters, etc.)
    while our data_processor expects dl_cgi format: {"devices": [...]}

    This converter bridges the gap with minimal code changes.

    Args:
        pvs_data: PVSData object from pypvs.update() call

    Returns:
        dict: Legacy format {"devices": [device_dicts...]}
    """
    devices = []

    try:
        # Convert Gateway (PVS device)
        if hasattr(pvs_data, 'gateway') and pvs_data.gateway:
            gateway = pvs_data.gateway
            pvs_device = {
                "DEVICE_TYPE": "PVS",
                "SERIAL": getattr(pvs_data, '_firmware', None) and pvs_data._firmware.serial or "Unknown",
                "MODEL": getattr(gateway, 'model', 'PVS6'),
                "SWVER": getattr(gateway, 'software_version', 'Unknown'),
                "HWVER": getattr(gateway, 'hardware_version', 'Unknown'),
                "STATE": "working",
                "STATEDESCR": "Working",
                "dl_uptime": str(int(getattr(gateway, 'uptime_s', 0))),
                "dl_cpu_load": str(float(getattr(gateway, 'cpu_usage_percent', 0)) / 100),
                "dl_mem_used": str(int(getattr(gateway, 'ram_usage_percent', 0) * 1000)),  # Rough estimate
                "dl_flash_avail": str(100 - int(getattr(gateway, 'flash_usage_percent', 0))),
                "dl_err_count": "0",
                "dl_comm_err": "0",
                "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
            }
            devices.append(pvs_device)
            _LOGGER.debug("Converted pypvs gateway to PVS device")

        # Convert Inverters
        if hasattr(pvs_data, 'inverters') and pvs_data.inverters:
            for serial, inverter in pvs_data.inverters.items():
                inv_device = {
                    "DEVICE_TYPE": "Inverter",
                    "SERIAL": serial,
                    "MODEL": getattr(inverter, 'model', 'Unknown'),
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    # Map pypvs fields to dl_cgi field names
                    "p_kw": str(float(getattr(inverter, 'last_report_kw', 0))),
                    "vln_a": str(float(getattr(inverter, 'last_report_voltage_v', 0))),
                    "i_a": str(float(getattr(inverter, 'last_report_current_a', 0))),
                    "freq_hz": str(float(getattr(inverter, 'last_report_frequency_hz', 0))),
                    "t_htsnk_degc": str(float(getattr(inverter, 'last_report_temperature_c', 0))),
                    "ltea_kwh": str(float(getattr(inverter, 'lte_kwh', 0))),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(inv_device)
            _LOGGER.debug("Converted %d pypvs inverters", len(pvs_data.inverters))

        # Convert Meters
        if hasattr(pvs_data, 'meters') and pvs_data.meters:
            for serial, meter in pvs_data.meters.items():
                meter_device = {
                    "DEVICE_TYPE": "Power Meter",
                    "SERIAL": serial,
                    "MODEL": getattr(meter, 'model', 'Unknown'),
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "TYPE": "PVS-METER-P",
                    # Map pypvs fields to dl_cgi field names
                    "p_3phsum_kw": str(float(getattr(meter, 'power_3ph_kw', 0))),
                    "v12_v": str(float(getattr(meter, 'v12_v', 0))),
                    "i_a": str(float(getattr(meter, 'current_3ph_a', 0))),
                    "freq_hz": str(float(getattr(meter, 'freq_hz', 0))),
                    "net_ltea_3phsum_kwh": str(float(getattr(meter, 'net_lte_kwh', 0))),
                    "neg_ltea_3phsum_kwh": str(float(getattr(meter, 'neg_lte_kwh', 0))),
                    "pos_ltea_3phsum_kwh": str(float(getattr(meter, 'pos_lte_kwh', 0))),
                    "ct_scl_fctr": str(int(getattr(meter, 'ct_scale_factor', 1))),
                    "q_3phsum_kvar": str(float(getattr(meter, 'q3phsum_kvar', 0))),
                    "s_3phsum_kva": str(float(getattr(meter, 's3phsum_kva', 0))),
                    "tot_pf_rto": str(float(getattr(meter, 'tot_pf_ratio', 1.0))),
                    "p_1_kw": str(float(getattr(meter, 'p1_kw', 0))),
                    "p_2_kw": str(float(getattr(meter, 'p2_kw', 0))),
                    "i1_a": str(float(getattr(meter, 'i1_a', 0))),
                    "i2_a": str(float(getattr(meter, 'i2_a', 0))),
                    "v1n_v": str(float(getattr(meter, 'v1n_v', 0))),
                    "v2n_v": str(float(getattr(meter, 'v2n_v', 0))),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(meter_device)
            _LOGGER.debug("Converted %d pypvs meters", len(pvs_data.meters))

        # Convert ESS/Battery (if present)
        if hasattr(pvs_data, 'ess') and pvs_data.ess:
            for serial, ess in pvs_data.ess.items():
                ess_device = {
                    "DEVICE_TYPE": "Energy Storage System",
                    "SERIAL": serial,
                    "MODEL": getattr(ess, 'model', 'SunVault'),
                    "STATE": "working",
                    "STATEDESCR": "Working",
                    "soc": str(float(getattr(ess, 'state_of_charge', 0))),
                    "DATATIME": datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S"),
                }
                devices.append(ess_device)
            _LOGGER.debug("Converted %d pypvs ESS devices", len(pvs_data.ess))

        _LOGGER.info("✅ pypvs → dl_cgi conversion: %d devices total", len(devices))
        return {"devices": devices}

    except Exception as e:
        _LOGGER.error("❌ Failed to convert pypvs data to legacy format: %s", e, exc_info=True)
        return {"devices": []}
