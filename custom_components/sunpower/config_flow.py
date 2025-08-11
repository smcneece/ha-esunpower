import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN
from .sunpower import SunPowerMonitor, ConnectionException, ParseException
from .notifications import get_mobile_devices

_LOGGER = logging.getLogger(__name__)

# Default to 300 seconds for PVS safety
DEFAULT_SUNPOWER_UPDATE_INTERVAL = 300

class SunPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._basic_config = {}

    async def _test_pvs_connection(self, host):
        """Test PVS connection and validate real device data during setup"""
        try:
            _LOGGER.info("Setup validation: Testing PVS connection to %s", host)
            
            # Create monitor and test connection
            monitor = SunPowerMonitor(host)
            
            # Test with reasonable timeout for setup
            try:
                device_data = await asyncio.wait_for(
                    monitor.device_list_async(),
                    timeout=30.0  # 30 second timeout for setup
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Setup validation: PVS connection timeout after 30 seconds")
                return False, "Connection timeout - PVS did not respond within 30 seconds"
            
            # Validate response structure
            if not device_data:
                _LOGGER.warning("Setup validation: PVS returned empty data")
                return False, "PVS returned empty response"
            
            if not isinstance(device_data, dict):
                _LOGGER.warning("Setup validation: PVS returned invalid data type: %s", type(device_data))
                return False, f"PVS returned invalid data type: {type(device_data)}"
            
            if "devices" not in device_data:
                _LOGGER.warning("Setup validation: PVS response missing 'devices' key")
                return False, "PVS response missing device data"
            
            devices = device_data.get("devices", [])
            if not devices:
                _LOGGER.warning("Setup validation: PVS returned no devices")
                return False, "PVS returned no devices"
            
            device_count = len(devices)
            _LOGGER.info("Setup validation: PVS returned %d devices", device_count)
            
            # Validate we have reasonable device count (at least 10 for a real solar system)
            if device_count < 10:
                _LOGGER.warning("Setup validation: Suspiciously low device count: %d", device_count)
                return False, f"Only {device_count} devices found - expected at least 10 for a solar system"
            
            # Validate we have required device types
            device_types = [device.get("DEVICE_TYPE") for device in devices]
            has_pvs = any(dt == "PVS" for dt in device_types)
            has_inverters = any(dt == "Inverter" for dt in device_types)
            
            if not has_pvs:
                _LOGGER.warning("Setup validation: No PVS device found in response")
                return False, "No PVS supervisor device found"
            
            if not has_inverters:
                _LOGGER.warning("Setup validation: No inverter devices found in response")
                return False, "No solar inverters found"
            
            # Count device types for user feedback
            inverter_count = sum(1 for dt in device_types if dt == "Inverter")
            meter_count = sum(1 for dt in device_types if dt == "Power Meter")
            
            _LOGGER.info("Setup validation: SUCCESS - Found %d inverters, %d meters, 1 PVS", 
                        inverter_count, meter_count)
            
            return True, f"Connection successful! Found {inverter_count} inverters, {meter_count} meters, and PVS supervisor"
            
        except (ConnectionException, ParseException) as e:
            _LOGGER.warning("Setup validation: PVS connection failed: %s", e)
            return False, f"Cannot connect to PVS: {str(e)}"
        except Exception as e:
            _LOGGER.error("Setup validation: Unexpected error: %s", e)
            return False, f"Setup validation failed: {str(e)}"

    async def async_step_user(self, user_input=None):
        """Handle the basic configuration step with sun elevation moved here."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            # Validate polling interval
            polling_interval = user_input["polling_interval_seconds"]
            if polling_interval < 300:
                errors["polling_interval_seconds"] = "MIN_INTERVAL"
            else:
                # Test PVS connection before proceeding
                _LOGGER.info("Setup: Validating PVS connection before proceeding")
                
                success, message = await self._test_pvs_connection(user_input["host"])
                
                if success:
                    # Store basic config and proceed to advanced step
                    self._basic_config = user_input.copy()
                    _LOGGER.info("Setup: Basic configuration validated, proceeding to advanced settings")
                    return await self.async_step_advanced()
                else:
                    # Connection failed - show error and allow retry
                    _LOGGER.warning("Setup: PVS validation failed: %s", message)
                    errors["host"] = "connection_failed"
                    description_placeholders["error_details"] = message

        # Basic configuration schema with sun elevation included
        schema = vol.Schema({
            vol.Required("host", default="172.27.153.1"): str,
            vol.Required("polling_interval_seconds", default=DEFAULT_SUNPOWER_UPDATE_INTERVAL): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=300,  # Minimum 300 seconds for PVS safety
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("has_battery_system", default=False): selector.BooleanSelector(),
            vol.Required("sunrise_elevation", default=5): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=45,
                    unit_of_measurement="degrees",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("sunset_elevation", default=5): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=45,
                    unit_of_measurement="degrees",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders
        )

    async def async_step_advanced(self, user_input=None):
        """Handle the advanced configuration step - now less crowded."""
        errors = {}

        if user_input is not None:
            # Combine basic and advanced config
            complete_config = self._basic_config.copy()
            complete_config.update(user_input)
            
            _LOGGER.info("Setup: Creating integration with complete configuration")
            return self.async_create_entry(
                title=f"Enhanced SunPower PVS {complete_config['host']}",
                data={
                    "host": complete_config["host"],
                    "polling_interval_seconds": complete_config["polling_interval_seconds"],
                    "has_battery_system": complete_config["has_battery_system"],
                },
                options={
                    "sunrise_elevation": complete_config["sunrise_elevation"],
                    "sunset_elevation": complete_config["sunset_elevation"],
                    "general_notifications": complete_config["general_notifications"],
                    "deep_debug_notifications": complete_config["deep_debug_notifications"],
                    "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                    "mobile_notifications": complete_config["mobile_notifications"],
                    "mobile_device": complete_config.get("mobile_device"),
                    "route_check_enabled": complete_config["route_check_enabled"],
                    "route_gateway_ip": complete_config.get("route_gateway_ip", "192.168.1.80"),
                }
            )

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Advanced configuration schema - cleaner without sun elevation
        schema = vol.Schema({
            vol.Required("general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=False): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("mobile_notifications", default=False): selector.BooleanSelector(),
            vol.Optional("mobile_device", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("route_check_enabled", default=False): selector.BooleanSelector(),
            vol.Required("route_gateway_ip", default="192.168.1.80"): selector.TextSelector(),
        })

        return self.async_show_form(
            step_id="advanced",
            data_schema=schema,
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SunPowerOptionsFlowHandler(config_entry)


class SunPowerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        # FIXED: Remove explicit config_entry assignment (deprecated in HA 2025.12)
        # self.config_entry is automatically available in OptionsFlow
        self._basic_config = {}

    async def async_step_init(self, user_input=None):
        """Handle the basic options step with sun elevation moved here."""
        errors = {}

        if user_input is not None:
            polling_interval = user_input["polling_interval_seconds"]
            if polling_interval < 300:
                errors["polling_interval_seconds"] = "MIN_INTERVAL"
            else:
                # Store basic config and proceed to advanced step
                self._basic_config = user_input.copy()
                return await self.async_step_advanced()

        # Get current values from either options or data (fallback)
        current_host = self.config_entry.options.get(
            "host", 
            self.config_entry.data.get("host", "172.27.153.1")
        )
        
        current_interval = self.config_entry.options.get(
            "polling_interval_seconds", 
            self.config_entry.data.get("polling_interval_seconds", DEFAULT_SUNPOWER_UPDATE_INTERVAL)
        )
        
        current_battery = self.config_entry.options.get(
            "has_battery_system",
            self.config_entry.data.get("has_battery_system", False)
        )

        # Get current sun elevation values with migration from old single elevation
        current_sunrise = self.config_entry.options.get("sunrise_elevation")
        current_sunset = self.config_entry.options.get("sunset_elevation")
        
        # Migration: If no sunrise/sunset values but old minimum_sun_elevation exists
        if current_sunrise is None or current_sunset is None:
            old_elevation = self.config_entry.options.get("minimum_sun_elevation", 5)
            current_sunrise = old_elevation if current_sunrise is None else current_sunrise
            current_sunset = old_elevation if current_sunset is None else current_sunset
            _LOGGER.info("Migrating from minimum_sun_elevation=%s to sunrise=%s, sunset=%s", 
                        old_elevation, current_sunrise, current_sunset)

        # Basic options schema with sun elevation included
        schema = vol.Schema({
            vol.Required("host", default=current_host): str,
            vol.Required("polling_interval_seconds", default=current_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=300,  # Minimum 300 seconds for PVS safety
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("has_battery_system", default=current_battery): selector.BooleanSelector(),
            vol.Required("sunrise_elevation", default=current_sunrise): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=45,
                    unit_of_measurement="degrees",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("sunset_elevation", default=current_sunset): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=45,
                    unit_of_measurement="degrees",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors
        )

    async def async_step_advanced(self, user_input=None):
        """Handle the advanced options step - cleaner without sun elevation."""
        errors = {}

        if user_input is not None:
            # Combine basic and advanced config
            complete_config = self._basic_config.copy()
            complete_config.update(user_input)
            
            # Update data if basic settings changed
            data_updates = {}
            if complete_config["host"] != self.config_entry.data.get("host"):
                data_updates["host"] = complete_config["host"]
            if complete_config["has_battery_system"] != self.config_entry.data.get("has_battery_system"):
                data_updates["has_battery_system"] = complete_config["has_battery_system"]
            if complete_config["polling_interval_seconds"] != self.config_entry.data.get("polling_interval_seconds"):
                data_updates["polling_interval_seconds"] = complete_config["polling_interval_seconds"]
            
            # Apply data updates if needed
            if data_updates:
                new_data = dict(self.config_entry.data)
                new_data.update(data_updates)
                
                title = f"Enhanced SunPower PVS {new_data['host']}" if "host" in data_updates else None
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, 
                    data=new_data,
                    title=title
                )
            
            # Create options with sunrise/sunset elevation from basic config
            options = {
                "sunrise_elevation": complete_config["sunrise_elevation"],
                "sunset_elevation": complete_config["sunset_elevation"],
                "general_notifications": complete_config["general_notifications"],
                "deep_debug_notifications": complete_config["deep_debug_notifications"],
                "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                "mobile_notifications": complete_config["mobile_notifications"],
                "mobile_device": complete_config.get("mobile_device"),
                "route_check_enabled": complete_config["route_check_enabled"],
                "route_gateway_ip": complete_config.get("route_gateway_ip", "192.168.1.80"),
            }
            
            return self.async_create_entry(title="", data=options)

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Get current advanced values
        current_general = self.config_entry.options.get("general_notifications", True)
        current_debug = self.config_entry.options.get("deep_debug_notifications", False)
        current_overwrite = self.config_entry.options.get("overwrite_general_notifications", True)
        current_mobile_enabled = self.config_entry.options.get("mobile_notifications", False)
        current_mobile_device = self.config_entry.options.get("mobile_device", "none")
        current_route_check = self.config_entry.options.get("route_check_enabled", False)
        current_gateway_ip = self.config_entry.options.get("route_gateway_ip", "192.168.1.80")

        # Advanced options schema - cleaner without sun elevation
        schema = vol.Schema({
            vol.Required("general_notifications", default=current_general): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=current_debug): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=current_overwrite): selector.BooleanSelector(),
            vol.Required("mobile_notifications", default=current_mobile_enabled): selector.BooleanSelector(),
            vol.Optional("mobile_device", default=current_mobile_device): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("route_check_enabled", default=current_route_check): selector.BooleanSelector(),
            vol.Required("route_gateway_ip", default=current_gateway_ip): str,
        })

        return self.async_show_form(
            step_id="advanced",
            data_schema=schema,
            errors=errors
        )