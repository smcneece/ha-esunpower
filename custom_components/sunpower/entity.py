"""The Enhanced SunPower integration base entity."""

import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PVS_DEVICE_TYPE
from .data_processor import mask_pvs_serial

_LOGGER = logging.getLogger(__name__)


class SunPowerEntity(CoordinatorEntity):
    """Base entity for Enhanced SunPower integration.

    Provides common functionality for all SunPower sensors and binary sensors,
    including device info generation and unique ID management.
    """

    def __init__(self, coordinator, my_info, parent_info):
        """Initialize the entity.

        Args:
            coordinator: DataUpdateCoordinator instance
            my_info: Device-specific information dict
            parent_info: Parent device information dict (for grouped devices)
        """
        super().__init__(coordinator)
        self._my_info = my_info
        self._parent_info = parent_info
        self.base_unique_id = self._my_info.get("SERIAL", "")

    @property
    def device_info(self):
        serial = self._my_info.get("SERIAL", "UnknownSerial")
        model = self._my_info.get("MODEL", "UnknownModel")
        # The PVS's own device record has no DESCR field, so it falls through to
        # this f"{model} {serial}" default. Its serial's last 5 characters are the
        # auth password, and this "name" is the device card title shown in
        # Settings > Devices & Services, so it must never show the raw serial.
        # Other device types (inverter, meter, ESS) always provide DESCR and never
        # reach this fallback with a sensitive value.
        display_serial = mask_pvs_serial(serial) if self._my_info.get("DEVICE_TYPE") == PVS_DEVICE_TYPE else serial
        name = self._my_info.get("DESCR", f"{model} {display_serial}")
        hw_version = self._my_info.get("HWVER", self._my_info.get("hw_version")) or None
        sw_version = self._my_info.get("SWVER") or None
        device_info = {
            "identifiers": {(DOMAIN, self.base_unique_id)},
            "name": name,
            "manufacturer": "SunPower",
            "model": model,
            "sw_version": sw_version,
            "hw_version": hw_version,
        }
        if self._parent_info is not None:
            parent_serial = self._parent_info.get("SERIAL", "UnknownParent")
            try:
                device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
                    self.coordinator.hass,
                    (DOMAIN, parent_serial),
                    config_entry_id=self.coordinator.config_entry.entry_id,
                )
            except ValueError:
                # Parent (PVS) device isn't registered yet. Shouldn't normally
                # happen since PVS entities are always processed first (PVS_DEVICE_TYPE
                # is the first key in SUNPOWER_SENSORS/SUNPOWER_BINARY_SENSORS), but
                # fall back to no via-device link rather than crashing entity setup.
                _LOGGER.debug(
                    "Could not link device to parent PVS %s (not yet registered)",
                    mask_pvs_serial(parent_serial),
                )
        return device_info