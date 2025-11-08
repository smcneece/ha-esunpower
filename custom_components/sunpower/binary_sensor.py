"""Support for Enhanced SunPower binary sensors - UPDATED IMPORTS VERSION."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import (
    DOMAIN,
    ESS_DEVICE_TYPE,
    PVS_DEVICE_TYPE,
    SUNPOWER_BINARY_SENSORS,
    SUNPOWER_COORDINATOR,
    SUNPOWER_DESCRIPTIVE_NAMES,
    SUNPOWER_PRODUCT_NAMES,
)
# UPDATED: Import battery constants from battery_handler.py
from .battery_handler import SUNVAULT_BINARY_SENSORS
from .entity import SunPowerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Enhanced SunPower binary sensors with dynamic entity discovery.
    
    Entities are created when devices are first detected, allowing setup to succeed
    even if inverters are offline (e.g., at night).
    """
    sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Enhanced SunPower state: %s", sunpower_state)

    do_descriptive_names = False
    if SUNPOWER_DESCRIPTIVE_NAMES in config_entry.data:
        do_descriptive_names = config_entry.data[SUNPOWER_DESCRIPTIVE_NAMES]

    do_product_names = False
    if SUNPOWER_PRODUCT_NAMES in config_entry.data:
        do_product_names = config_entry.data[SUNPOWER_PRODUCT_NAMES]

    coordinator = sunpower_state[SUNPOWER_COORDINATOR]
    sunpower_data = coordinator.data

    # Track created entities to avoid duplicates on coordinator updates
    if "_binary_sensor_entities_created" not in sunpower_state:
        sunpower_state["_binary_sensor_entities_created"] = set()
    created_entities = sunpower_state["_binary_sensor_entities_created"]

    do_ess = False
    if sunpower_data and ESS_DEVICE_TYPE in sunpower_data:
        do_ess = True
    else:
        _LOGGER.debug("Found No ESS Data")

    # Set up coordinator listener to create entities when new devices appear
    # This handles both initial setup (no data yet) and ongoing discovery (new inverters added)
    def _add_entities_when_ready():
        """Add entities when coordinator data becomes available or changes."""
        if coordinator.data and PVS_DEVICE_TYPE in coordinator.data:
            # Schedule the async entity creation
            hass.async_create_task(
                _create_binary_entities(hass, config_entry, async_add_entities, coordinator,
                                       do_descriptive_names, do_product_names, created_entities)
            )

    # Listen for coordinator updates (for ongoing device discovery)
    config_entry.async_on_unload(
        coordinator.async_add_listener(_add_entities_when_ready)
    )

    # IMPROVED: Allow setup even without PVS data initially
    if not sunpower_data or PVS_DEVICE_TYPE not in sunpower_data:
        _LOGGER.info("PVS data not available yet - binary sensor entities will be created when data arrives")
        # Return empty list for now - entities will be added when data arrives via listener
        async_add_entities([], True)
        return

    # Data is available - create entities now (listener will handle future additions)
    await _create_binary_entities(hass, config_entry, async_add_entities, coordinator,
                                 do_descriptive_names, do_product_names, created_entities)


async def _create_binary_entities(hass, config_entry, async_add_entities, coordinator,
                                 do_descriptive_names, do_product_names, created_entities):
    """Create binary sensor entities from coordinator data."""
    sunpower_data = coordinator.data
    
    if not sunpower_data or PVS_DEVICE_TYPE not in sunpower_data:
        return
    
    entities = []

    pvs = next(iter(sunpower_data[PVS_DEVICE_TYPE].values()))

    # Check for ESS data
    do_ess = ESS_DEVICE_TYPE in sunpower_data
    
    # UPDATED: Combine core binary sensors with battery binary sensors when needed
    BINARY_SENSORS = SUNPOWER_BINARY_SENSORS.copy()
    if do_ess:
        BINARY_SENSORS.update(SUNVAULT_BINARY_SENSORS)

    for device_type in BINARY_SENSORS:
        if device_type not in sunpower_data:
            _LOGGER.debug(f"Device type {device_type} not present (expected if you don't have this equipment)")
            continue
        unique_id = BINARY_SENSORS[device_type]["unique_id"]
        sensors = BINARY_SENSORS[device_type]["sensors"]
        
        for index, sensor_data in enumerate(sunpower_data[device_type].values()):
            device_serial = sensor_data.get('SERIAL', 'Unknown')
            
            for sensor_name in sensors:
                sensor = sensors[sensor_name]
                
                # Generate unique entity ID for tracking
                entity_unique_id = f"{device_serial}_pvs_{sensor['field']}"
                
                # Skip if already created
                if entity_unique_id in created_entities:
                    continue
                
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
                sunpower_sensor = SunPowerState(
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
                    device_class=sensor["device"],
                    on_value=sensor["on_value"],
                    entity_category=sensor.get("entity_category", None),
                )
                
                _LOGGER.debug("Creating binary sensor %s for %s", sensor_name, device_serial)
                entities.append(sunpower_sensor)
                created_entities.add(entity_unique_id)

    # Add new entities if any were created
    if entities:
        _LOGGER.info("Adding %d new binary sensor entities", len(entities))
        async_add_entities(entities, True)


class SunPowerState(SunPowerEntity, BinarySensorEntity):
    """Representation of Enhanced SunPower binary sensor."""

    def __init__(
        self,
        coordinator,
        my_info,
        parent_info,
        id_code,
        device_type,
        field,
        title,
        device_class,
        on_value,
        entity_category,
    ):
        super().__init__(coordinator, my_info, parent_info)
        self._id_code = id_code
        self._device_type = device_type
        self._title = title
        self._field = field
        self._my_device_class = device_class
        self._on_value = on_value
        self._entity_category = entity_category

    @property
    def name(self):
        return self._title

    @property
    def device_class(self):
        return self._my_device_class

    @property
    def entity_category(self):
        return self._entity_category

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
    def is_on(self):
        """Return true if the binary sensor is on with bulletproof error handling."""
        try:
            value = self.coordinator.data[self._device_type][self.base_unique_id][self._field]
            if isinstance(value, str):
                return value.lower() == self._on_value.lower()
            return value == self._on_value
        except (KeyError, TypeError, AttributeError):
            # FIXED: Coordinator data might not be available yet or structure changed
            # This is normal during startup - entity will update when data arrives
            return None