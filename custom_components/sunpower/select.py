"""Select platform for SunPower battery control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Battery mode mapping: Friendly name -> API value
BATTERY_MODE_MAP = {
    "Self Supply": "SELF_CONSUMPTION",
    "Cost Savings": "ENERGY_ARBITRAGE",
    "Emergency Reserve": "EMERGENCY_RESERVE",  # TODO: Verify this value with testing
}

# Reverse mapping: API value -> Friendly name
BATTERY_MODE_REVERSE = {v: k for k, v in BATTERY_MODE_MAP.items()}

# Minimum reserve percentage options
RESERVE_PERCENTAGE_OPTIONS = [
    "10%", "20%", "30%", "40%", "50%",
    "60%", "70%", "80%", "90%", "100%"
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SunPower select entities."""
    sunpower_state = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = sunpower_state["coordinator"]

    # Check if system has battery (ESS device)
    has_battery = False
    if coordinator.data and "devices" in coordinator.data:
        for device in coordinator.data["devices"]:
            if device.get("DEVICE_TYPE") == "Energy Storage System":
                has_battery = True
                break

    # Only create battery control selects if battery system is present
    if not has_battery:
        _LOGGER.debug("No battery system detected, skipping battery control selects")
        return

    # Get PVS serial and check for new firmware
    pvs_serial = config_entry.unique_id
    pvs_object = sunpower_state.get("pvs_object")

    # Battery control only works with new firmware (pypvs)
    if not pvs_object:
        _LOGGER.warning("Battery control requires new firmware (pypvs), skipping selects")
        return

    entities = []

    # Create battery mode select
    battery_mode_select = SunPowerBatteryModeSelect(
        coordinator, config_entry, pvs_serial, pvs_object
    )
    entities.append(battery_mode_select)

    # Create minimum reserve percentage select
    reserve_percentage_select = SunPowerReservePercentageSelect(
        coordinator, config_entry, pvs_serial, pvs_object
    )
    entities.append(reserve_percentage_select)

    async_add_entities(entities)
    _LOGGER.info("Created %d battery control select(s) for PVS %s", len(entities), pvs_serial)


class SunPowerBatteryModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for SunVault battery control mode."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        pvs_serial: str,
        pvs_object
    ) -> None:
        """Initialize the battery mode select."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._pvs_serial = pvs_serial
        self._pvs_object = pvs_object
        self._attr_name = "Battery Control Mode"
        self._attr_unique_id = f"{pvs_serial}_battery_control_mode"
        self._attr_icon = "mdi:battery-sync"
        self._attr_options = list(BATTERY_MODE_MAP.keys())

    @property
    def current_option(self) -> str | None:
        """Return the current battery mode."""
        if not self.coordinator.data or "devices" not in self.coordinator.data:
            return None

        # Find ESS device and read op_mode
        for device in self.coordinator.data["devices"]:
            if device.get("DEVICE_TYPE") == "Energy Storage System":
                api_mode = device.get("op_mode", "")
                # Convert API value to friendly name
                return BATTERY_MODE_REVERSE.get(api_mode, None)

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the battery mode."""
        if option not in BATTERY_MODE_MAP:
            _LOGGER.error("Invalid battery mode option: %s", option)
            return

        api_value = BATTERY_MODE_MAP[option]
        _LOGGER.info("Setting battery mode to %s (%s)", option, api_value)

        try:
            # Use pypvs getVarserver with set parameter
            # Format: /vars?set=/ess/config/dcm/mode_param/control_mode=ENERGY_ARBITRAGE
            await self._pvs_object.getVarserver(
                "/vars",
                params={"set": f"/ess/config/dcm/mode_param/control_mode={api_value}"}
            )
            _LOGGER.info("✅ Battery mode set to %s successfully", option)

            # Refresh coordinator data to update current_option
            await self.coordinator.async_request_refresh()

        except Exception as e:
            _LOGGER.error("❌ Failed to set battery mode to %s: %s", option, e)
            raise

    @property
    def device_info(self):
        """Return device info to link this select to the existing PVS device."""
        return {
            "identifiers": {(DOMAIN, self._pvs_serial)},
        }


class SunPowerReservePercentageSelect(CoordinatorEntity, SelectEntity):
    """Select entity for SunVault minimum reserve percentage."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        pvs_serial: str,
        pvs_object
    ) -> None:
        """Initialize the reserve percentage select."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._pvs_serial = pvs_serial
        self._pvs_object = pvs_object
        self._attr_name = "Battery Reserve Percentage"
        self._attr_unique_id = f"{pvs_serial}_battery_reserve_percentage"
        self._attr_icon = "mdi:battery-lock"
        self._attr_options = RESERVE_PERCENTAGE_OPTIONS

    @property
    def current_option(self) -> str | None:
        """Return the current reserve percentage."""
        # TODO: Need to read current min_customer_soc from config endpoint
        # For now, return None (unknown)
        # The config value is at /ess/config/dcm/control_param/min_customer_soc
        # but we need to fetch it separately as it's not in the regular polling data
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the minimum reserve percentage."""
        if option not in RESERVE_PERCENTAGE_OPTIONS:
            _LOGGER.error("Invalid reserve percentage option: %s", option)
            return

        # Convert "20%" to 0.20
        percentage_value = int(option.rstrip('%')) / 100.0
        _LOGGER.info("Setting battery reserve percentage to %s (%.2f)", option, percentage_value)

        try:
            # Use pypvs getVarserver with set parameter
            # Format: /vars?set=/ess/config/dcm/control_param/min_customer_soc=0.20
            await self._pvs_object.getVarserver(
                "/vars",
                params={"set": f"/ess/config/dcm/control_param/min_customer_soc={percentage_value:.2f}"}
            )
            _LOGGER.info("✅ Battery reserve percentage set to %s successfully", option)

            # Refresh coordinator data
            await self.coordinator.async_request_refresh()

        except Exception as e:
            _LOGGER.error("❌ Failed to set battery reserve percentage to %s: %s", option, e)
            raise

    @property
    def device_info(self):
        """Return device info to link this select to the existing PVS device."""
        return {
            "identifiers": {(DOMAIN, self._pvs_serial)},
        }
