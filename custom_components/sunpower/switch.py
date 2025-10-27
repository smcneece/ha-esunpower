"""Switch platform for SunPower integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SunPower switch entities."""
    sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = sunpower_state["coordinator"]

    # Get PVS serial from config
    pvs_serial = config_entry.unique_id

    # Create polling control switch
    polling_switch = SunPowerPollingSwitch(coordinator, config_entry, pvs_serial)

    async_add_entities([polling_switch])

    _LOGGER.info("Created polling control switch for PVS %s", pvs_serial)


class SunPowerPollingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable PVS polling."""

    def __init__(self, coordinator, config_entry: ConfigEntry, pvs_serial: str) -> None:
        """Initialize the polling switch."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._pvs_serial = pvs_serial
        self._attr_name = "Polling Enabled"
        self._attr_unique_id = f"{pvs_serial}_polling_enabled"
        self._attr_icon = "mdi:sync"

    @property
    def is_on(self) -> bool:
        """Return true if polling is enabled."""
        # Check config_entry options for polling_enabled flag (default True)
        return self.config_entry.options.get("polling_enabled", True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable PVS polling."""
        _LOGGER.info("Enabling PVS polling for %s", self._pvs_serial)

        # Update config entry options
        new_options = {**self.config_entry.options, "polling_enabled": True}
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )

        # Send notification
        from .notifications import notify_polling_enabled
        await notify_polling_enabled(self.hass, self.config_entry, self._pvs_serial)

        # Update coordinator diagnostic data
        if hasattr(self.coordinator, 'async_refresh'):
            await self.coordinator.async_refresh()

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable PVS polling."""
        _LOGGER.info("Disabling PVS polling for %s", self._pvs_serial)

        # Update config entry options
        new_options = {**self.config_entry.options, "polling_enabled": False}
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )

        # Send notification
        from .notifications import notify_polling_disabled
        await notify_polling_disabled(self.hass, self.config_entry, self._pvs_serial)

        # Update coordinator diagnostic data
        if hasattr(self.coordinator, 'async_refresh'):
            await self.coordinator.async_refresh()

        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info to link this switch to the existing PVS device."""
        # Link to existing PVS device using its serial as identifier
        return {
            "identifiers": {(DOMAIN, self._pvs_serial)},
        }
