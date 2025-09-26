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
    """Integrate ESS data from its unique data source into the PVS data

    FIXED: Handle mismatched serial numbers between DeviceList and ESS endpoints.
    Instead of trying to merge data into physical battery devices (which have different serials),
    we create virtual battery devices from ESS data and aggregate into SunVault.
    """
    # Safety check for ESS data structure
    if not ess_data or "ess_report" not in ess_data:
        _LOGGER.warning("Invalid ESS data structure, skipping battery processing")
        return data

    ess_report = ess_data["ess_report"]
    sunvault_amperages = []
    sunvault_voltages = []
    sunvault_temperatures = []
    sunvault_customer_state_of_charges = []
    sunvault_system_state_of_charges = []
    sunvault_power = []
    sunvault_power_inputs = []
    sunvault_power_outputs = []
    sunvault_state = "working"

    # Process battery status from ESS endpoint
    battery_status_list = ess_report.get("battery_status", [])
    _LOGGER.debug("Processing %d battery status entries from ESS endpoint", len(battery_status_list))

    for i, device in enumerate(battery_status_list):
        try:
            battery_serial = device.get("serial_number", f"unknown_battery_{i}")
            _LOGGER.debug("Processing ESS battery %d with serial: %s", i, battery_serial)

            # Create virtual battery device from ESS data instead of trying to match serials
            # This handles the mismatch between physical battery serials (M00...) and BMS serial (BC...)
            # Safe string slicing - ensure we have at least 6 chars, otherwise use full serial
            serial_suffix = battery_serial[-6:] if len(battery_serial) >= 6 else battery_serial
            virtual_battery_serial = f"ess_battery_{i}_{serial_suffix}"

            # Initialize virtual battery device
            if BATTERY_DEVICE_TYPE not in data:
                data[BATTERY_DEVICE_TYPE] = {}

            # Safely extract values with defaults
            battery_amperage = device.get("battery_amperage", {}).get("value", 0)
            battery_voltage = device.get("battery_voltage", {}).get("value", 0)
            customer_soc = device.get("customer_state_of_charge", {}).get("value", 0)
            system_soc = device.get("system_state_of_charge", {}).get("value", 0)
            temperature = device.get("temperature", {}).get("value", 0)

            data[BATTERY_DEVICE_TYPE][virtual_battery_serial] = {
                "battery_amperage": battery_amperage,
                "battery_voltage": battery_voltage,
                "customer_state_of_charge": customer_soc,
                "system_state_of_charge": system_soc,
                "temperature": temperature,
                "STATE": "working",  # ESS data doesn't provide state, assume working
                "SERIAL": virtual_battery_serial,
                "SWVER": "ESS",
                "HWVER": "ESS",
                "DESCR": f"Virtual Battery {i+1}",
                "MODEL": "ESS Battery",
                "DEVICE_TYPE": BATTERY_DEVICE_TYPE
            }

            _LOGGER.debug("Created virtual battery device: %s (A=%.1f, V=%.1f, SOC=%.1f%%)",
                         virtual_battery_serial, battery_amperage, battery_voltage, customer_soc)

            # Aggregate for SunVault virtual device using safely extracted values
            sunvault_amperages.append(battery_amperage)
            sunvault_voltages.append(battery_voltage)
            sunvault_temperatures.append(temperature)
            sunvault_customer_state_of_charges.append(customer_soc)
            sunvault_system_state_of_charges.append(system_soc)
            sunvault_power.append(battery_amperage * battery_voltage)

            if battery_amperage < 0:
                sunvault_power_outputs.append(abs(battery_amperage * battery_voltage))
                sunvault_power_inputs.append(0)
            elif battery_amperage > 0:
                sunvault_power_inputs.append(battery_amperage * battery_voltage)
                sunvault_power_outputs.append(0)
            else:
                sunvault_power_inputs.append(0)
                sunvault_power_outputs.append(0)

        except Exception as e:
            _LOGGER.error("Failed to process ESS battery %d: %s", i, e)
            continue  # Skip this battery but continue with others

    # Process ESS status - handle potential serial mismatches
    ess_status_list = ess_report.get("ess_status", [])
    _LOGGER.debug("Processing %d ESS status entries from ESS endpoint", len(ess_status_list))

    for i, device in enumerate(ess_status_list):
        try:
            ess_serial = device.get("serial_number", f"unknown_ess_{i}")
            _LOGGER.debug("Processing ESS device %d with serial: %s", i, ess_serial)

            # Try to find matching ESS device in DeviceList data, but create virtual if not found
            if ESS_DEVICE_TYPE in data and ess_serial in data[ESS_DEVICE_TYPE]:
                # Direct match found, use existing device
                target_device = data[ESS_DEVICE_TYPE][ess_serial]
            else:
                # No match or no ESS devices, create virtual ESS device
                # Safe string slicing - ensure we have at least 8 chars, otherwise use full serial
                serial_suffix = ess_serial[-8:] if len(ess_serial) >= 8 else ess_serial
                virtual_ess_serial = f"ess_virtual_{i}_{serial_suffix}"
                _LOGGER.debug("Creating virtual ESS device: %s (original: %s)", virtual_ess_serial, ess_serial)

                if ESS_DEVICE_TYPE not in data:
                    data[ESS_DEVICE_TYPE] = {}

                data[ESS_DEVICE_TYPE][virtual_ess_serial] = {
                    "STATE": "working",
                    "SERIAL": virtual_ess_serial,
                    "SWVER": "ESS",
                    "HWVER": "ESS",
                    "DESCR": f"Virtual ESS {i+1}",
                    "MODEL": "ESS Device",
                    "DEVICE_TYPE": ESS_DEVICE_TYPE
                }
                target_device = data[ESS_DEVICE_TYPE][virtual_ess_serial]

            # Safely populate ESS data with defaults
            target_device["enclosure_humidity"] = device.get("enclosure_humidity", {}).get("value", 0)
            target_device["enclosure_temperature"] = device.get("enclosure_temperature", {}).get("value", 0)

            # Handle nested ess_meter_reading structure safely
            meter_reading = device.get("ess_meter_reading", {})
            target_device["agg_power"] = meter_reading.get("agg_power", {}).get("value", 0)

            meter_a = meter_reading.get("meter_a", {}).get("reading", {})
            target_device["meter_a_current"] = meter_a.get("current", {}).get("value", 0)
            target_device["meter_a_power"] = meter_a.get("power", {}).get("value", 0)
            target_device["meter_a_voltage"] = meter_a.get("voltage", {}).get("value", 0)

            meter_b = meter_reading.get("meter_b", {}).get("reading", {})
            target_device["meter_b_current"] = meter_b.get("current", {}).get("value", 0)
            target_device["meter_b_power"] = meter_b.get("power", {}).get("value", 0)
            target_device["meter_b_voltage"] = meter_b.get("voltage", {}).get("value", 0)

            _LOGGER.debug("Processed ESS device: %s (Power: %.3f kW)",
                         target_device.get("SERIAL", "unknown"), target_device["agg_power"])

        except Exception as e:
            _LOGGER.error("Failed to process ESS device %d: %s", i, e)
            continue  # Skip this ESS device but continue with others

    # Process HubPlus status - handle potential serial mismatches
    if "hub_plus_status" in ess_report:
        try:
            device = ess_report["hub_plus_status"]
            hubplus_serial = device.get("serial_number", "unknown_hubplus")
            _LOGGER.debug("Processing HubPlus device with serial: %s", hubplus_serial)

            # Try to find matching HubPlus device in DeviceList data, but create virtual if not found
            if HUBPLUS_DEVICE_TYPE in data and hubplus_serial in data[HUBPLUS_DEVICE_TYPE]:
                # Direct match found, use existing device
                target_device = data[HUBPLUS_DEVICE_TYPE][hubplus_serial]
            else:
                # No match or no HubPlus devices, create virtual HubPlus device
                # Safe string slicing - ensure we have at least 8 chars, otherwise use full serial
                serial_suffix = hubplus_serial[-8:] if len(hubplus_serial) >= 8 else hubplus_serial
                virtual_hubplus_serial = f"hubplus_virtual_{serial_suffix}"
                _LOGGER.debug("Creating virtual HubPlus device: %s (original: %s)", virtual_hubplus_serial, hubplus_serial)

                if HUBPLUS_DEVICE_TYPE not in data:
                    data[HUBPLUS_DEVICE_TYPE] = {}

                data[HUBPLUS_DEVICE_TYPE][virtual_hubplus_serial] = {
                    "STATE": "working",
                    "SERIAL": virtual_hubplus_serial,
                    "SWVER": "ESS",
                    "HWVER": "ESS",
                    "DESCR": "Virtual Hub Plus",
                    "MODEL": "Hub Plus Device",
                    "DEVICE_TYPE": HUBPLUS_DEVICE_TYPE
                }
                target_device = data[HUBPLUS_DEVICE_TYPE][virtual_hubplus_serial]

            # Safely populate HubPlus data with defaults
            target_device["contactor_position"] = device.get("contactor_position", "UNKNOWN")
            target_device["grid_frequency_state"] = device.get("grid_frequency_state", "UNKNOWN")
            target_device["grid_phase1_voltage"] = device.get("grid_phase1_voltage", {}).get("value", 0)
            target_device["grid_phase2_voltage"] = device.get("grid_phase2_voltage", {}).get("value", 0)
            target_device["grid_voltage_state"] = device.get("grid_voltage_state", "UNKNOWN")
            target_device["hub_humidity"] = device.get("hub_humidity", {}).get("value", 0)
            target_device["hub_temperature"] = device.get("hub_temperature", {}).get("value", 0)
            target_device["inverter_connection_voltage"] = device.get("inverter_connection_voltage", {}).get("value", 0)
            target_device["load_frequency_state"] = device.get("load_frequency_state", "UNKNOWN")
            target_device["load_phase1_voltage"] = device.get("load_phase1_voltage", {}).get("value", 0)
            target_device["load_phase2_voltage"] = device.get("load_phase2_voltage", {}).get("value", 0)
            target_device["load_voltage_state"] = device.get("load_voltage_state", "UNKNOWN")
            target_device["main_voltage"] = device.get("main_voltage", {}).get("value", 0)

            _LOGGER.debug("Processed HubPlus device: %s (Grid V1: %.1f, V2: %.1f)",
                         target_device.get("SERIAL", "unknown"),
                         target_device["grid_phase1_voltage"], target_device["grid_phase2_voltage"])

        except Exception as e:
            _LOGGER.error("Failed to process HubPlus device: %s", e)

    # Create SunVault aggregation device only if we have battery data
    if sunvault_amperages:  # Only create if we have battery data
        # Generate a usable serial number for this virtual device, use PVS serial as base
        # since we must be talking through one and it has a serial
        pvs_serial = next(iter(data[PVS_DEVICE_TYPE]))  # only one PVS
        sunvault_serial = f"sunvault_{pvs_serial}"

        if SUNVAULT_DEVICE_TYPE not in data:
            data[SUNVAULT_DEVICE_TYPE] = {}

        data[SUNVAULT_DEVICE_TYPE][sunvault_serial] = {
            "sunvault_amperage": sum(sunvault_amperages),
            "sunvault_voltage": sum(sunvault_voltages) / len(sunvault_voltages) if sunvault_voltages else 0,
            "sunvault_temperature": sum(sunvault_temperatures) / len(sunvault_temperatures) if sunvault_temperatures else 0,
            "sunvault_customer_state_of_charge": sum(sunvault_customer_state_of_charges) / len(sunvault_customer_state_of_charges) if sunvault_customer_state_of_charges else 0,
            "sunvault_system_state_of_charge": sum(sunvault_system_state_of_charges) / len(sunvault_system_state_of_charges) if sunvault_system_state_of_charges else 0,
            "sunvault_power_input": sum(sunvault_power_inputs),
            "sunvault_power_output": sum(sunvault_power_outputs),
            "sunvault_power": sum(sunvault_power),
            "STATE": sunvault_state,
            "SERIAL": sunvault_serial,
            "SWVER": "1.0",
            "HWVER": "Virtual",
            "DESCR": "Virtual SunVault",
            "MODEL": "Virtual SunVault",
            "DEVICE_TYPE": SUNVAULT_DEVICE_TYPE
        }
        _LOGGER.debug("Created SunVault aggregation device: %s with %d batteries", sunvault_serial, len(sunvault_amperages))
    else:
        _LOGGER.debug("No battery data found, skipping SunVault aggregation device creation")
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