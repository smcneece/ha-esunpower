import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENABLE_LIVE_DATA,
    CONF_LIVE_DATA_THRESHOLD,
    CONF_LIVE_DATA_WRITE_INTERVAL,
    DEFAULT_LIVE_DATA_THRESHOLD,
    DEFAULT_LIVE_DATA_WRITE_INTERVAL,
    DEFAULT_SUNPOWER_UPDATE_INTERVAL,
    DOMAIN,
    MIN_SUNPOWER_UPDATE_INTERVAL,
)
from .varserver_client import VarserverClient
from .notifications import get_mobile_devices, get_email_notification_services

_LOGGER = logging.getLogger(__name__)

# Removed duplicate - using const.py values


def parse_build_number(build_raw):
    """Parse BUILD number from various firmware version formats

    Handles formats like:
    - "2025.11, Build 5412" → 5412 (PVS5 new format)
    - "61846" → 61846 (PVS6 string format)
    - 61846 → 61846 (PVS6 int format)
    - "0.0.25.5412" → 5412 (PVS5 dotted format)

    Args:
        build_raw: Raw BUILD field from supervisor/info (string or int)

    Returns:
        int: Numeric build number, or None if unparseable
    """
    if build_raw is None:
        return None

    try:
        # If already an integer, return it
        if isinstance(build_raw, int):
            return build_raw

        # Convert to string for parsing
        build_str = str(build_raw).strip()

        # Format: "2025.11, Build 5412" - extract number after "Build"
        if "Build" in build_str or "build" in build_str:
            import re
            match = re.search(r'[Bb]uild\s+(\d+)', build_str)
            if match:
                return int(match.group(1))

        # Format: "0.0.25.5412" - extract last segment
        if '.' in build_str:
            parts = build_str.split('.')
            # Try last part first (most likely to be build number)
            for part in reversed(parts):
                try:
                    build_num = int(part)
                    # Sanity check: build numbers are typically 4-5 digits
                    if build_num >= 1000:
                        return build_num
                except ValueError:
                    continue

        # Format: "61846" - plain number string
        return int(build_str)

    except (ValueError, AttributeError, TypeError) as e:
        _LOGGER.warning("Failed to parse BUILD '%s': %s", build_raw, e)
        return None


async def get_supervisor_info(host, session):
    """Auto-detect PVS serial, firmware build, and model from supervisor/info endpoint

    Returns:
        Tuple of (serial, build, last5, model, error_message)

    Note: PVS5 firmware does not include a standalone BUILD field. BUILD is embedded
    in the SWVER string (e.g. "2025.11, Build 5412"). This function falls back to
    parsing SWVER when BUILD is absent.
    """
    import aiohttp

    try:
        url = f"http://{host}/cgi-bin/dl_cgi/supervisor/info"
        timeout = aiohttp.ClientTimeout(total=30)

        async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    supervisor = data.get("supervisor", {})

                    serial = supervisor.get("SERIAL")
                    model = supervisor.get("MODEL", "")

                    # Prefer standalone BUILD field; fall back to SWVER for PVS5
                    build_raw = supervisor.get("BUILD") or supervisor.get("SWVER")

                    if serial and build_raw:
                        # Parse BUILD to handle different firmware formats including
                        # PVS5 SWVER format: "2025.11, Build 5412"
                        build = parse_build_number(build_raw)
                        if build is None:
                            _LOGGER.warning("Could not parse BUILD from '%s', will try legacy detection", build_raw)
                            return None, None, None, model, f"Unparseable BUILD format: {build_raw}"

                        last5 = (serial[-5:] if len(serial) >= 5 else serial).upper()
                        _LOGGER.info("supervisor/info: SERIAL=%s, BUILD=%s (raw: %s), MODEL=%s, Last5=%s",
                                    serial, build, build_raw, model, last5)
                        return serial, build, last5, model, None
                    else:
                        return None, None, None, model, "supervisor/info missing SERIAL or BUILD"
                else:
                    return None, None, None, "", f"supervisor/info HTTP {response.status}"

    except Exception as e:
        _LOGGER.warning("supervisor/info request failed: %s", e, exc_info=True)
        return None, None, None, "", str(e)


class SunPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Enhanced SunPower integration.

    Handles 3-step configuration:
    1. Basic setup (host, auth, polling interval)
    2. Solar configuration (naming preferences)
    3. Notifications (mobile devices, email services, flash memory monitoring)
    """
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._basic_config = {}

    async def _validate_pvs(self, host):
        """Validate PVS connection and auto-detect serial, build, and last5.

        Returns:
            Tuple of (serial, uses_pypvs, last5, build, error_message)
        """
        serial, build, last5, model, error = await get_supervisor_info(host, async_get_clientsession(self.hass, False))

        if error or build is None:
            return None, None, None, None, error or "Could not read firmware BUILD from PVS"

        _LOGGER.info("PVS detected: BUILD=%s, Serial=%s, Last5=%s, MODEL=%s", build, serial, last5, model)

        is_pvs5 = model == "PVS5"
        min_build = 5408 if is_pvs5 else 61840
        if build < min_build:
            return None, None, None, None, (
                f"Old firmware detected (BUILD {build}). This version of Enhanced SunPower "
                f"requires new firmware (BUILD {min_build}+ on {model or 'PVS6'}). "
                f"v2026.05.1 is the last version supporting old firmware. See the "
                f"Old Firmware Install Guide in the docs for pinning instructions."
            )

        try:
            client = VarserverClient(
                session=async_get_clientsession(self.hass, False),
                host=host,
                password=last5
            )
            if not await client.authenticate():
                raise RuntimeError("Authentication returned False")
            _LOGGER.info("Varserver validated successfully")
            return serial, True, last5, build, None
        except Exception as e:
            _LOGGER.error("Varserver validation failed: %s", e, exc_info=True)
            return None, None, None, None, f"Could not connect to PVS varserver: {str(e)}"

    async def async_step_user(self, user_input=None):
        """Handle initial connection setup - matches SunStrong pattern

        Step 1: Just IP and polling interval, validate PVS responds and get serial.
        Password collected in step 2 (async_step_need_password).
        """
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            # Validate IP address format
            import ipaddress
            host_input = user_input["host"].strip()
            try:
                # Handle host:port format
                host_part = host_input.split(':')[0]
                ipaddress.ip_address(host_part)
            except ValueError:
                errors["host"] = "invalid_ip"
                description_placeholders["error_details"] = f"Invalid IP address format: {host_input}"
                description_placeholders["help_text"] = "Enter a valid IP address (e.g., 172.27.153.1 or 192.168.1.73)"

            # Validate polling interval
            polling_interval = user_input["polling_interval"]

            if polling_interval < MIN_SUNPOWER_UPDATE_INTERVAL:
                errors["polling_interval"] = "MIN_INTERVAL"
            elif polling_interval > 3600:
                errors["polling_interval"] = "MAX_INTERVAL"

            if not errors:
                # Validate PVS connection with auto-detection
                serial, uses_pypvs, last5, build, error_message = await self._validate_pvs(host_input)

                if serial:
                    self.ip_address = host_input
                    self._basic_config = user_input.copy()
                    self._basic_config["host"] = host_input
                    self._basic_config["uses_pypvs"] = True
                    self._basic_config["auto_detected_last5"] = last5
                    self._basic_config["firmware_build"] = build

                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured({})
                    _LOGGER.info("Setup: Serial=%s, Build=%s, Last5=%s", serial, build, last5)

                    return await self.async_step_need_password()
                else:
                    # Connection failed - show error with user-friendly guidance
                    _LOGGER.warning("Setup: PVS validation failed: %s", error_message)
                    errors["host"] = "connection_failed"
                    description_placeholders["error_details"] = error_message

                    # Provide user-friendly troubleshooting guidance
                    if "timeout" in error_message.lower() or "timed out" in error_message.lower():
                        description_placeholders["help_text"] = (
                            "PVS not responding. Check: 1) PVS is powered on, "
                            "2) IP address is correct, 3) Network connection is working"
                        )
                    elif "auth" in error_message.lower() or "401" in error_message or "403" in error_message:
                        description_placeholders["help_text"] = (
                            "Authentication failed. This will be configured in the next step."
                        )
                    elif "connection" in error_message.lower() or "unreachable" in error_message.lower():
                        description_placeholders["help_text"] = (
                            "Cannot reach PVS. Check: 1) IP address (try 172.27.153.1 for LAN port), "
                            "2) PVS is on same network, 3) No firewall blocking connection"
                        )
                    else:
                        description_placeholders["help_text"] = (
                            "Check PVS connectivity. Common IPs: 172.27.153.1 (LAN port) or "
                            "192.168.1.x (WAN port - check router for actual IP)"
                        )

        # Page 1: Just IP and polling interval (like SunStrong)
        schema = vol.Schema({
            vol.Required("host", default=""): str,
            vol.Required("polling_interval", default=DEFAULT_SUNPOWER_UPDATE_INTERVAL): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SUNPOWER_UPDATE_INTERVAL,
                    max=3600,
                    unit_of_measurement="seconds",
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

    async def async_step_need_password(self, user_input=None):
        """Ask for PVS password - step 2 after validation

        Password is last 5 characters of PVS serial number.
        - New firmware (BUILD >= 61840): Password required for authentication
        - Old firmware (BUILD < 61840): Password collected but not used
        """
        errors = {}
        description_placeholders = {}

        auto_detected_last5 = self._basic_config.get("auto_detected_last5", "")
        firmware_build = self._basic_config.get("firmware_build")

        description_placeholders["serial_number"] = self.unique_id or "Unknown"
        description_placeholders["firmware_build"] = str(firmware_build) if firmware_build else "Unknown"
        description_placeholders["auth_required"] = "Yes"

        if user_input is not None:
            # Validate password (last 5 of serial) - force uppercase to match serial format
            pvs_serial_last5 = user_input.get("pvs_serial_last5", "").strip().upper()

            if not pvs_serial_last5:
                errors["pvs_serial_last5"] = "Password required (last 5 chars of serial)"
            elif len(pvs_serial_last5) != 5:
                errors["pvs_serial_last5"] = "Must be exactly 5 characters"
            elif not pvs_serial_last5.isalnum():
                errors["pvs_serial_last5"] = "Must contain only letters and numbers"

            if not errors:
                # Store uppercase password in basic config
                self._basic_config["pvs_serial_last5"] = pvs_serial_last5

                _LOGGER.info("Setup: Password=%s", pvs_serial_last5)
                return await self.async_step_notifications()

        # Step 2 schema: Pre-fill password with auto-detected last5
        schema = vol.Schema({
            vol.Required("pvs_serial_last5", default=auto_detected_last5 or ""): str,
        })

        return self.async_show_form(
            step_id="need_password",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders
        )

    # Solar step removed - descriptive names forced to True

    async def async_step_notifications(self, user_input=None):
        """Handle notifications and advanced configuration."""
        errors = {}

        if user_input is not None:
            # Validate email configuration
            email_service = user_input.get("email_notification_service", "none")
            email_recipient = user_input.get("email_notification_recipient", "").strip()

            if email_service != "none" and not email_recipient:
                errors["email_notification_recipient"] = "email_recipient_required"

            if not errors:
                # Clear email recipient if service is disabled
                if email_service == "none":
                    user_input["email_notification_recipient"] = ""

                # Combine all config and create entry
                complete_config = self._basic_config.copy()
                complete_config.update(user_input)
                # Force descriptive names to True (better for energy dashboard)
                complete_config["use_descriptive_names"] = True
                complete_config["use_product_names"] = False

                _LOGGER.info("Setup: Creating integration with complete configuration")
                return self.async_create_entry(
                title=f"Enhanced SunPower PVS {complete_config['host']}",
                data={
                    "host": complete_config["host"],
                    "polling_interval": complete_config["polling_interval"],
                    "use_descriptive_names": complete_config["use_descriptive_names"],
                    "use_product_names": complete_config["use_product_names"],
                    "pvs_serial_last5": complete_config.get("pvs_serial_last5", ""),
                    "uses_pypvs": complete_config.get("uses_pypvs", False),
                    "firmware_build": complete_config.get("firmware_build"),
                },
                options={
                    "general_notifications": complete_config["general_notifications"],
                    "deep_debug_notifications": complete_config["deep_debug_notifications"],
                    "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                    "mobile_device": complete_config.get("mobile_device"),
                    "flash_memory_threshold_mb": complete_config["flash_memory_threshold_mb"],
                    "flash_wear_threshold": complete_config.get("flash_wear_threshold", 90),
                    "email_notification_service": complete_config.get("email_notification_service"),
                    "email_notification_recipient": complete_config.get("email_notification_recipient", ""),
                }
            )

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Get available email notification services
        email_services = await get_email_notification_services(self.hass)
        email_options = {"none": "Disabled"}
        email_options.update(email_services)

        # Page 3: Notifications schema
        schema = vol.Schema({
            vol.Required("flash_memory_threshold_mb", default=85): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("flash_wear_threshold", default=90): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("general_notifications", default=False): selector.BooleanSelector(),
            vol.Required("deep_debug_notifications", default=False): selector.BooleanSelector(),
            vol.Required("overwrite_general_notifications", default=True): selector.BooleanSelector(),
            vol.Required("mobile_device", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in mobile_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("email_notification_service", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in email_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("email_notification_recipient", default=""): str,
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
            # Validate IP address format
            import ipaddress
            host_input = user_input["host"].strip()
            try:
                # Handle host:port format
                host_part = host_input.split(':')[0]
                ipaddress.ip_address(host_part)
                user_input["host"] = host_input  # Use cleaned host
            except ValueError:
                errors["host"] = "invalid_ip"

            polling_interval = user_input["polling_interval"]

            # Validate polling interval with appropriate minimum
            if polling_interval < MIN_SUNPOWER_UPDATE_INTERVAL:
                errors["polling_interval"] = "MIN_INTERVAL"
            elif polling_interval > 3600:
                errors["polling_interval"] = "MAX_INTERVAL"

            # Validate PVS serial last 5 chars if provided (options flow)
            pvs_serial_last5 = user_input.get("pvs_serial_last5", "").strip()
            if pvs_serial_last5:
                if len(pvs_serial_last5) != 5:
                    errors["pvs_serial_last5"] = "Must be exactly 5 characters"
                elif not pvs_serial_last5.isalnum():
                    errors["pvs_serial_last5"] = "Must contain only letters and numbers"

            if not errors:
                # Auto-detect firmware build for routing and persistence
                host = user_input["host"]
                serial, build, last5, model, error = await get_supervisor_info(host, async_get_clientsession(self.hass, False))

                if build:
                    user_input["firmware_build"] = build
                    _LOGGER.info("Options: Auto-detected firmware BUILD %s, MODEL=%s", build, model)

                    if not pvs_serial_last5:
                        errors["pvs_serial_last5"] = "Password required (last 5 chars of serial)"

            if not errors:
                self._basic_config = user_input.copy()
                firmware_build = user_input.get("firmware_build", self.config_entry.data.get("firmware_build", 0)) or 0
                if firmware_build >= 61840:
                    return await self.async_step_live_data()
                return await self.async_step_notifications()

        # Get current values from either options or data (fallback)
        current_host = self.config_entry.options.get(
            "host", 
            self.config_entry.data.get("host", "172.27.153.1")
        )
        
        current_interval = self.config_entry.options.get(
            "polling_interval",
            self.config_entry.data.get("polling_interval",
                DEFAULT_SUNPOWER_UPDATE_INTERVAL
            )
        )

        current_pvs_serial = self.config_entry.options.get("pvs_serial_last5") or self.config_entry.data.get("pvs_serial_last5", "")

        # Page 1: Connection & Hardware schema
        schema = vol.Schema({
            vol.Required("host", default=current_host): str,
            vol.Required("polling_interval", default=current_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SUNPOWER_UPDATE_INTERVAL,
                    max=3600,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
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

        # Get current naming values with fallback to data
        current_descriptive = self.config_entry.data.get("use_descriptive_names", True)
        current_product = self.config_entry.data.get("use_product_names", False)

        # Page 2: Naming Preferences schema (elevation settings removed - not used in simplified polling)
        schema = vol.Schema({
            vol.Required("use_descriptive_names", default=current_descriptive): selector.BooleanSelector(),
            vol.Required("use_product_names", default=current_product): selector.BooleanSelector(),
        })

        return self.async_show_form(
            step_id="solar",
            data_schema=schema,
            errors=errors
        )

    async def async_step_live_data(self, user_input=None):
        """Handle WebSocket live data options (new firmware only)."""
        if user_input is not None:
            self._basic_config.update(user_input)
            return await self.async_step_notifications()

        current_enable = self.config_entry.options.get(CONF_ENABLE_LIVE_DATA, False)
        current_threshold = self.config_entry.options.get(CONF_LIVE_DATA_THRESHOLD, DEFAULT_LIVE_DATA_THRESHOLD)
        current_write_interval = self.config_entry.options.get(CONF_LIVE_DATA_WRITE_INTERVAL, DEFAULT_LIVE_DATA_WRITE_INTERVAL)

        schema = vol.Schema({
            vol.Required(CONF_ENABLE_LIVE_DATA, default=current_enable): selector.BooleanSelector(),
            vol.Required(CONF_LIVE_DATA_THRESHOLD, default=current_threshold): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.01,
                    max=1.0,
                    step=0.01,
                    unit_of_measurement="kW",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_LIVE_DATA_WRITE_INTERVAL, default=current_write_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=60,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="live_data",
            data_schema=schema,
            errors={},
        )

    async def async_step_notifications(self, user_input=None):
        """Handle notifications and advanced options."""
        errors = {}

        if user_input is not None:
            # Validate email configuration
            email_service = user_input.get("email_notification_service", "none")
            email_recipient = user_input.get("email_notification_recipient", "").strip()

            if email_service != "none" and not email_recipient:
                errors["email_notification_recipient"] = "email_recipient_required"

            if not errors:
                # Clear email recipient if service is disabled
                if email_service == "none":
                    user_input["email_notification_recipient"] = ""

                # Combine all config and update entry
                complete_config = self._basic_config.copy()
                complete_config.update(user_input)
                # Force descriptive names to True (better for energy dashboard)
                complete_config["use_descriptive_names"] = True
                complete_config["use_product_names"] = False
            
            # Update data if basic settings changed
            data_updates = {}
            if complete_config["host"] != self.config_entry.data.get("host"):
                data_updates["host"] = complete_config["host"]
            if complete_config["polling_interval"] != self.config_entry.data.get("polling_interval"):
                data_updates["polling_interval"] = complete_config["polling_interval"]
            if complete_config["use_descriptive_names"] != self.config_entry.data.get("use_descriptive_names"):
                data_updates["use_descriptive_names"] = complete_config["use_descriptive_names"]
            if complete_config["use_product_names"] != self.config_entry.data.get("use_product_names"):
                data_updates["use_product_names"] = complete_config["use_product_names"]
            if complete_config.get("pvs_serial_last5", "") != self.config_entry.data.get("pvs_serial_last5", ""):
                data_updates["pvs_serial_last5"] = complete_config.get("pvs_serial_last5", "")
            # Always update firmware info if detected (critical for existing integrations)
            if "firmware_build" in complete_config:
                data_updates["firmware_build"] = complete_config["firmware_build"]
            if "uses_pypvs" in complete_config:
                data_updates["uses_pypvs"] = complete_config["uses_pypvs"]

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
                "general_notifications": complete_config["general_notifications"],
                "deep_debug_notifications": complete_config["deep_debug_notifications"],
                "overwrite_general_notifications": complete_config["overwrite_general_notifications"],
                "mobile_device": complete_config.get("mobile_device"),
                "flash_memory_threshold_mb": complete_config["flash_memory_threshold_mb"],
                "flash_wear_threshold": complete_config.get("flash_wear_threshold", 90),
                "email_notification_service": complete_config.get("email_notification_service"),
                "email_notification_recipient": complete_config.get("email_notification_recipient", ""),
                "pvs_serial_last5": complete_config.get("pvs_serial_last5", ""),
            }

            # Persist live data options (new firmware only; safe to include for old firmware too)
            options[CONF_ENABLE_LIVE_DATA] = complete_config.get(CONF_ENABLE_LIVE_DATA, False)
            options[CONF_LIVE_DATA_THRESHOLD] = complete_config.get(CONF_LIVE_DATA_THRESHOLD, DEFAULT_LIVE_DATA_THRESHOLD)
            options[CONF_LIVE_DATA_WRITE_INTERVAL] = int(complete_config.get(CONF_LIVE_DATA_WRITE_INTERVAL, DEFAULT_LIVE_DATA_WRITE_INTERVAL))

            return self.async_create_entry(title="", data=options)

        # Get available mobile devices
        mobile_devices = await get_mobile_devices(self.hass)
        mobile_options = {"none": "Disabled"}
        mobile_options.update(mobile_devices)

        # Get available email notification services
        email_services = await get_email_notification_services(self.hass)
        email_options = {"none": "Disabled"}
        email_options.update(email_services)

        # Get current values
        current_general = self.config_entry.options.get("general_notifications", False)
        current_debug = self.config_entry.options.get("deep_debug_notifications", False)
        current_overwrite = self.config_entry.options.get("overwrite_general_notifications", True)
        current_mobile_device = self.config_entry.options.get("mobile_device", "none")
        current_flash_threshold = self.config_entry.options.get("flash_memory_threshold_mb", 0)
        current_email_service = self.config_entry.options.get("email_notification_service", "none")
        current_email_recipient = self.config_entry.options.get("email_notification_recipient", "")

        # Clear recipient display if email service is disabled
        if current_email_service == "none":
            current_email_recipient = ""

        if current_flash_threshold == 0 or current_flash_threshold > 100:
            current_flash_threshold = 85

        # Page 3: Notifications schema
        schema = vol.Schema({
            vol.Required("flash_memory_threshold_mb", default=current_flash_threshold): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("flash_wear_threshold", default=self.config_entry.options.get("flash_wear_threshold", 90)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    unit_of_measurement="%",
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
            vol.Required("email_notification_service", default=current_email_service): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in email_options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("email_notification_recipient", default=current_email_recipient): str,
        })

        return self.async_show_form(
            step_id="notifications",
            data_schema=schema,
            errors=errors
        )
