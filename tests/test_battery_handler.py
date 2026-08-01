"""Tests for battery_handler.py sensor definitions."""
from homeassistant.components.sensor import SensorDeviceClass
from custom_components.sunpower.battery_handler import SUNVAULT_SENSORS

SOC_FIELDS = {
    "sunvault_customer_state_of_charge",
    "sunvault_system_state_of_charge",
    "customer_state_of_charge",
    "system_state_of_charge",
    "soc_val",
    "customer_soc_val",
    "soh_val",
}


def test_soc_sensors_have_battery_device_class():
    """All SOC/SOH sensors must have SensorDeviceClass.BATTERY set.

    Regression test: these were previously missing device_class, causing
    them to be excluded from the HA Energy Dashboard SOC sensor picker.
    """
    for device_type, device_def in SUNVAULT_SENSORS.items():
        for sensor_name, sensor_def in device_def.get("sensors", {}).items():
            if sensor_def.get("field") in SOC_FIELDS:
                assert sensor_def["device"] == SensorDeviceClass.BATTERY, (
                    f"Sensor {sensor_name} (field={sensor_def['field']}) "
                    f"must have SensorDeviceClass.BATTERY but has {sensor_def['device']}"
                )
