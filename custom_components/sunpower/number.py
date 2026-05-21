"""Number platform for SunPower integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_LIVE_DATA,
    CONF_LIVE_DATA_WRITE_INTERVAL,
    DEFAULT_LIVE_DATA_WRITE_INTERVAL,
    DOMAIN,
    MIN_SUNPOWER_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

MAX_POLLING_INTERVAL = 86400  # 1 day


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SunPower number entities."""
    sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = sunpower_state["coordinator"]
    pvs_serial = config_entry.unique_id

    entities = [SunPowerPollingIntervalNumber(coordinator, config_entry, pvs_serial)]

    if config_entry.options.get(CONF_ENABLE_LIVE_DATA, False):
        entities.append(SunPowerLiveWriteIntervalNumber(coordinator, config_entry, pvs_serial))

    async_add_entities(entities)


class SunPowerPollingIntervalNumber(CoordinatorEntity, NumberEntity):
    """Number entity to control PVS polling interval."""

    _attr_icon = "mdi:timer-sync"
    _attr_native_min_value = MIN_SUNPOWER_UPDATE_INTERVAL
    _attr_native_max_value = MAX_POLLING_INTERVAL
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Polling Interval"

    def __init__(self, coordinator, config_entry: ConfigEntry, pvs_serial: str) -> None:
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._pvs_serial = pvs_serial
        self._attr_unique_id = f"{pvs_serial}_polling_interval"

    @property
    def native_value(self) -> float:
        return float(
            self.config_entry.options.get(
                "polling_interval",
                self.config_entry.data.get("polling_interval", 300)
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        new_interval = max(MIN_SUNPOWER_UPDATE_INTERVAL, min(MAX_POLLING_INTERVAL, int(value)))
        _LOGGER.info("Polling interval changed to %d seconds for PVS %s", new_interval, self._pvs_serial)

        new_options = {**self.config_entry.options, "polling_interval": new_interval}
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

        self.coordinator.update_interval = timedelta(seconds=new_interval)

        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pvs_serial)},
        }


class SunPowerLiveWriteIntervalNumber(CoordinatorEntity, NumberEntity):
    """Number entity to control how often live data power sensors write to HA state."""

    _attr_icon = "mdi:timer-play"
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Live Data Write Interval"

    def __init__(self, coordinator, config_entry: ConfigEntry, pvs_serial: str) -> None:
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._pvs_serial = pvs_serial
        self._attr_unique_id = f"{pvs_serial}_live_write_interval"

    @property
    def native_value(self) -> float:
        return float(
            self.config_entry.options.get(
                CONF_LIVE_DATA_WRITE_INTERVAL,
                DEFAULT_LIVE_DATA_WRITE_INTERVAL,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        new_interval = max(1, min(60, int(value)))
        _LOGGER.info("Live data write interval changed to %ds for PVS %s", new_interval, self._pvs_serial)

        new_options = {**self.config_entry.options, CONF_LIVE_DATA_WRITE_INTERVAL: new_interval}
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

        # Update existing sensor instances directly so no reload is needed.
        sunpower_state = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        for sensor in sunpower_state.get("_live_data_sensors", []):
            sensor._write_interval = float(new_interval)

        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pvs_serial)},
        }
