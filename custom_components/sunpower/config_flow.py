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
            
            # Validate we have minimum device count (at least 3: PVS + 1 inverter + optional meter)
            if device_count < 3:
                _LOGGER.warning("Setup validation: Too few devices: %d", device_count)
                return False, f"Only {device_count} devices found - need at least PVS + 1 inverter (minimum 3 devices)"
            
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
        """Handle the initial connection and hardware setup."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            # Validate daytime polling interval
            daytime_interval = user_input["daytime_polling_interval"]
            nighttime_interval = user_input["nighttime_polling_interval"]

            if daytime_interval < 300:
                errors["daytime_polling_interval"] = "MIN_INTERVAL"

            # Validate nighttime polling interval (0 = disabled, or >= 300 for PVS protection)
            if nighttime_interval > 0 and nighttime_interval < 300:
                errors["nighttime_polling_interval"] = "MIN_INTERVAL"

            # Validate PVS serial last 5 chars if provided
            pvs_serial_last5 = user_input.get("pvs_serial_last5", "").strip()
            if pvs_serial_last5:
                if len(pvs_serial_last5) != 5:
                    errors["pvs_serial_last5"] = "Must be exactly 5 characters"
                elif not pvs_serial_last5.isalnum():
                    errors["pvs_serial_last5"] = "Must contain only letters and numbers"

            if not errors:
                # Test PVS connection before proceeding
                _LOGGER.info("Setup: Validating PVS connection")
                
                success, message = await self._test_pvs_connection(user_input["host"])
                
                if success:
                    # Store basic config and proceed to solar config
                    self._basic_config = user_input.copy()
                    _LOGGER.info("Setup: Connection validated, proceeding to solar configuration")
                    return await self.async_step_solar()
                else:
                    # Connection failed - show error
                    _LOGGER.warning("Setup: PVS validation failed: %s", message)
                    errors["host"] = "connection_failed"
                    description_placeholders["error_details"] = message

        # Page 1: Connection & Hardware schema
        schema = vol.Schema({
            vol.Required("host", default="172.27.153.1"): str,
            vol.Required("daytime_polling_interval", default=DEFAULT_SUNPOWER_UPDATE_INTERVAL): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=300,
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("nighttime_polling_interval", default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("route_gateway_ip", default=""): str,
            vol.Optional("pvs_serial_last5", default=""): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders
        )

    async def async_step_solar(self, user_input=None):
        """Handle solar optimization configuration."""
        errors = {}

        if user_input is not None:
            # Store solar config and proceed to notifications
            self._basic_config.update(user_input)
            return await self.async_step_notifications()

        # Page 2: Solar Optimization schema
        schema = vol.Schema({
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
            vol.Required("use_descriptive_names", default=True): selector.BooleanSelector(),
            vol.Required("use_product_names", default=False): selector.BooleanSelector(),
        })

        return self.async_show_form(
            step_id="solar",
            data_schema=schema,
            errors=errors
        )

    async def async_step_notifications(self, user_input=None):
        """Handle notifications and advanced configuration."""
        errors = {}

        if user_input is not None:
            # Combine all config and create entry
            complete_config = self._basic_config.copy()
            complete_config.update(user_input)
            
            _LOGGER.info("Setup: Creating integration with complete configuration")
            return self.async_create_entry(
                title=f"Enhanced SunPower PVS {complete_config['host']}",
                data={
                    "host": complete_config["host"],
                    "daytime_polling_interval": complete_config["daytime_polling_interval"],
                    "nighttime_polling_interval": complete_config["nighttime_polling_interval"],
                    "use_descriptive_names": complete_config["use_descriptive_names"],
                    "use_product_names": complete_config["use_product_names"],
                    "route_gateway_ip": complete_config.get("route_gateway_ip", ""),
                    "pvs_serial_last5": complete_config.get("pvs_serial_last5", ""),
                },
                options={
                    "sunrise_elevation": complete_config["sunrise_elevation"],
                    "sunset_elevation": complete_config["sunset_elevation"],
                    "general_notifications": complete_config["general_notifications"],
                    "deep_debug_notifications": complete_config["deep_debug_notifications"],
                    "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                    "mobile_device": complete_config.get("mobile_device"),
                    "flash_memory_threshold_mb": complete_config["flash_memory_threshold_mb"],
                }
            )

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Page 3: Notifications schema
        schema = vol.Schema({
            vol.Required("flash_memory_threshold_mb", default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=200,
                    unit_of_measurement="MB",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=False): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("mobile_device", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="notifications",
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
        self._basic_config = {}

    async def async_step_init(self, user_input=None):
        """Handle the connection and hardware options."""
        errors = {}

        if user_input is not None:
            daytime_interval = user_input["daytime_polling_interval"]
            nighttime_interval = user_input["nighttime_polling_interval"]

            if daytime_interval < 300:
                errors["daytime_polling_interval"] = "MIN_INTERVAL"

            # Validate nighttime polling interval (0 = disabled, or >= 300 for PVS protection)
            if nighttime_interval > 0 and nighttime_interval < 300:
                errors["nighttime_polling_interval"] = "MIN_INTERVAL"

            # Validate PVS serial last 5 chars if provided (options flow)
            pvs_serial_last5 = user_input.get("pvs_serial_last5", "").strip()
            if pvs_serial_last5:
                if len(pvs_serial_last5) != 5:
                    errors["pvs_serial_last5"] = "Must be exactly 5 characters"
                elif not pvs_serial_last5.isalnum():
                    errors["pvs_serial_last5"] = "Must contain only letters and numbers"

            if not errors:
                # Store basic config and proceed to solar step
                self._basic_config = user_input.copy()
                return await self.async_step_solar()

        # Get current values from either options or data (fallback)
        current_host = self.config_entry.options.get(
            "host", 
            self.config_entry.data.get("host", "172.27.153.1")
        )
        
        current_interval = self.config_entry.options.get(
            "daytime_polling_interval", 
            self.config_entry.data.get("daytime_polling_interval", DEFAULT_SUNPOWER_UPDATE_INTERVAL)
        )
        
        current_nighttime_interval = self.config_entry.options.get(
            "nighttime_polling_interval",
            self.config_entry.data.get("nighttime_polling_interval", 0)
        )

        current_route_gateway_ip = self.config_entry.data.get("route_gateway_ip", "")
        current_pvs_serial = self.config_entry.data.get("pvs_serial_last5", "")

        # Page 1: Connection & Hardware schema
        schema = vol.Schema({
            vol.Required("host", default=current_host): str,
            vol.Required("daytime_polling_interval", default=current_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=300,
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("nighttime_polling_interval", default=current_nighttime_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("route_gateway_ip", default=current_route_gateway_ip): str,
            vol.Optional("pvs_serial_last5", default=current_pvs_serial): str,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors
        )

    async def async_step_solar(self, user_input=None):
        """Handle solar optimization options."""
        errors = {}

        if user_input is not None:
            # Store solar config and proceed to notifications
            self._basic_config.update(user_input)
            return await self.async_step_notifications()

        # Get current sun elevation values with migration
        current_sunrise = self.config_entry.options.get("sunrise_elevation")
        current_sunset = self.config_entry.options.get("sunset_elevation")
        
        # Migration: If no sunrise/sunset values but old minimum_sun_elevation exists
        if current_sunrise is None or current_sunset is None:
            old_elevation = self.config_entry.options.get("minimum_sun_elevation", 5)
            current_sunrise = old_elevation if current_sunrise is None else current_sunrise
            current_sunset = old_elevation if current_sunset is None else current_sunset
            _LOGGER.info("Migrating from minimum_sun_elevation=%s to sunrise=%s, sunset=%s", 
                        old_elevation, current_sunrise, current_sunset)

        # Get current naming values with fallback to data
        current_descriptive = self.config_entry.data.get("use_descriptive_names", True)
        current_product = self.config_entry.data.get("use_product_names", False)

        # Page 2: Solar Optimization schema
        schema = vol.Schema({
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
            vol.Required("use_descriptive_names", default=current_descriptive): selector.BooleanSelector(),
            vol.Required("use_product_names", default=current_product): selector.BooleanSelector(),
        })

        return self.async_show_form(
            step_id="solar",
            data_schema=schema,
            errors=errors
        )

    async def async_step_notifications(self, user_input=None):
        """Handle notifications and advanced options."""
        errors = {}

        if user_input is not None:
            # Combine all config and update entry
            complete_config = self._basic_config.copy()
            complete_config.update(user_input)
            
            # Update data if basic settings changed
            data_updates = {}
            if complete_config["host"] != self.config_entry.data.get("host"):
                data_updates["host"] = complete_config["host"]
            if complete_config["nighttime_polling_interval"] != self.config_entry.data.get("nighttime_polling_interval"):
                data_updates["nighttime_polling_interval"] = complete_config["nighttime_polling_interval"]
            if complete_config["daytime_polling_interval"] != self.config_entry.data.get("daytime_polling_interval"):
                data_updates["daytime_polling_interval"] = complete_config["daytime_polling_interval"]
            if complete_config["use_descriptive_names"] != self.config_entry.data.get("use_descriptive_names"):
                data_updates["use_descriptive_names"] = complete_config["use_descriptive_names"]
            if complete_config["use_product_names"] != self.config_entry.data.get("use_product_names"):
                data_updates["use_product_names"] = complete_config["use_product_names"]
            if complete_config["route_gateway_ip"] != self.config_entry.data.get("route_gateway_ip"):
                data_updates["route_gateway_ip"] = complete_config["route_gateway_ip"]
            if complete_config.get("pvs_serial_last5", "") != self.config_entry.data.get("pvs_serial_last5", ""):
                data_updates["pvs_serial_last5"] = complete_config.get("pvs_serial_last5", "")
            
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
            
            # Create options
            options = {
                "sunrise_elevation": complete_config["sunrise_elevation"],
                "sunset_elevation": complete_config["sunset_elevation"],
                "general_notifications": complete_config["general_notifications"],
                "deep_debug_notifications": complete_config["deep_debug_notifications"],
                "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                "mobile_device": complete_config.get("mobile_device"),
                "flash_memory_threshold_mb": complete_config["flash_memory_threshold_mb"],
            }
            
            return self.async_create_entry(title="", data=options)

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Get current values
        current_general = self.config_entry.options.get("general_notifications", True)
        current_debug = self.config_entry.options.get("deep_debug_notifications", False)
        current_overwrite = self.config_entry.options.get("overwrite_general_notifications", True)
        current_mobile_device = self.config_entry.options.get("mobile_device", "none")
        current_flash_threshold = self.config_entry.options.get("flash_memory_threshold_mb", 0)

        # Page 3: Notifications schema
        schema = vol.Schema({
            vol.Required("flash_memory_threshold_mb", default=current_flash_threshold): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=200,
                    unit_of_measurement="MB",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("general_notifications", default=current_general): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=current_debug): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=current_overwrite): selector.BooleanSelector(),
            vol.Required("mobile_device", default=current_mobile_device): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="notifications",
            data_schema=schema,
            errors=errors
        )
