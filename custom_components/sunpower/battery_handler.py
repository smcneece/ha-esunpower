"""SunPower SunVault Battery System Handler - WITH EXTRACTED CONSTANTS"""

import logging
import time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)

from .const import (
    BATTERY_DEVICE_TYPE,
    ESS_DEVICE_TYPE,
    HUBPLUS_DEVICE_TYPE,
    PVS_DEVICE_TYPE,
    SUNVAULT_DEVICE_TYPE,
    WORKING_STATE,
)

_LOGGER = logging.getLogger(__name__)

# ==========================================
# EXTRACTED BATTERY CONSTANTS FROM const.py
# ==========================================

SUNVAULT_BINARY_SENSORS = {
    HUBPLUS_DEVICE_TYPE: {
        "unique_id": "hubplus",
        "sensors": {
            "HUBPLUS_STATE": {
                "field": "STATE",
                "title": "{SUN_POWER}Hub Plus State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
    ESS_DEVICE_TYPE: {
        "unique_id": "ess",
        "sensors": {
            "ESS_STATE": {
                "field": "STATE",
                "title": "{SUN_VAULT}ESS {index}State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
    BATTERY_DEVICE_TYPE: {
        "unique_id": "battery",
        "sensors": {
            "BATTERY_STATE": {
                "field": "STATE",
                "title": "{SUN_VAULT}Battery {index}State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
    SUNVAULT_DEVICE_TYPE: {
        "unique_id": "sunvault",
        "sensors": {
            "SUNVAULT_STATE": {
                "field": "STATE",
                "title": "{SUN_VAULT}State",
                "device": SensorDeviceClass.POWER,
                "on_value": WORKING_STATE,
            },
        },
    },
}

SUNVAULT_SENSORS = {
    SUNVAULT_DEVICE_TYPE: {
        "unique_id": "sunvault",
        "sensors": {
            "SUNVAULT_AMPERAGE": {
                "field": "sunvault_amperage",
                "title": "{SUN_VAULT}Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "SUNVAULT_VOLTAGE": {
                "field": "sunvault_voltage",
                "title": "{SUN_VAULT}Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "SUNVAULT_TEMPERATURE": {
                "field": "sunvault_temperature",
                "title": "{SUN_VAULT}Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "SUNVAULT_CUSTOMER_STATE_OF_CHARGE": {
                "field": "sunvault_customer_state_of_charge",
                "title": "{SUN_VAULT}Customer State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
            },
            "SUNVAULT_SYSTEM_STATE_OF_CHARGE": {
                "field": "sunvault_system_state_of_charge",
                "title": "{SUN_VAULT}System State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "SUNVAULT_POWER": {
                "field": "sunvault_power",
                "title": "{SUN_VAULT}Power",
                "unit": UnitOfPower.WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
            "SUNVAULT_POWER_INPUT": {
                "field": "sunvault_power_input",
                "title": "{SUN_VAULT}Power Input",
                "unit": UnitOfPower.WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
            "SUNVAULT_POWER_OUTPUT": {
                "field": "sunvault_power_output",
                "title": "{SUN_VAULT}Power Output",
                "unit": UnitOfPower.WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
        },
    },
    HUBPLUS_DEVICE_TYPE: {
        "unique_id": "hubplus",
        "sensors": {
            "HUBPLUS_GRID_P1_V": {
                "field": "grid_phase1_voltage",
                "title": "{SUN_POWER}HUB Plus Grid Phase 1 Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "HUBPLUS_GRID_P2_V": {
                "field": "grid_phase2_voltage",
                "title": "{SUN_POWER}HUB Plus Grid Phase 2 Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "HUBPLUS_HUMIDITY": {
                "field": "hub_humidity",
                "title": "{SUN_POWER}HUB Plus Humidity",
                "unit": PERCENTAGE,
                "icon": "mdi:water-percent",
                "device": SensorDeviceClass.HUMIDITY,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "HUBPLUS_TEMPERATURE": {
                "field": "hub_temperature",
                "title": "{SUN_POWER}HUB Plus Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "HUBPLUS_LOAD_P1_V": {
                "field": "load_phase1_voltage",
                "title": "{SUN_POWER}HUB Plus Load Phase 1 Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "HUBPLUS_LOAD_P2_V": {
                "field": "load_phase2_voltage",
                "title": "{SUN_POWER}HUB Plus Load Phase 2 Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
    BATTERY_DEVICE_TYPE: {
        "unique_id": "battery",
        "sensors": {
            "BATTERY_AMPERAGE": {
                "field": "battery_amperage",
                "title": "{SUN_VAULT}Battery {index}Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_VOLTAGE": {
                "field": "battery_voltage",
                "title": "{SUN_VAULT}Battery {index}Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_TEMPERATURE": {
                "field": "temperature",
                "title": "{SUN_VAULT}Battery {index}Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "BATTERY_CUSTOMER_STATE_OF_CHARGE": {
                "field": "customer_state_of_charge",
                "title": "{SUN_VAULT}Battery {index}Customer State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_SYSTEM_STATE_OF_CHARGE": {
                "field": "system_state_of_charge",
                "title": "{SUN_VAULT}Battery {index}System State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
    ESS_DEVICE_TYPE: {
        "unique_id": "ess",
        "sensors": {
            "ESS_HUMIDITY": {
                "field": "enclosure_humidity",
                "title": "{SUN_VAULT}ESS {index}Humidity",
                "unit": PERCENTAGE,
                "icon": "mdi:water-percent",
                "device": SensorDeviceClass.HUMIDITY,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_TEMPERATURE": {
                "field": "enclosure_temperature",
                "title": "{SUN_VAULT}ESS {index}Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_POWER": {
                "field": "agg_power",
                "title": "{SUN_VAULT}ESS {index}Power",
                "unit": UnitOfPower.KILO_WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
            },
            "ESS_METER_A_A": {
                "field": "meter_a_current",
                "title": "{SUN_VAULT}ESS {index}Meter A Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_METER_A_W": {
                "field": "meter_a_power",
                "title": "{SUN_VAULT}ESS {index}Meter A Power",
                "unit": UnitOfPower.WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_METER_A_V": {
                "field": "meter_a_voltage",
                "title": "{SUN_VAULT}ESS {index}Meter A Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_METER_B_A": {
                "field": "meter_b_current",
                "title": "{SUN_VAULT}ESS {index}Meter B Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_METER_B_W": {
                "field": "meter_b_power",
                "title": "{SUN_VAULT}ESS {index}Meter B Power",
                "unit": UnitOfPower.WATT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.POWER,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "ESS_METER_B_V": {
                "field": "meter_b_voltage",
                "title": "{SUN_VAULT}ESS {index}Meter B Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
    "Battery": {
        "unique_id": "battery_actual",
        "sensors": {
            "BATTERY_AMPERAGE": {
                "field": "battery_amperage",
                "title": "{SUN_VAULT}Battery {index}Amps",
                "unit": UnitOfElectricCurrent.AMPERE,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.CURRENT,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_VOLTAGE": {
                "field": "battery_voltage",
                "title": "{SUN_VAULT}Battery {index}Voltage",
                "unit": UnitOfElectricPotential.VOLT,
                "icon": "mdi:flash",
                "device": SensorDeviceClass.VOLTAGE,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_TEMPERATURE": {
                "field": "temperature",
                "title": "{SUN_VAULT}Battery {index}Temperature",
                "unit": UnitOfTemperature.CELSIUS,
                "icon": "mdi:thermometer",
                "device": SensorDeviceClass.TEMPERATURE,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "BATTERY_CUSTOMER_STATE_OF_CHARGE": {
                "field": "customer_state_of_charge",
                "title": "{SUN_VAULT}Battery {index}Customer State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
            },
            "BATTERY_SYSTEM_STATE_OF_CHARGE": {
                "field": "system_state_of_charge",
                "title": "{SUN_VAULT}Battery {index}System State of Charge",
                "unit": PERCENTAGE,
                "icon": "mdi:battery-charging-100",
                "device": None,
                "state": SensorStateClass.MEASUREMENT,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
        },
    },
}


# ==========================================
# EXISTING BATTERY HANDLER FUNCTIONS
# ==========================================

def convert_ess_data(ess_data, data):
    """Integrate ESS data from its unique data source into the PVS data"""
    sunvault_amperages = []
    sunvault_voltages = []
    sunvault_temperatures = []
    sunvault_customer_state_of_charges = []
    sunvault_system_state_of_charges = []
    sunvault_power = []
    sunvault_power_inputs = []
    sunvault_power_outputs = []
    sunvault_state = "working"

    for device in ess_data["ess_report"]["battery_status"]:
        battery_serial = device["serial_number"]

        # krbaker's exact approach - direct access to BATTERY_DEVICE_TYPE
        data[BATTERY_DEVICE_TYPE][battery_serial]["battery_amperage"] = device["battery_amperage"]["value"]
        data[BATTERY_DEVICE_TYPE][battery_serial]["battery_voltage"] = device["battery_voltage"]["value"]
        data[BATTERY_DEVICE_TYPE][battery_serial]["customer_state_of_charge"] = device["customer_state_of_charge"]["value"]
        data[BATTERY_DEVICE_TYPE][battery_serial]["system_state_of_charge"] = device["system_state_of_charge"]["value"]
        data[BATTERY_DEVICE_TYPE][battery_serial]["temperature"] = device["temperature"]["value"]

        if data[BATTERY_DEVICE_TYPE][battery_serial]["STATE"] != "working":
            sunvault_state = data[BATTERY_DEVICE_TYPE][battery_serial]["STATE"]

        sunvault_amperages.append(device["battery_amperage"]["value"])
        sunvault_voltages.append(device["battery_voltage"]["value"])
        sunvault_temperatures.append(device["temperature"]["value"])
        sunvault_customer_state_of_charges.append(device["customer_state_of_charge"]["value"])
        sunvault_system_state_of_charges.append(device["system_state_of_charge"]["value"])
        sunvault_power.append(sunvault_amperages[-1] * sunvault_voltages[-1])

        if sunvault_amperages[-1] < 0:
            sunvault_power_outputs.append(abs(sunvault_amperages[-1] * sunvault_voltages[-1]))
            sunvault_power_inputs.append(0)
        elif sunvault_amperages[-1] > 0:
            sunvault_power_inputs.append(sunvault_amperages[-1] * sunvault_voltages[-1])
            sunvault_power_outputs.append(0)
        else:
            sunvault_power_inputs.append(0)
            sunvault_power_outputs.append(0)

    # Process ESS status
    for device in ess_data["ess_report"]["ess_status"]:
        ess_serial = device["serial_number"]
        data[ESS_DEVICE_TYPE][ess_serial]["enclosure_humidity"] = device["enclosure_humidity"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["enclosure_temperature"] = device["enclosure_temperature"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["agg_power"] = device["ess_meter_reading"]["agg_power"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_a_current"] = device["ess_meter_reading"]["meter_a"]["reading"]["current"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_a_power"] = device["ess_meter_reading"]["meter_a"]["reading"]["power"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_a_voltage"] = device["ess_meter_reading"]["meter_a"]["reading"]["voltage"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_b_current"] = device["ess_meter_reading"]["meter_b"]["reading"]["current"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_b_power"] = device["ess_meter_reading"]["meter_b"]["reading"]["power"]["value"]
        data[ESS_DEVICE_TYPE][ess_serial]["meter_b_voltage"] = device["ess_meter_reading"]["meter_b"]["reading"]["voltage"]["value"]

    if True:
        device = ess_data["ess_report"]["hub_plus_status"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["contactor_position"] = device["contactor_position"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["grid_frequency_state"] = device["grid_frequency_state"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["grid_phase1_voltage"] = device["grid_phase1_voltage"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["grid_phase2_voltage"] = device["grid_phase2_voltage"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["grid_voltage_state"] = device["grid_voltage_state"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["hub_humidity"] = device["hub_humidity"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["hub_temperature"] = device["hub_temperature"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["inverter_connection_voltage"] = device["inverter_connection_voltage"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["load_frequency_state"] = device["load_frequency_state"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["load_phase1_voltage"] = device["load_phase1_voltage"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["load_phase2_voltage"] = device["load_phase2_voltage"]["value"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["load_voltage_state"] = device["load_voltage_state"]
        data[HUBPLUS_DEVICE_TYPE][device["serial_number"]]["main_voltage"] = device["main_voltage"]["value"]

    if True:
        # Generate a usable serial number for this virtual device, use PVS serial as base
        # since we must be talking through one and it has a serial
        pvs_serial = next(iter(data[PVS_DEVICE_TYPE]))  # only one PVS
        sunvault_serial = f"sunvault_{pvs_serial}"
        data[SUNVAULT_DEVICE_TYPE] = {sunvault_serial: {}}
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_amperage"] = sum(sunvault_amperages)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_voltage"] = sum(sunvault_voltages) / len(sunvault_voltages)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_temperature"] = sum(sunvault_temperatures) / len(sunvault_temperatures)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_customer_state_of_charge"] = sum(sunvault_customer_state_of_charges) / len(sunvault_customer_state_of_charges)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_system_state_of_charge"] = sum(sunvault_system_state_of_charges) / len(sunvault_system_state_of_charges)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_power_input"] = sum(sunvault_power_inputs)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_power_output"] = sum(sunvault_power_outputs)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["sunvault_power"] = sum(sunvault_power)
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["STATE"] = sunvault_state
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["SERIAL"] = sunvault_serial
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["SWVER"] = "1.0"
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["HWVER"] = "Virtual"
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["DESCR"] = "Virtual SunVault"
        data[SUNVAULT_DEVICE_TYPE][sunvault_serial]["MODEL"] = "Virtual SunVault"
    return data


def get_battery_configuration(entry, cache):
    """Auto-detect battery configuration from PVS data"""
    # Auto-detection from cache if available
    has_battery_from_data = False
    if hasattr(cache, 'previous_pvs_sample') and cache.previous_pvs_sample and "devices" in cache.previous_pvs_sample:
        has_battery_from_data = any(
            device.get("DEVICE_TYPE") in ("ESS", "Battery", "ESS BMS", "Energy Storage System", "SunVault")
            for device in cache.previous_pvs_sample.get("devices", [])
        )

    _LOGGER.debug("Battery auto-detection: detected=%s", has_battery_from_data)

    return has_battery_from_data, False  # Return (detected, legacy_user_setting)


def reset_battery_failure_tracking(cache):
    """Reset battery failure tracking on HA restart"""
    if not hasattr(cache, '_restart_handled'):
        _LOGGER.debug("Fresh HA start detected, resetting battery failure tracking")
        cache.battery_detection_failures = 0
        cache.battery_warning_sent = False
        cache._restart_handled = True


def handle_battery_detection_and_warnings(hass, entry, data, cache, safe_notify, user_has_battery):
    """Handle battery detection and send warnings if needed - SIMPLIFIED"""
    if not user_has_battery:
        return  # User doesn't expect batteries, skip checking
    
    # Check if we successfully got battery data when user expects it
    current_battery_detected = any(
        device.get("DEVICE_TYPE") in ("ESS", "Battery", "ESS BMS", "Energy Storage System")
        for device in data.get("devices", [])
    )
    
    if not current_battery_detected:
        cache.battery_detection_failures += 1
        _LOGGER.debug("Battery detection failure #%d", cache.battery_detection_failures)
        
        # After 3 failed attempts, send warning (bypasses notification toggle)
        if cache.battery_detection_failures >= 3 and not cache.battery_warning_sent:
            warning_msg = (
                "⚠️ SunVault Battery Detection Issue\n\n"
                f"You have 'battery system' enabled, but no battery data has been detected "
                f"after {cache.battery_detection_failures} polling attempts.\n\n"
                "Possible causes:\n"
                "• No SunVault batteries actually installed\n"
                "• Batteries not properly connected to PVS\n"
                "• Communication issue with ESS system\n\n"
                "Consider disabling 'battery system' in integration settings if you don't have batteries."
            )
            safe_notify(hass, warning_msg, "SunPower Battery Warning", entry, force_notify=True, cache=cache)
            cache.battery_warning_sent = True
            _LOGGER.warning("Battery detection failed %d times, sent user warning", cache.battery_detection_failures)
    else:
        # Reset failure tracking if we successfully detect batteries
        if cache.battery_detection_failures > 0:
            _LOGGER.info("Battery detection successful after %d previous failures", cache.battery_detection_failures)
            cache.battery_detection_failures = 0
            cache.battery_warning_sent = False


# SIMPLIFIED MAIN FUNCTIONS ONLY - REMOVED DUPLICATE FALLBACKS
# All functions now handle both battery and non-battery systems gracefully