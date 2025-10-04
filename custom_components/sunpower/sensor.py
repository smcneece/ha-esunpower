"""Support for Enhanced SunPower sensors - UPDATED IMPORTS VERSION."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import EntityCategory

from .const import (
    BATTERY_DEVICE_TYPE,
    DOMAIN,
    ESS_DEVICE_TYPE,
    HUBPLUS_DEVICE_TYPE,
    PVS_DEVICE_TYPE,
    SUNPOWER_COORDINATOR,
    SUNPOWER_DESCRIPTIVE_NAMES,
    SUNPOWER_PRODUCT_NAMES,
    SUNPOWER_SENSORS,
)
# UPDATED: Import battery constants from battery_handler.py
from .battery_handler import SUNVAULT_SENSORS
from .entity import SunPowerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Enhanced SunPower sensors - UPDATED IMPORTS VERSION."""
    sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Enhanced SunPower state: %s", sunpower_state)

    do_descriptive_names = False
    if "use_descriptive_names" in config_entry.options:
        do_descriptive_names = config_entry.options["use_descriptive_names"]
    elif SUNPOWER_DESCRIPTIVE_NAMES in config_entry.data:
        do_descriptive_names = config_entry.data[SUNPOWER_DESCRIPTIVE_NAMES]

    do_product_names = False
    if "use_product_names" in config_entry.options:
        do_product_names = config_entry.options["use_product_names"]
    elif SUNPOWER_PRODUCT_NAMES in config_entry.data:
        do_product_names = config_entry.data[SUNPOWER_PRODUCT_NAMES]

    coordinator = sunpower_state[SUNPOWER_COORDINATOR]
    sunpower_data = coordinator.data

    do_ess = False
    if sunpower_data and ESS_DEVICE_TYPE in sunpower_data:
        do_ess = True
    else:
        _LOGGER.debug("Found No ESS Data")

    if not sunpower_data or PVS_DEVICE_TYPE not in sunpower_data:
        _LOGGER.warning("Cannot find PVS Entry - coordinator may not have data yet, will retry on next update")
        # FIXED: Don't create entities now, but don't fail either - they'll be created on next coordinator update
        async_add_entities([], True)
        return
    else:
        entities = []

        pvs = next(iter(sunpower_data[PVS_DEVICE_TYPE].values()))

        # UPDATED: Combine core sensors with battery sensors when needed
        SENSORS = SUNPOWER_SENSORS
        if do_ess:
            SENSORS.update(SUNVAULT_SENSORS)

        for device_type in SENSORS:
            if device_type not in sunpower_data:
                _LOGGER.error(f"Cannot find any {device_type}")
                continue
            unique_id = SENSORS[device_type]["unique_id"]
            sensors = SENSORS[device_type]["sensors"]
            
            
            for index, sensor_data in enumerate(sunpower_data[device_type].values()):
                for sensor_name in sensors:
                    sensor = sensors[sensor_name]
                    
                    # NEW: Hybrid approach - field exists AND has value (upgrade compatible + clean interface)
                    field_name = sensor["field"]
                    if field_name not in sensor_data:
                        _LOGGER.debug("Skipping sensor %s for %s - field '%s' not in device data", 
                                    sensor_name, sensor_data.get('SERIAL', 'Unknown'), field_name)
                        continue
                    
                    # Create the sensor object to check its value
                    sensor_type = (
                        "" if not do_descriptive_names else f"{sensor_data.get('TYPE', '')} "
                    )
                    sensor_description = (
                        "" if not do_descriptive_names else f"{sensor_data.get('DESCR', '')} "
                    )
                    text_sunpower = "" if not do_product_names else "SunPower "
                    text_sunvault = "" if not do_product_names else "SunVault "
                    text_pvs = "" if not do_product_names else "PVS "
                    sensor_index = "" if not do_descriptive_names else f"{index + 1} "
                    sunpower_sensor = SunPowerSensor(
                        coordinator=coordinator,
                        my_info=sensor_data,
                        parent_info=pvs if device_type != PVS_DEVICE_TYPE else None,
                        id_code=unique_id,
                        device_type=device_type,
                        field=sensor["field"],
                        title=sensor["title"].format(
                            index=sensor_index,
                            TYPE=sensor_type,
                            DESCR=sensor_description,
                            SUN_POWER=text_sunpower,
                            SUN_VAULT=text_sunvault,
                            PVS=text_pvs,
                            SERIAL=sensor_data.get("SERIAL", "Unknown"),
                            MODEL=sensor_data.get("MODEL", "Unknown"),
                        ),
                        unit=sensor["unit"],
                        icon=sensor["icon"],
                        device_class=sensor["device"],
                        state_class=sensor["state"],
                        entity_category=sensor.get("entity_category", None),
                    )
                    
                    # HYBRID: Field exists + has value (original compatibility + our clean interface)
                    if sunpower_sensor.native_value is not None:
                        # Skip KB-based memory/flash sensors if value is "0" (new firmware - data unavailable)
                        if sensor_name in ["PVS_MEMORY_USED", "PVS_FLASH_AVAILABLE"] and sunpower_sensor.native_value == "0":
                            _LOGGER.debug("Skipping sensor %s for %s - new firmware uses percentage sensors instead",
                                        sensor_name, sensor_data.get('SERIAL', 'Unknown'))
                            continue

                        _LOGGER.debug("Creating sensor %s for %s - field '%s' has value: %s",
                                    sensor_name, sensor_data.get('SERIAL', 'Unknown'), field_name,
                                    sunpower_sensor.native_value)
                        entities.append(sunpower_sensor)
                    else:
                        _LOGGER.debug("Skipping sensor %s for %s - field '%s' has no value",
                                    sensor_name, sensor_data.get('SERIAL', 'Unknown'), field_name)

        # Create entities for each device type

    async_add_entities(entities, True)


class SunPowerSensor(SunPowerEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        my_info,
        parent_info,
        id_code,
        device_type,
        field,
        title,
        unit,
        icon,
        device_class,
        state_class,
        entity_category,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, my_info, parent_info)
        self._id_code = id_code
        self._device_type = device_type
        self._title = title
        self._field = field
        self._unit = unit
        self._icon = icon
        self._my_device_class = device_class
        self._my_state_class = state_class
        self._entity_category = entity_category

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Return device class."""
        return self._my_device_class

    @property
    def entity_category(self):
        return self._entity_category

    @property
    def state_class(self):
        """Return state class."""
        return self._my_state_class

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def name(self):
        """Device Name."""
        return self._title

    @property
    def unique_id(self):
        """Device Uniqueid.
        https://developers.home-assistant.io/docs/entity_registry_index/#unique-id
        Should not include the domain, home assistant does that for us
        base_unique_id is the serial number of the device (Inverter, PVS, Meter etc)
        "_pvs_" just as a divider - in case we start pulling data from some other source
        _field is the field within the data that this came from which is a dict so there
        is only one.
        Updating this format is a breaking change and should be called out if changed in a PR
        """
        return f"{self.base_unique_id}_pvs_{self._field}"

    @property
    def native_value(self):
        """Get the current value with bulletproof error handling"""
        # Special handling for firmware version - get it directly from device info
        if self._field == "SWVER":
            return self._my_info.get("SWVER")
        
        # Special handling for last successful poll - return the formatted string directly
        if self._field == "last_successful_poll":
            try:
                formatted_value = self.coordinator.data[self._device_type][self.base_unique_id].get(self._field, "Never")
                return formatted_value  # Already formatted as timestamp in __init__.py
            except (KeyError, TypeError, AttributeError):
                return "Never"
        
        if self._my_device_class == SensorDeviceClass.POWER_FACTOR:
            try:
                value = float(
                    self.coordinator.data[self._device_type][self.base_unique_id][self._field],
                )
                return value * 100.0
            except (ValueError, KeyError, TypeError, AttributeError):
                return None
        
        # FIXED: Safe data access with proper error handling for all scenarios
        try:
            return self.coordinator.data[self._device_type][self.base_unique_id].get(self._field, None)
        except (KeyError, TypeError, AttributeError):
            # Coordinator data might not be available yet or structure changed
            # This is normal during startup - entity will update when data arrives
            return None
