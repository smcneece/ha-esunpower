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
from .notifications import notify_inverters_discovered

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Enhanced SunPower sensors with dynamic entity discovery.
    
    Entities are created when devices are first detected, allowing setup to succeed
    even if inverters are offline (e.g., at night).
    """
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

    # Track created entities to avoid duplicates on coordinator updates
    if "_sensor_entities_created" not in sunpower_state:
        sunpower_state["_sensor_entities_created"] = set()
    created_entities = sunpower_state["_sensor_entities_created"]

    do_ess = False
    if sunpower_data and ESS_DEVICE_TYPE in sunpower_data:
        do_ess = True
    else:
        _LOGGER.debug("Found No ESS Data")

    # IMPROVED: Allow setup even without PVS data initially
    if not sunpower_data or PVS_DEVICE_TYPE not in sunpower_data:
        _LOGGER.info("PVS data not available yet - entities will be created when data arrives")
        # Set up coordinator listener to create entities when data becomes available
        async def _async_add_entities_when_ready():
            """Add entities when coordinator data becomes available."""
            if coordinator.data and PVS_DEVICE_TYPE in coordinator.data:
                await _create_entities(hass, config_entry, async_add_entities, coordinator, 
                                      do_descriptive_names, do_product_names, created_entities)
        
        # Listen for coordinator updates
        config_entry.async_on_unload(
            coordinator.async_add_listener(_async_add_entities_when_ready)
        )
        
        # Return empty list for now - entities will be added when data arrives
        async_add_entities([], True)
        return
    
    # Data is available - create entities now
    await _create_entities(hass, config_entry, async_add_entities, coordinator,
                          do_descriptive_names, do_product_names, created_entities)


async def _create_entities(hass, config_entry, async_add_entities, coordinator,
                          do_descriptive_names, do_product_names, created_entities):
    """Create sensor entities from coordinator data."""
    sunpower_data = coordinator.data
    
    if not sunpower_data or PVS_DEVICE_TYPE not in sunpower_data:
        return
    
    entities = []
    inverters_newly_discovered = False

    pvs = next(iter(sunpower_data[PVS_DEVICE_TYPE].values()))

    # Check for ESS data
    do_ess = ESS_DEVICE_TYPE in sunpower_data
    
    # UPDATED: Combine core sensors with battery sensors when needed
    SENSORS = SUNPOWER_SENSORS.copy()
    if do_ess:
        SENSORS.update(SUNVAULT_SENSORS)

    for device_type in SENSORS:
        if device_type not in sunpower_data:
            _LOGGER.debug(f"Device type {device_type} not present (expected if you don't have this equipment)")
            continue
        unique_id = SENSORS[device_type]["unique_id"]
        sensors = SENSORS[device_type]["sensors"]
        
        for index, sensor_data in enumerate(sunpower_data[device_type].values()):
            device_serial = sensor_data.get('SERIAL', 'Unknown')
            
            for sensor_name in sensors:
                sensor = sensors[sensor_name]
                
                # Generate unique entity ID for tracking
                entity_unique_id = f"{device_serial}_pvs_{sensor['field']}"
                
                # Skip if already created
                if entity_unique_id in created_entities:
                    continue
                
                # Track if this is the first inverter entity being created
                from .const import INVERTER_DEVICE_TYPE
                if device_type == INVERTER_DEVICE_TYPE and not inverters_newly_discovered:
                    inverters_newly_discovered = True
                
                # NEW: Hybrid approach - field exists AND has value (upgrade compatible + clean interface)
                field_name = sensor["field"]
                if field_name not in sensor_data:
                    _LOGGER.debug("Skipping sensor %s for %s - field '%s' not in device data", 
                                sensor_name, device_serial, field_name)
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
                        SERIAL=device_serial,
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
                                    sensor_name, device_serial)
                        continue

                    _LOGGER.debug("Creating sensor %s for %s - field '%s' has value: %s",
                                sensor_name, device_serial, field_name,
                                sunpower_sensor.native_value)
                    entities.append(sunpower_sensor)
                    created_entities.add(entity_unique_id)
                else:
                    _LOGGER.debug("Skipping sensor %s for %s - field '%s' has no value",
                                sensor_name, device_serial, field_name)

    # Add new entities if any were created
    if entities:
        _LOGGER.info("Adding %d new sensor entities", len(entities))
        async_add_entities(entities, True)
        
        # Notify user if inverters were just discovered
        if inverters_newly_discovered:
            from .const import INVERTER_DEVICE_TYPE
            inverter_count = len(sunpower_data.get(INVERTER_DEVICE_TYPE, {}))
            if inverter_count > 0:
                # Get cache from hass.data
                sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
                cache = sunpower_state.get("_cache")
                if cache:
                    notify_inverters_discovered(hass, config_entry, cache, inverter_count)
                    _LOGGER.info("Notified user: %d inverters discovered and entities created", inverter_count)


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
