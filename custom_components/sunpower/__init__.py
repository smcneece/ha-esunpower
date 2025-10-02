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
from homeassistant.util import dt as dt_util

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

_LOGGER = logging.getLogger(__name__)




CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor", "binary_sensor"]

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
        self.startup_notifications_sent = set()
        
        # PVS health check tracking
        self.pvs_health_failures = 0
        self.last_health_check = 0
        self.health_backoff_until = 0
        
        # Inverter health monitoring
        self.inverter_health_initialized = False
        self.expected_inverters = set()
        self.inverter_failure_counts = {}
        
        # Firmware tracking
        self.last_known_firmware = None
        self.firmware_tracking_initialized = False
        
        # Diagnostic tracking
        self.diagnostic_stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'consecutive_failures': 0,
            'last_successful_poll': None,
            'response_times': [],
            'integration_start_time': time.time(),
        }


def create_diagnostic_device_data(cache, inverter_data, meter_data=None):
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

    # Calculate uptime percentage
    uptime_start = stats.get('uptime_start', time.time())
    total_runtime = time.time() - uptime_start
    if total_runtime > 0 and stats.get('last_success_time', 0) > 0:
        uptime_seconds = total_runtime - (stats.get('failed_polls', 0) * 300)
        uptime_percent = max(0, min(100, (uptime_seconds / total_runtime) * 100))
    else:
        uptime_percent = 0

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
        "poll_success_rate": round(success_rate, 1),
        "total_polls": stats.get('total_polls', 0),
        "consecutive_failures": stats.get('failed_polls', 0),  # Use failed_polls as consecutive failures
        "last_successful_poll": last_poll_str,
        "average_response_time": round(avg_response, 2),
        "active_inverters": active_inverters,
        "pvs_uptime_percent": round(uptime_percent, 1),
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


    polling_url = f"http://{entry.data['host']}/cgi-bin/dl_cgi?Command=DeviceList"

    # Get PVS serial last 5 characters for authentication (if provided)
    pvs_serial_last5 = entry.data.get("pvs_serial_last5", "").strip()
    auth_password = pvs_serial_last5 if pvs_serial_last5 else None

    if auth_password:
        _LOGGER.info("Authentication configured - PVS serial last 5 characters provided")
    else:
        _LOGGER.info("No authentication configured - will use unauthenticated requests")

    sunpower_monitor = SunPowerMonitor(entry.data['host'], auth_password=auth_password)

    
    # Simple polling interval - adjustments happen in config flow after battery detection
    polling_interval = entry.options.get("polling_interval", entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL))

    _LOGGER.info("Creating coordinator with interval=%ds", polling_interval)

    async def async_update_data():
        """Simplified data fetching - single polling interval, always active"""

        notify_diagnostic_coordinator_started(hass, entry, cache)

        # Get host IP for cache operations
        host_ip = entry.data['host']

        # Get battery configuration from auto-detection (simplified - no polling overrides)
        has_battery, user_has_battery = get_battery_configuration(entry, cache)

        # Always poll with single interval
        current_polling_interval = polling_interval

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
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}

                notify_using_cached_data(hass, entry, cache, "polling_interval_not_elapsed", cache_age, current_polling_interval)
                return data

        # Always poll PVS - simplified single interval
        fresh_data = None

        # Step 1: Poll PVS for fresh data
        try:
            fresh_data = await poll_pvs_with_safety(sunpower_monitor, current_polling_interval, cache, hass, entry)
            # Note: fresh_data can be None if PVS is unhealthy/backoff - this is normal, use cache
        except Exception as e:
            _LOGGER.error("PVS polling exception: %s", e)
            # Handle authentication vs general polling failures
            await _handle_polling_error(hass, entry, cache, host_ip, e)
            fresh_data = None
            # Continue to cache fallback below

        # Step 2: Save cache if we got fresh data
        if fresh_data:
            try:
                cache_success = await save_cache_file(hass, host_ip, fresh_data)
                if cache_success:
                    cache.previous_pvs_sample = fresh_data
                    cache.previous_pvs_sample_time = time.time()
            except Exception as e:
                _LOGGER.warning("Cache save failed: %s", e)
                # Continue - cache failure isn't critical

        # Step 3: Convert and validate data
        if fresh_data:
            try:
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
            # Battery processing (if detected)
            if has_battery:
                try:
                    old_battery_count = len(data.get(BATTERY_DEVICE_TYPE, {}))
                    ess_data = await sunpower_monitor.energy_storage_system_status_async()

                    if ess_data:
                        data = convert_ess_data(ess_data, data)
                        new_battery_count = len(data.get(BATTERY_DEVICE_TYPE, {}))

                        if old_battery_count == new_battery_count:
                            _LOGGER.warning("ESS data processed but no virtual devices created")

                except Exception as convert_error:
                    _LOGGER.error("ESS data conversion failed: %s", convert_error, exc_info=True)
                    # Don't re-raise - continue with PVS data

            # Step 5: Health checks - only when we have valid PVS data
            try:
                pvs_data = data.get(PVS_DEVICE_TYPE, {})
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})

                if pvs_data and inverter_data:
                    check_firmware_upgrade(hass, entry, cache, pvs_data)
                    check_flash_memory_level(hass, entry, cache, pvs_data)
                    check_inverter_health(hass, entry, cache, inverter_data)
            except Exception as e:
                _LOGGER.warning("Health checks failed: %s", e)
                # Continue - health check failures shouldn't stop data processing

            # Step 6: Create diagnostic device
            try:
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
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
                        diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
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
