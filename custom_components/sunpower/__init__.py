"""The Enhanced SunPower integration with Simplified 24/7 Polling"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from pypvs.pvs import PVS
from pypvs.exceptions import PVSError

# Suppress pypvs library auth retry warnings (harmless - pypvs handles retries internally)
logging.getLogger("pypvs.pvs_fcgi").setLevel(logging.ERROR)

from .const import (
    BATTERY_DEVICE_TYPE,
    DIAGNOSTIC_DEVICE_TYPE,
    DOMAIN,
    ESS_DEVICE_TYPE,
    HUBPLUS_DEVICE_TYPE,
    INVERTER_DEVICE_TYPE,
    MIN_SUNPOWER_UPDATE_INTERVAL,
    MIN_SUNVAULT_UPDATE_INTERVAL,
    PVS_DEVICE_TYPE,
    SUNPOWER_COORDINATOR,
    SUNPOWER_HOST,
    SUNPOWER_OBJECT,
)
from .sunpower import (
    ConnectionException,
    ParseException,
    SunPowerMonitor,
)

# Import data processing functions
from .data_processor import (
    convert_sunpower_data,
    validate_converted_data,
    get_device_summary,
)

# Import health check functions
from .health_check import (
    check_firmware_upgrade,
    check_flash_memory_level,
    check_flash_wear_level,
    check_inverter_health,
    reset_inverter_health_tracking,
    smart_pvs_health_check,
    update_diagnostic_stats,
)

# Import battery handler functions
from .battery_handler import (
    convert_ess_data,
    get_battery_configuration,
)

# Import notification functions
from .notifications import (
    format_time_duration,
    notify_data_update_success,
    notify_diagnostic_coordinator_started,
    notify_diagnostic_coordinator_status,
    notify_firmware_upgrade,
    notify_polling_failed,
    notify_setup_success,
    notify_setup_warning,
    notify_using_cached_data,
    safe_notify,
)

from .pypvs_converter import convert_pypvs_to_legacy

_LOGGER = logging.getLogger(__name__)

# Dependency diagnostic logging - check installations (one-time on load)
try:
    import pypvs
    import aiohttp
    import simplejson
    _LOGGER.info("Dependencies loaded: pypvs=%s, aiohttp=%s, simplejson=%s",
                 getattr(pypvs, '__version__', 'unknown'),
                 aiohttp.__version__,
                 simplejson.__version__)
except ImportError as e:
    _LOGGER.error("❌ Dependency import failed: %s", e)
except Exception as e:
    _LOGGER.error("❌ Dependency check error: %s", e)


CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor", "binary_sensor", "switch"]

# Default to 300 seconds (5 minutes) for PVS safety
DEFAULT_POLLING_INTERVAL = 300



def get_cache_filename(host):
    """Get consistent cache filename based on PVS host address
    
    Args:
        host: PVS host address (e.g., '172.27.153.1' or '10.222.1.245:9090')
    
    Returns:
        Cache filename string (e.g., 'sunpower_cache_172_27_153_1.json' or 'sunpower_cache_10_222_1_245_9090.json')
    """
    # Replace dots and colons with underscores to create valid filename for all OS
    clean_host = host.replace(".", "_").replace(":", "_")
    return f"sunpower_cache_{clean_host}.json"


class SunPowerDataCache:
    """Enhanced cache with inverter health monitoring and diagnostics support"""
    def __init__(self):
        # Basic cache attributes
        self.previous_pvs_sample_time = 0
        self.previous_pvs_sample = {}
        self.previous_ess_sample_time = 0
        self.previous_ess_sample = {}
        
        # Startup notification throttling
        self.startup_time = time.time()
        self.startup_notifications_sent = {}  # Dict to track alert times, not a set
        
        # PVS health check tracking
        self.pvs_health_failures = 0
        self.last_health_check = 0
        self.health_backoff_until = 0
        
        # Inverter health monitoring
        self.inverter_health_initialized = False
        self.expected_inverters = set()
        self.inverter_failure_counts = {}

        # Battery detection (persistent once detected)
        self.battery_detected_once = False
        
        # Firmware tracking
        self.last_known_firmware = None
        self.firmware_tracking_initialized = False
        
        # Diagnostic tracking
        self.diagnostic_stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'consecutive_failures': 0,
            'last_success_time': 0,
            'response_times': [],
            'integration_start_time': time.time(),
        }
        
        # Authentication session tracking for pypvs
        self.last_auth_time = 0
        self.auth_refresh_interval = 3600  # Re-auth every hour proactively

        # Authentication session tracking for pypvs
        self.last_auth_time = 0
        self.auth_refresh_interval = 3600  # Re-auth every hour proactively


def create_diagnostic_device_data(cache, inverter_data, meter_data=None, polling_interval=None, polling_enabled=True):
    """Create diagnostic device data for sensors"""

    # Initialize stats if not present
    if not hasattr(cache, 'diagnostic_stats'):
        cache.diagnostic_stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'average_response_time': 0.0,
            'last_success_time': 0,
            'last_failure_time': 0,
            'uptime_start': time.time()
        }

    stats = cache.diagnostic_stats

    # Calculate success rate
    if stats['total_polls'] > 0:
        success_rate = (stats['successful_polls'] / stats['total_polls']) * 100
    else:
        success_rate = 0

    # Use average response time from stats
    avg_response = stats.get('average_response_time', 0.0)

    # Count active inverters
    active_inverters = len(inverter_data) if inverter_data else 0

    # Last successful poll formatting - use timestamp with date
    last_success_time = stats.get('last_success_time', 0)
    if last_success_time > 0:
        last_poll_dt = datetime.fromtimestamp(last_success_time)
        last_poll_str = last_poll_dt.strftime("%H:%M %m-%d-%y")
        last_poll_seconds = last_success_time
    else:
        last_poll_str = "Never"
        last_poll_seconds = None

    # Determine polling status
    polling_status = "Enabled" if polling_enabled else "Disabled"

    # Create diagnostic device
    diagnostic_serial = "sunpower_diagnostics"
    diagnostic_device = {
        "SERIAL": diagnostic_serial,
        "MODEL": "Enhanced SunPower Diagnostics",
        "DESCR": "Enhanced SunPower Integration Diagnostics",
        "DEVICE_TYPE": DIAGNOSTIC_DEVICE_TYPE,
        "STATE": "working",
        "SWVER": "2025.8.12",
        "HWVER": "Virtual",
        "polling_interval_seconds": int(polling_interval) if polling_interval else 300,
        "poll_success_rate": round(success_rate, 1),
        "total_polls": stats.get('total_polls', 0),
        "consecutive_failures": stats.get('consecutive_failures', 0),
        "last_successful_poll": last_poll_str,
        "average_response_time": round(avg_response, 2),
        "active_inverters": active_inverters,
        "polling_status": polling_status,
    }

    return diagnostic_serial, diagnostic_device


async def save_cache_file(hass: HomeAssistant, host: str, pvs_data: dict):
    """Save PVS data to cache file with consistent naming based on host IP"""
    try:
        # Use HA storage directory for cache file
        storage_path = hass.config.path(".storage")
        cache_filename = get_cache_filename(host)
        cache_file = os.path.join(storage_path, cache_filename)
        
        # Validate data before saving
        if not pvs_data or not isinstance(pvs_data, dict) or "devices" not in pvs_data:
            _LOGGER.warning("Invalid PVS data, not saving to cache")
            return False
        
        def write_cache_file():
            with open(cache_file, 'w') as f:
                json.dump(pvs_data, f, indent=2)
            return True
        
        await hass.async_add_executor_job(write_cache_file)
        
        device_count = len(pvs_data.get("devices", []))
        _LOGGER.info("Saved PVS data to cache: %s (%d devices)", cache_filename, device_count)
        return True
        
    except Exception as e:
        _LOGGER.error("Failed to save cache file: %s", e)
        return False


async def load_cache_file(hass: HomeAssistant, host: str):
    """Load PVS data from cache file with consistent naming based on host IP"""
    try:
        # Use HA storage directory for cache file
        storage_path = hass.config.path(".storage")
        cache_filename = get_cache_filename(host)
        cache_file = os.path.join(storage_path, cache_filename)
        
        def check_and_load_cache():
            if not os.path.exists(cache_file):
                return None, 0, False
            
            # Get cache age from file timestamp
            cache_age = time.time() - os.path.getmtime(cache_file)
            
            # Load raw PVS JSON
            with open(cache_file, 'r') as f:
                pvs_data = json.load(f)
            
            return pvs_data, cache_age, True
        
        pvs_data, cache_age, file_exists = await hass.async_add_executor_job(check_and_load_cache)
        
        if not file_exists:
            _LOGGER.info("No cache file found: %s", cache_filename)
            return None, 0
        
        # Validate cached data
        if not pvs_data or not isinstance(pvs_data, dict) or "devices" not in pvs_data:
            _LOGGER.warning("Invalid cached data, removing cache file")
            await hass.async_add_executor_job(lambda: os.remove(cache_file))
            return None, 0
        
        device_count = len(pvs_data.get("devices", []))
        _LOGGER.info("Loaded cached PVS data: %s (%d devices, %.0fs old)", cache_filename, device_count, cache_age)
        return pvs_data, cache_age
        
    except Exception as e:
        _LOGGER.error("Failed to load cache file: %s", e)
        return None, 0


async def poll_pvs_with_safety(sunpower_monitor, polling_interval, cache, hass, entry):
    """Poll PVS with safety protocols and diagnostic tracking"""

    start_time = time.time()

    # Smart PVS health check - but with better HTTP testing
    try:
        health_timeout = min(30.0, polling_interval // 4)
        health_status = await asyncio.wait_for(
            smart_pvs_health_check(sunpower_monitor.host, cache, hass, entry, 2, 1),
            timeout=health_timeout
        )
    except asyncio.TimeoutError:
        _LOGGER.warning("Health check timed out after %ds, PVS considered offline", health_timeout)
        health_status = 'unreachable'
        update_diagnostic_stats(cache, False)
        return None

    # If PVS unhealthy, don't attempt poll
    if health_status != 'healthy':
        if health_status == 'backoff':
            remaining = int(cache.health_backoff_until - time.time())
            _LOGGER.info("PVS in backoff period, %ds remaining", remaining)
        else:
            _LOGGER.warning("PVS health check failed, skipping poll")
        update_diagnostic_stats(cache, False)
        return None

    # PVS is healthy, proceed with polling
    _LOGGER.info("PVS health check passed, proceeding with poll")
    
    try:
        # Poll PVS with adaptive timeout
        pvs_timeout = min(90.0, polling_interval - 10)
        sunpower_data = await asyncio.wait_for(
            sunpower_monitor.device_list_async(),
            timeout=pvs_timeout
        )
        
        elapsed_time = time.time() - start_time
        _LOGGER.info("PVS polling completed in %.2f seconds", elapsed_time)
        
        # Validate response
        if not sunpower_data or not isinstance(sunpower_data, dict) or "devices" not in sunpower_data:
            update_diagnostic_stats(cache, False, elapsed_time)
            raise UpdateFailed("PVS returned invalid data")
        
        device_count = len(sunpower_data.get("devices", []))
        if device_count == 0:
            update_diagnostic_stats(cache, False, elapsed_time)
            raise UpdateFailed("PVS returned no devices")
        

        # Success!
        update_diagnostic_stats(cache, True, elapsed_time)
        _LOGGER.info("PVS returned %d devices - poll successful", device_count)
        return sunpower_data
        
    except (ParseException, ConnectionException) as error:
        elapsed_time = time.time() - start_time
        update_diagnostic_stats(cache, False, elapsed_time)
        _LOGGER.error("PVS poll failed: %s", error)
        raise UpdateFailed(f"PVS poll failed: {error}") from error
    except Exception as error:
        elapsed_time = time.time() - start_time
        update_diagnostic_stats(cache, False, elapsed_time)
        _LOGGER.error("Unexpected PVS poll error: %s", error)
        raise UpdateFailed(f"Unexpected PVS poll error: {error}") from error


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Enhanced SunPower component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=conf,
        ),
    )
    return True


async def migrate_from_krbaker_if_needed(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate config from krbaker's original integration format only"""
    old_data = entry.data
    old_options = entry.options

    # Only migrate krbaker-specific fields, not our own legacy formats
    krbaker_fields = ["polling_interval_seconds", "has_battery_system"]
    needs_migration = any(field in old_data or field in old_options for field in krbaker_fields)

    if not needs_migration:
        return

    _LOGGER.info("Migrating from krbaker integration format...")

    # Migrate data section
    new_data = dict(old_data)
    if "polling_interval_seconds" in old_data:
        new_data["polling_interval"] = max(300, old_data["polling_interval_seconds"])
        del new_data["polling_interval_seconds"]
        _LOGGER.info("Migrated polling_interval_seconds to polling_interval")

    if "has_battery_system" in old_data:
        del new_data["has_battery_system"]  # We auto-detect now
        _LOGGER.info("Removed has_battery_system - using auto-detection")

    # Migrate options section
    new_options = dict(old_options)
    if "polling_interval_seconds" in old_options:
        new_options["polling_interval"] = max(300, old_options["polling_interval_seconds"])
        del new_options["polling_interval_seconds"]

    if "has_battery_system" in old_options:
        del new_options["has_battery_system"]

    # Ensure required fields exist
    if "polling_interval" not in new_data:
        new_data["polling_interval"] = DEFAULT_POLLING_INTERVAL

    # Apply migration
    hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)
    _LOGGER.info("✅ krbaker migration completed successfully")



async def _handle_polling_error(hass, entry, cache, host_ip, error):
    """Handle PVS polling errors with specific authentication vs general error handling.

    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        cache: Integration cache object
        host_ip: PVS IP address
        error: Exception that occurred during polling

    Sends appropriate notifications based on error type (auth vs network).
    """

    # Check for authentication-specific failures
    error_str = str(error).lower()
    if any(auth_error in error_str for auth_error in [
        "authentication failed", "check pvs serial", "authentication required",
        "session authentication failed", "initial authentication failed"
    ]):
        # Critical authentication failure
        auth_msg = (
            f"🔒 CRITICAL: Enhanced SunPower Authentication Failed!\n\n"
            f"The new firmware requires authentication but login failed.\n\n"
            f"✅ Check: PVS Serial Number (last 5 digits) in integration settings\n"
            f"🔄 Error: {str(error)}\n\n"
            f"Go to Settings → Devices & Services → Enhanced SunPower → Configure\n"
            f"to verify your PVS serial number is correct."
        )
        safe_notify(hass, auth_msg, "Enhanced SunPower Authentication", entry,
                   force_notify=True, notification_category="health", cache=cache)
    else:
        # Standard polling failure
        polling_url = f"http://{host_ip}/cgi-bin/dl_cgi?Command=DeviceList"
        notify_polling_failed(hass, entry, cache, polling_url, error)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Enhanced SunPower from a config entry"""
    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP ===")
    entry_id = entry.entry_id

    hass.data[DOMAIN].setdefault(entry_id, {})

    # Create enhanced cache with diagnostics - REMOVED CALLBACK SETUP
    cache = SunPowerDataCache()

    # Migrate from krbaker format if needed
    await migrate_from_krbaker_if_needed(hass, entry)

    # Check if we should use pypvs (new firmware) or legacy dl_cgi (old firmware)
    uses_pypvs = entry.data.get("uses_pypvs", False)
    firmware_build = entry.data.get("firmware_build")

    # FIRMWARE UPGRADE MIGRATION: Detect if PVS firmware was upgraded to 61840+
    if not uses_pypvs:
        _LOGGER.info("Checking if PVS firmware was upgraded...")
        try:
            # Query supervisor/info for current BUILD
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{entry.data['host']}/cgi-bin/dl_cgi/supervisor/info", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        supervisor = await resp.json()
                        current_build = supervisor.get("BUILD")
                        current_serial = supervisor.get("SERIAL")

                        MIN_LOCALAPI_BUILD = 61840
                        if current_build and current_build >= MIN_LOCALAPI_BUILD:
                            _LOGGER.warning("⚠️ FIRMWARE UPGRADE DETECTED: BUILD %s requires pypvs but config has uses_pypvs=False", current_build)
                            _LOGGER.info("Migrating to new firmware mode...")

                            # Extract last5 from serial for authentication
                            last5 = (current_serial[-5:] if current_serial and len(current_serial) >= 5 else "").upper()

                            # Update config entry
                            new_data = dict(entry.data)
                            new_data["uses_pypvs"] = True
                            new_data["firmware_build"] = current_build
                            if not new_data.get("pvs_serial_last5"):
                                new_data["pvs_serial_last5"] = last5
                                _LOGGER.info("Auto-detected serial last5: %s", last5)

                            hass.config_entries.async_update_entry(entry, data=new_data)

                            # Update local variables
                            uses_pypvs = True
                            firmware_build = current_build

                            _LOGGER.info("✅ Migration complete: Now using pypvs with BUILD %s", current_build)
        except Exception as e:
            _LOGGER.debug("Firmware upgrade check failed (not critical): %s", e)

    # Set polling URL based on firmware method
    if uses_pypvs:
        polling_url = f"http://{entry.data['host']}/vars (pypvs LocalAPI)"
    else:
        polling_url = f"http://{entry.data['host']}/cgi-bin/dl_cgi?Command=DeviceList"

    # Get authentication details - ONLY use password for new firmware (BUILD >= 61840)
    # Check both entry.data (initial setup) and entry.options (reconfigure) for serial
    pvs_serial_last5 = entry.options.get("pvs_serial_last5") or entry.data.get("pvs_serial_last5", "")
    pvs_serial_last5 = pvs_serial_last5.strip() if pvs_serial_last5 else ""
    auth_password = pvs_serial_last5 if (pvs_serial_last5 and uses_pypvs) else None

    if uses_pypvs:
        _LOGGER.info("🔒 Using pypvs library for new firmware (BUILD %s) WITH authentication", firmware_build)
        _LOGGER.info("Auth details: host=%s, user=ssm_owner, password=%s*** (length=%d)",
                     entry.data['host'], auth_password[:2] if auth_password else "NONE",
                     len(auth_password) if auth_password else 0)

        # Create PVS object with password for new firmware
        try:
            pvs_object = PVS(
                session=async_get_clientsession(hass, False),
                host=entry.data['host'],
                user="ssm_owner",
                password=auth_password
            )
            _LOGGER.info("✅ pypvs object created successfully (version %s)", getattr(pypvs, '__version__', 'unknown'))

            # Set serial number from config flow validation (skip discovery)
            # Discovery makes multiple rapid requests that can timeout
            pvs_serial = entry.unique_id
            _LOGGER.info("Using serial from config: %s (skipping discovery)", pvs_serial)
            pvs_object._serial_number = pvs_serial  # Set directly instead of discovering

            # Initialize pypvs - authenticate only (serial already set)
            _LOGGER.info("Initializing pypvs authentication...")
            await pvs_object.setup(auth_password=auth_password)
            cache.last_auth_time = time.time()  # Track initial auth time
            _LOGGER.info("✅ pypvs initialized and authenticated successfully (serial: %s)", pvs_object.serial_number)
        except Exception as e:
            _LOGGER.warning("⚠️ Failed to initialize pypvs during setup (PVS may be temporarily offline): %s", e)
            _LOGGER.info("Integration will continue setup - coordinator will retry authentication during first poll")
            cache.last_auth_time = 0  # Mark as needing authentication
            # Don't raise - let coordinator handle retry gracefully
        sunpower_monitor = None  # Not used when using pypvs
    else:
        _LOGGER.info("🔓 Using legacy dl_cgi for old firmware (BUILD %s) WITHOUT authentication", firmware_build)
        pvs_object = None  # Not used when using legacy method
        sunpower_monitor = SunPowerMonitor(
            entry.data['host'],
            auth_password=None,  # Old firmware does NOT use authentication
            pvs_serial=entry.unique_id
        )

    # Simple polling interval - adjustments happen in config flow after battery detection
    polling_interval = entry.options.get("polling_interval", entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL))

    _LOGGER.info("Creating coordinator with interval=%ds", polling_interval)

    async def async_update_data():
        """Simplified data fetching - single polling interval, always active"""
        from .data_processor import convert_sunpower_data, validate_converted_data

        notify_diagnostic_coordinator_started(hass, entry, cache)

        # Track poll start time for diagnostic stats
        poll_start_time = time.time()
        cache.diagnostic_stats['total_polls'] += 1

        # Check if polling is enabled via switch
        polling_enabled = entry.options.get("polling_enabled", True)
        if not polling_enabled:
            _LOGGER.info("Polling disabled by user switch - returning cached data without PVS poll")
            # Load cached data and return it without polling PVS
            host_ip = entry.data['host']
            cached_data, cache_age = await load_cache_file(hass, host_ip)
            if cached_data and isinstance(cached_data, dict) and "devices" in cached_data:
                # Convert raw cached data to device dictionary format
                data = convert_sunpower_data(cached_data)

                # Validate converted data
                is_valid, device_count, error_message = validate_converted_data(data)
                if not is_valid:
                    _LOGGER.warning("Cached data validation failed: %s", error_message)
                    raise UpdateFailed(f"Invalid cached data: {error_message}")

                # Add diagnostic device to converted data before returning
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                meter_data = data.get('Power Meter', {})
                current_polling_interval = entry.options.get("polling_interval", entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL))
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data, current_polling_interval, polling_enabled)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}

                # No notification here - switch already notified when toggled off
                return data
            else:
                _LOGGER.warning("Polling disabled but no cached data available - cannot return data")
                raise UpdateFailed("Polling disabled and no cached data available")

        # Get host IP for cache operations
        host_ip = entry.data['host']

        # Get battery configuration from auto-detection (simplified - no polling overrides)
        has_battery, user_has_battery = get_battery_configuration(entry, cache)

        # Re-read polling interval from entry (might have changed via reconfigure)
        current_polling_interval = entry.options.get("polling_interval", entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL))

        # Update coordinator interval if needed
        new_interval = timedelta(seconds=current_polling_interval)
        if coordinator.update_interval != new_interval:
            coordinator.update_interval = new_interval
            _LOGGER.info("Updated polling interval to %d seconds", current_polling_interval)

        # Notify status - simplified polling
        notify_diagnostic_coordinator_status(hass, entry, cache, current_polling_interval,
                                           current_polling_interval, "simplified_polling")

        # Check cache tolerance (simplified - no complex interval calculations)
        cached_data, cache_age = await load_cache_file(hass, host_ip)
        poll_tolerance = 30  # Simple 30-second tolerance

        if cached_data and cache_age < (current_polling_interval - poll_tolerance):
            remaining_time = current_polling_interval - cache_age
            _LOGGER.info("Using cached data (age: %d seconds, interval: %d seconds, remaining: %d seconds)",
                        cache_age, current_polling_interval, remaining_time)

            # Return cached data
            data = convert_sunpower_data(cached_data)
            is_valid, device_count, error_message = validate_converted_data(data)
            if is_valid:
                # Get device data for diagnostic creation
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})

                # Run health checks on cached data too
                try:
                    pvs_data = data.get(PVS_DEVICE_TYPE, {})
                    if pvs_data and inverter_data:
                        check_firmware_upgrade(hass, entry, cache, pvs_data)
                        check_flash_memory_level(hass, entry, cache, pvs_data)
                        check_flash_wear_level(hass, entry, cache, pvs_data)
                        check_inverter_health(hass, entry, cache, inverter_data)
                except Exception as e:
                    _LOGGER.error("Health checks failed on cached data: %s", e, exc_info=True)

                # Track cached data return as success (coordinator returned data successfully)
                cache.diagnostic_stats['successful_polls'] += 1
                cache.diagnostic_stats['consecutive_failures'] = 0

                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data, current_polling_interval, polling_enabled)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}

                notify_using_cached_data(hass, entry, cache, "polling_interval_not_elapsed", cache_age, current_polling_interval)
                return data

        # Always poll PVS - simplified single interval
        fresh_data = None

        # Step 1: Poll PVS for fresh data
        try:
            if pvs_object:
                # New firmware: Use pypvs library
                # Proactive session refresh if auth is old (prevents session expiration)
                time_since_auth = time.time() - cache.last_auth_time
                if auth_password and time_since_auth > cache.auth_refresh_interval:
                    _LOGGER.info("Proactive session refresh (last auth: %.0f seconds ago)", time_since_auth)
                    try:
                        await pvs_object.setup(auth_password=auth_password)
                        cache.last_auth_time = time.time()
                        _LOGGER.info("✅ Proactive re-authentication successful")
                    except Exception as refresh_error:
                        _LOGGER.warning("Proactive re-auth failed (will retry on error): %s", refresh_error)
                        # Don't fail the poll, just log and continue

                _LOGGER.debug("Polling PVS using pypvs (new firmware)")
                pvs_data = await pvs_object.update()
                # Query flash wear percentage (not in pypvs PVSGateway model yet)
                flashwear_pct = 0
                try:
                    flashwear_hex = await pvs_object.getVarserverVar('/sys/pvs/flashwear_type_b')
                    # Convert hex to percentage: 0x01 = 10%, 0x09 = 90%
                    if flashwear_hex:
                        if isinstance(flashwear_hex, str) and flashwear_hex.startswith('0x'):
                            flashwear_pct = int(flashwear_hex, 16) * 10
                        else:
                            flashwear_pct = int(flashwear_hex) * 10
                        _LOGGER.debug('Flash wear: %d%%', flashwear_pct)
                except Exception as e:
                    _LOGGER.debug('Could not fetch flashwear_type_b: %s', e)
                # Convert pypvs PVSData object to legacy dl_cgi format
                # Pass PVS serial from pvs_object for virtual device creation
                fresh_data = convert_pypvs_to_legacy(pvs_data, pvs_serial=pvs_object.serial_number, flashwear_percent=flashwear_pct)
            else:
                # Old firmware: Use legacy dl_cgi
                _LOGGER.debug("Polling PVS using dl_cgi (old firmware)")
                fresh_data = await poll_pvs_with_safety(sunpower_monitor, current_polling_interval, cache, hass, entry)
            # Note: fresh_data can be None if PVS is unhealthy/backoff - this is normal, use cache
        except Exception as e:
            # Check if this is an authentication error and attempt automatic re-auth
            # Note: pypvs updaters may throw various exception types, not just PVSError
            error_str = str(e).lower()
            is_auth_error = any(keyword in error_str for keyword in [
                '401', '403', 'auth', 'unauthorized', 'forbidden',
                'login to the pvs failed', 'login failed', 'authentication failed'
            ])

            if is_auth_error and pvs_object and auth_password:
                _LOGGER.warning("⚠️ Authentication error detected during polling: %s", e)
                _LOGGER.info("Attempting automatic re-authentication (re-setup)...")
                try:
                    # Re-initialize pypvs session - setup only (serial already set)
                    await pvs_object.setup(auth_password=auth_password)
                    cache.last_auth_time = time.time()  # Update auth timestamp
                    _LOGGER.info("✅ Re-authentication successful (serial: %s), retrying poll...", pvs_object.serial_number)

                    # Retry the poll after successful re-auth
                    pvs_data = await pvs_object.update()

                    # Re-fetch flash wear data
                    flashwear_pct = 0
                    try:
                        flashwear_hex = await pvs_object.getVarserverVar('/sys/pvs/flashwear_type_b')
                        if flashwear_hex:
                            if isinstance(flashwear_hex, str) and flashwear_hex.startswith('0x'):
                                flashwear_pct = int(flashwear_hex, 16) * 10
                            else:
                                flashwear_pct = int(flashwear_hex) * 10
                    except Exception as e:
                        _LOGGER.debug("Could not fetch flash wear data (optional): %s", e)
                        pass  # Flash wear is optional

                    fresh_data = convert_pypvs_to_legacy(pvs_data, pvs_serial=pvs_object.serial_number, flashwear_percent=flashwear_pct)
                    _LOGGER.info("✅ Poll retry after re-auth successful")

                except Exception as retry_error:
                    _LOGGER.error("❌ Re-authentication or poll retry failed: %s", retry_error)
                    cache.diagnostic_stats['failed_polls'] += 1
                    cache.diagnostic_stats['consecutive_failures'] += 1
                    fresh_data = None

                    # Send critical notification for persistent auth failures
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "🔐 PVS Authentication Failure",
                            "message": f"Automatic re-authentication failed: {retry_error}<br><br>Check PVS password configuration (last 5 of serial).",
                            "notification_id": f"sunpower_auth_failure_{entry.entry_id}"
                        }
                    )
            else:
                # Non-auth error or can't retry - just log and fail
                if not auth_password:
                    _LOGGER.error("pypvs polling error (no auth configured): %s", e)
                    _LOGGER.error("This may be an authentication error but no PVS serial is configured")
                else:
                    _LOGGER.error("pypvs polling error (non-auth): %s", e)
                cache.diagnostic_stats['failed_polls'] += 1
                cache.diagnostic_stats['consecutive_failures'] += 1
                fresh_data = None

                # For legacy method, send additional error notifications
                if not pvs_object:
                    await _handle_polling_error(hass, entry, cache, host_ip, e)

        # Step 2: Save cache if we got fresh data - preserve missing devices
        if fresh_data:
            try:
                # Merge cached inverters/meters before saving to preserve night-time data
                data_to_save = dict(fresh_data)  # Copy fresh data
                if cached_data:
                    fresh_device_types = {dev.get('DEVICE_TYPE') for dev in fresh_data.get('devices', [])}
                    fresh_serials = {dev.get('SERIAL') for dev in fresh_data.get('devices', [])}
                    cached_devices = cached_data.get('devices', [])
                    
                    # Preserve inverters if missing (night-time)
                    if 'Inverter' not in fresh_device_types:
                        cached_inverters = [dev for dev in cached_devices 
                                           if dev.get('DEVICE_TYPE') == 'Inverter']
                        if cached_inverters:
                            data_to_save['devices'] = fresh_data['devices'] + cached_inverters
                            _LOGGER.debug("Preserving %d inverters in cache (offline)", len(cached_inverters))
                
                cache_success = await save_cache_file(hass, host_ip, data_to_save)
                if cache_success:
                    cache.previous_pvs_sample = data_to_save
                    cache.previous_pvs_sample_time = time.time()
            except Exception as e:
                _LOGGER.warning("Cache save failed: %s", e)
                # Continue - cache failure isn't critical

        # Step 3: Convert and validate data
        if fresh_data:
            try:
                # Merge cached device data at RAW JSON level BEFORE conversion
                # This ensures virtual meter creation has all device data available
                if cached_data:
                    try:
                        # Get existing serials to avoid duplicates
                        fresh_serials = {dev.get('SERIAL') for dev in fresh_data.get('devices', [])}
                        fresh_device_types = {dev.get('DEVICE_TYPE') for dev in fresh_data.get('devices', [])}
                        cached_devices = cached_data.get('devices', [])
                        
                        # Preserve inverters if missing from fresh data (night-time)
                        if 'Inverter' not in fresh_device_types:
                            cached_inverters = [dev for dev in cached_devices 
                                               if dev.get('DEVICE_TYPE') == 'Inverter' 
                                               and dev.get('SERIAL') not in fresh_serials]
                            if cached_inverters:
                                fresh_data['devices'].extend(cached_inverters)
                                _LOGGER.debug("Restored %d inverters from cache (offline at night)", len(cached_inverters))
                        
                        # Preserve power meters if missing
                        if 'Power Meter' not in fresh_device_types:
                            cached_meters = [dev for dev in cached_devices 
                                            if dev.get('DEVICE_TYPE') == 'Power Meter' 
                                            and dev.get('SERIAL') not in fresh_serials]
                            if cached_meters:
                                fresh_data['devices'].extend(cached_meters)
                                _LOGGER.debug("Restored %d power meters from cache", len(cached_meters))
                    except Exception as merge_error:
                        _LOGGER.debug("Cache merge failed: %s", merge_error)
                        # Continue without cached data
                
                # NOW convert with complete device list (fresh + cached)
                data = convert_sunpower_data(fresh_data)
                is_valid, device_count, error_message = validate_converted_data(data)

                if not is_valid:
                    _LOGGER.error("Data validation failed: %s", error_message)
                    raise UpdateFailed(f"Data conversion failed: {error_message}")
            except Exception as e:
                _LOGGER.error("Data conversion failed: %s", e)
                fresh_data = None  # Fall back to cache

        # Step 4: Process fresh data if we have it
        if fresh_data:
            # Re-check battery detection from FRESH data (fixes first-poll detection)
            # This ensures ESS polling happens on first poll if batteries are present
            fresh_has_battery = any(
                device.get("DEVICE_TYPE") in ("ESS", "Battery", "ESS BMS", "Energy Storage System", "SunVault")
                for device in fresh_data.get("devices", [])
            )
            if fresh_has_battery and not has_battery:
                _LOGGER.info("Battery system detected in fresh poll data - enabling ESS polling")
                has_battery = True
                # Persist the detection
                cache.battery_detected_once = True

            # Battery processing (if detected from cache OR fresh data)
            if has_battery:
                try:
                    _LOGGER.debug("Polling ESS endpoint for battery data")
                    old_battery_count = len(data.get(BATTERY_DEVICE_TYPE, {}))
                    ess_data = await sunpower_monitor.energy_storage_system_status_async()

                    if ess_data:
                        _LOGGER.debug("ESS endpoint returned data - converting to battery entities")
                        data = convert_ess_data(ess_data, data)
                        new_battery_count = len(data.get(BATTERY_DEVICE_TYPE, {}))

                        # Only log entity count at INFO when it changes
                        if new_battery_count != old_battery_count:
                            if new_battery_count == 0:
                                _LOGGER.warning("ESS data processed but no battery entities created (was %d)", old_battery_count)
                            else:
                                _LOGGER.info("Battery entity count changed: %d → %d", old_battery_count, new_battery_count)
                        else:
                            _LOGGER.debug("ESS polling successful - %d battery entities", new_battery_count)
                    else:
                        _LOGGER.warning("ESS endpoint returned no data - battery entities may become unavailable")

                except Exception as convert_error:
                    _LOGGER.error("ESS data conversion failed: %s", convert_error, exc_info=True)
                    # Don't re-raise - continue with PVS data

            # Step 5: Health checks
            try:
                pvs_data = data.get(PVS_DEVICE_TYPE, {})
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                if pvs_data and inverter_data:
                    check_firmware_upgrade(hass, entry, cache, pvs_data)
                    check_flash_memory_level(hass, entry, cache, pvs_data)
                    check_flash_wear_level(hass, entry, cache, pvs_data)
                    check_inverter_health(hass, entry, cache, inverter_data)
            except Exception as e:
                _LOGGER.error("Health checks failed on fresh data: %s", e, exc_info=True)

            # Step 6: Track successful poll with response time (BEFORE creating diagnostic device)
            response_time = time.time() - poll_start_time
            cache.diagnostic_stats['successful_polls'] += 1
            cache.diagnostic_stats['consecutive_failures'] = 0
            cache.diagnostic_stats['last_success_time'] = time.time()
            cache.diagnostic_stats['response_times'].append(response_time)

            # Keep only last 100 response times for average calculation
            if len(cache.diagnostic_stats['response_times']) > 100:
                cache.diagnostic_stats['response_times'] = cache.diagnostic_stats['response_times'][-100:]

            # Calculate average response time
            if cache.diagnostic_stats['response_times']:
                cache.diagnostic_stats['average_response_time'] = sum(cache.diagnostic_stats['response_times']) / len(cache.diagnostic_stats['response_times'])

            # Step 7: Create diagnostic device (AFTER updating stats so it shows current poll)
            try:
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data, current_polling_interval, polling_enabled)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
            except Exception as e:
                _LOGGER.warning("Diagnostic device creation failed: %s", e)
                # Continue - diagnostic failure shouldn't stop data processing

            # Success notification
            notify_data_update_success(hass, entry, cache, time.time())
            return data

        # Step 7: Cache fallback if fresh data failed
        if not cached_data:
            cached_data, cache_age = await load_cache_file(hass, host_ip)

        if cached_data:
            try:
                cache.previous_pvs_sample = cached_data
                cache.previous_pvs_sample_time = time.time() - cache_age

                data = convert_sunpower_data(cached_data)
                is_valid, device_count, error_message = validate_converted_data(data)

                if is_valid:
                    # Create diagnostic device for cached data
                    try:
                        inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                        meter_data = data.get('Power Meter', {})
                        pvs_data = data.get(PVS_DEVICE_TYPE, {})
                        diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data, current_polling_interval, polling_enabled)
                        data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                    except Exception as e:
                        _LOGGER.warning("Diagnostic device creation failed for cached data: %s", e)

                    notify_using_cached_data(hass, entry, cache, "polling_error", cache_age)
                    return data
                else:
                    _LOGGER.error("Cached data validation failed: %s", error_message)
            except Exception as e:
                _LOGGER.error("Cache fallback processing failed: %s", e)

        # Ultimate fallback - no data available
        raise UpdateFailed("All data sources failed: fresh polling failed and no valid cache available")

    # Create coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Enhanced SunPower PVS",
        update_method=async_update_data,
        update_interval=timedelta(seconds=polling_interval),
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER,
            cooldown=max(30, polling_interval // 4),
            immediate=False
        ),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        SUNPOWER_OBJECT: sunpower_monitor,
        SUNPOWER_COORDINATOR: coordinator,
        "_cache": cache,  # Make cache accessible for diagnostics
    }

    # Initial setup - COORDINATOR FIRST, THEN PLATFORMS
    try:
        _LOGGER.info("Attempting initial Enhanced SunPower data fetch...")
        await coordinator.async_config_entry_first_refresh()
        
        notify_setup_success(hass, entry, cache)
        _LOGGER.info("Enhanced SunPower integration setup completed successfully")
        
    except Exception as startup_error:
        _LOGGER.warning("Initial Enhanced SunPower data fetch failed: %s", startup_error)
        notify_setup_warning(hass, entry, cache, polling_url, polling_interval)
        _LOGGER.info("Enhanced SunPower integration continuing with polling schedule")

    # Set up platforms AFTER coordinator is working
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP COMPLETE ===")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up session resources
        entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
        sunpower_monitor = entry_data.get(SUNPOWER_OBJECT)
        if sunpower_monitor and hasattr(sunpower_monitor, 'close'):
            await sunpower_monitor.close()

        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
