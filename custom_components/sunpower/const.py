"""Constants for the Enhanced SunPower integration - WITH DIAGNOSTIC SENSORS."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)

DOMAIN = "sunpower"

SUNPOWER_DESCRIPTIVE_NAMES = "use_descriptive_names"
SUNPOWER_PRODUCT_NAMES = "use_product_names"
SUNPOWER_OBJECT = "sunpower"
SUNPOWER_HOST = "host"
SUNPOWER_COORDINATOR = "coordinator"
DEFAULT_SUNPOWER_UPDATE_INTERVAL = 120
DEFAULT_SUNVAULT_UPDATE_INTERVAL = 60
MIN_SUNPOWER_UPDATE_INTERVAL = 60
MIN_SUNVAULT_UPDATE_INTERVAL = 20
SUNPOWER_UPDATE_INTERVAL = "PVS_UPDATE_INTERVAL"
SUNVAULT_UPDATE_INTERVAL = "ESS_UPDATE_INTERVAL"
SETUP_TIMEOUT_MIN = 5

PVS_DEVICE_TYPE = "PVS"
INVERTER_DEVICE_TYPE = "Inverter"
METER_DEVICE_TYPE = "Power Meter"
BATTERY_DEVICE_TYPE = "ESS BMS"
ESS_DEVICE_TYPE = "Energy Storage System"
HUBPLUS_DEVICE_TYPE = "HUB+"
SUNVAULT_DEVICE_TYPE = "SunVault"
DIAGNOSTIC_DEVICE_TYPE = "Enhanced SunPower Diagnostics"

WORKING_STATE = "working"

SUNPOWER_BINARY_SENSORS = {
    METER_DEVICE_TYPE: {
        "unique_id": "meter",
        "sensors": {
            "METER_STATE": {
                "field": "STATE",
                "title": "{SUN_POWER}{DESCR}State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
    INVERTER_DEVICE_TYPE: {
        "unique_id": "inverter",
        "sensors": {
            "INVERTER_STATE": {
                "field": "STATE",
                "title": "{SUN_POWER}{DESCR}State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
    PVS_DEVICE_TYPE: {
        "unique_id": "pvs",
        "sensors": {
            "PVS_STATE": {
                "field": "STATE",
                "title": "{SUN_POWER}{MODEL} {SERIAL} State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
}

SUNPOWER_SENSORS = {
    PVS_DEVICE_TYPE: {
        "unique_id": "pvs",
        "sensors": {
            "PVS_LOAD": {
                "field": "dl_cpu_load",
                "title": "{SUN_POWER}{MODEL} {SERIAL} System Load",
                "unit": PERCENTAGE,
                "icon": "mdi:gauge",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_ERROR_COUNT": {
                "field": "dl_err_count",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Error Count",
                "unit": "",
                "icon": "mdi:alert-circle",
                "device": None,
                "state": SensorStateClass.TOTAL_INCREASING,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_COMMUNICATION_ERRORS": {
                "field": "dl_comm_err",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Communication Errors",
                "unit": "",
                "icon": "mdi:network-off",
                "device": None,
                "state": SensorStateClass.TOTAL_INCREASING,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_SKIPPED_SCANS": {
                "field": "dl_skipped_scans",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Skipped Scans",
                "unit": "",
                "icon": "mdi:network-strength-off-outline",
                "device": None,
                "state": SensorStateClass.TOTAL_INCREASING,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_SCAN_TIME": {
                "field": "dl_scan_time",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Scan Time",
                "unit": UnitOfTime.SECONDS,
                "icon": "mdi:timer-outline",
                "device": SensorDeviceClass.DURATION,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_UNTRANSMITTED": {
                "field": "dl_untransmitted",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Untransmitted Data",
                "unit": "",
                "icon": "mdi:radio-tower",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_UPTIME": {
                "field": "dl_uptime",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Uptime",
                "unit": UnitOfTime.SECONDS,
                "icon": "mdi:timer-outline",
                "device": SensorDeviceClass.DURATION,
                "state": SensorStateClass.TOTAL_INCREASING,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_MEMORY_USED": {
                "field": "dl_mem_used",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Memory Used",
                "unit": UnitOfInformation.KILOBYTES,
                "icon": "mdi:memory",
                "device": SensorDeviceClass.DATA_SIZE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_FLASH_AVAILABLE": {
                "field": "dl_flash_avail",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Flash Available",
                "unit": UnitOfInformation.KILOBYTES,
                "icon": "mdi:memory",
                "device": SensorDeviceClass.DATA_SIZE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "PVS_FIRMWARE": {
                "field": "SWVER",
                "title": "{SUN_POWER}{MODEL} {SERIAL} Firmware Version",
                "unit": None,
                "icon": "mdi:chip",
                "device": None,
                "state": None,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
    METER_DEVICE_TYPE: {
        "unique_id": "meter",
        "sensors": {
            "METER_FREQUENCY": {
                "field": "freq_hz",
                "title": "{SUN_POWER}{DESCR}Frequency",
                "unit": UnitOfFrequency.HERTZ,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.FREQUENCY,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_NET_KWH": {
                "field": "net_ltea_3phsum_kwh",
                "title": "{SUN_POWER}{DESCR}Lifetime Power",
                "unit": UnitOfEnergy.KILO_WATT_HOUR,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.ENERGY,
                "state": SensorStateClass.TOTAL,
            },
            "METER_KW": {
                "field": "p_3phsum_kw",
                "title": "{SUN_POWER}{DESCR}Power",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
            "METER_VAR": {
                "field": "q_3phsum_kvar",
                "title": "{SUN_POWER}{DESCR}Reactive Power",
                "unit": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.REACTIVE_POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_VA": {
                "field": "s_3phsum_kva",
                "title": "{SUN_POWER}{DESCR}Apparent Power",
                "unit": UnitOfApparentPower.VOLT_AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.APPARENT_POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_POWER_FACTOR": {
                "field": "tot_pf_rto",
                "title": "{SUN_POWER}{DESCR}Power Factor",
                "unit": PERCENTAGE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER_FACTOR,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L1_A": {
                "field": "i1_a",
                "title": "{SUN_POWER}{DESCR}Leg 1 Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_A": {
                "field": "i_a",
                "title": "{SUN_POWER}{DESCR}Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L2_A": {
                "field": "i2_a",
                "title": "{SUN_POWER}{DESCR}Leg 2 Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L1_KW": {
                "field": "p1_kw",
                "title": "{SUN_POWER}{DESCR}Leg 1 KW",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L2_KW": {
                "field": "p2_kw",
                "title": "{SUN_POWER}{DESCR}Leg 2 KW",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L1_V": {
                "field": "v1n_v",
                "title": "{SUN_POWER}{DESCR}Leg 1 Volts",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L2_V": {
                "field": "v2n_v",
                "title": "{SUN_POWER}{DESCR}Leg 2 Volts",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "METER_L12_V": {
                "field": "v12_v",
                "title": "{SUN_POWER}{DESCR}Supply Volts",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
            },
            "METER_TO_GRID": {
                "field": "neg_ltea_3phsum_kwh",
                "title": "{SUN_POWER}{DESCR}KWh To Grid",
                "unit": UnitOfEnergy.KILO_WATT_HOUR,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.ENERGY,
                "state": SensorStateClass.TOTAL_INCREASING,
            },
            "METER_TO_HOME": {
                "field": "pos_ltea_3phsum_kwh",
                "title": "{SUN_POWER}{DESCR}KWh To Home",
                "unit": UnitOfEnergy.KILO_WATT_HOUR,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.ENERGY,
                "state": SensorStateClass.TOTAL_INCREASING,
            },
        },
    },
    INVERTER_DEVICE_TYPE: {
        "unique_id": "inverter",
        "sensors": {
            "INVERTER_NET_KWH": {
                "field": "ltea_3phsum_kwh",
                "title": "{SUN_POWER}{DESCR}Lifetime Power",
                "unit": UnitOfEnergy.KILO_WATT_HOUR,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.ENERGY,
                "state": SensorStateClass.TOTAL_INCREASING,
            },
            "INVERTER_KW": {
                "field": "p_3phsum_kw",
                "title": "{SUN_POWER}{DESCR}Power",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
            "INVERTER_VOLTS": {
                "field": "vln_3phavg_v",
                "title": "{SUN_POWER}{DESCR}Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_AMPS": {
                "field": "i_3phsum_a",
                "title": "{SUN_POWER}{DESCR}Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_MPPT1_KW": {
                "field": "p_mppt1_kw",
                "title": "{SUN_POWER}{DESCR}MPPT KW",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_MPPT_V": {
                "field": "v_mppt1_v",
                "title": "{SUN_POWER}{DESCR}MPPT Volts",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_MPPT_A": {
                "field": "i_mppt1_a",
                "title": "{SUN_POWER}{DESCR}MPPT Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_TEMPERATURE": {
                "field": "t_htsnk_degc",
                "title": "{SUN_POWER}{DESCR}Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "INVERTER_FREQUENCY": {
                "field": "freq_hz",
                "title": "{SUN_POWER}{DESCR}Frequency",
                "unit": UnitOfFrequency.HERTZ,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.FREQUENCY,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
    # NEW: Diagnostic sensors for dashboard monitoring
    DIAGNOSTIC_DEVICE_TYPE: {
        "unique_id": "diagnostics",
        "sensors": {
            "POLL_SUCCESS_RATE": {
                "field": "poll_success_rate",
                "title": "SunPower Poll Success Rate",
                "unit": PERCENTAGE,
                "icon": "mdi:check-circle",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
            },
            "TOTAL_POLLS": {
                "field": "total_polls",
                "title": "SunPower Total Polls",
                "unit": "",
                "icon": "mdi:counter",
                "device": None,
                "state": SensorStateClass.TOTAL_INCREASING,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "CONSECUTIVE_FAILURES": {
                "field": "consecutive_failures",
                "title": "SunPower Consecutive Failures",
                "unit": "",
                "icon": "mdi:alert-circle",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "LAST_SUCCESSFUL_POLL": {
                "field": "last_successful_poll",
                "title": "SunPower Last Successful Poll",
                "unit": None,
                "icon": "mdi:clock-check",
                "device": None,
                "state": None,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "AVERAGE_RESPONSE_TIME": {
                "field": "average_response_time",
                "title": "SunPower Average Response Time",
                "unit": UnitOfTime.SECONDS,
                "icon": "mdi:speedometer",
                "device": SensorDeviceClass.DURATION,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ACTIVE_INVERTERS": {
                "field": "active_inverters",
                "title": "SunPower Active Inverters",
                "unit": "",
                "icon": "mdi:solar-panel",
                "device": None,
                "state": None,
            },
            "PVS_UPTIME_PERCENT": {
                "field": "pvs_uptime_percent",
                "title": "SunPower PVS Uptime",
                "unit": PERCENTAGE,
                "icon": "mdi:server-network",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
}

# NOTE: Battery/SunVault sensors moved to battery_handler.py for better organization