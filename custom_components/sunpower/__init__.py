"""The Enhanced SunPower integration with Sunrise/Sunset Elevation - COORDINATOR LOCKUP FIXED"""

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
    convert_state_reason_to_text,
    format_time_duration,
    notify_data_update_success,
    notify_day_mode_elevation,
    notify_diagnostic_coordinator_creating,
    notify_diagnostic_coordinator_started,
    notify_diagnostic_coordinator_status,
    notify_firmware_upgrade,
    notify_night_mode_elevation,
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


def calculate_sun_elevation_fallback():
    """Fallback sun elevation calculation if sun entity unavailable"""
    try:
        now = dt_util.now()
        hour = now.hour
        
        if 6 <= hour <= 20:
            if hour == 6 or hour == 20:
                return 5.0  # Dawn/dusk
            elif hour == 12:
                return 45.0  # Solar noon
            elif 8 <= hour <= 16:
                return 25.0  # Day hours
            else:
                return 10.0  # Morning/evening
        else:
            return -10.0  # Night
    except Exception as e:
        _LOGGER.warning("Fallback sun calculation failed: %s", e)
        return 15.0  # Safe default - assume day mode


def determine_sun_polling_state(elevation, sunrise_threshold, sunset_threshold, has_battery):
    """Determine if polling should be active based on sun elevation
    
    Args:
        elevation: Current sun elevation in degrees
        sunrise_threshold: Start polling threshold  
        sunset_threshold: Stop polling threshold
        has_battery: Whether battery system is installed
        
    Returns:
        tuple: (should_poll, state_reason, active_threshold)
    """
    
    # Battery systems poll 24/7 regardless of sun elevation
    if has_battery:
        return True, "battery_system_active", None
    
    # For solar-only systems, use the lower threshold for maximum coverage
    active_threshold = min(sunrise_threshold, sunset_threshold)
    
    # Simple day/night logic
    if elevation >= active_threshold:
        should_poll = True
        state_reason = "daytime_polling_active"
    else:
        should_poll = False
        state_reason = "nighttime_polling_disabled"
    
    return should_poll, state_reason, active_threshold


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
    stats = cache.diagnostic_stats
    
    # Calculate success rate
    if stats['total_polls'] > 0:
        success_rate = (stats['successful_polls'] / stats['total_polls']) * 100
    else:
        success_rate = 0
    
    # Calculate average response time
    if stats['response_times']:
        avg_response = sum(stats['response_times']) / len(stats['response_times'])
    else:
        avg_response = 0
    
    # Calculate uptime percentage
    total_runtime = time.time() - stats['integration_start_time']
    if total_runtime > 0 and stats['last_successful_poll']:
        uptime_seconds = total_runtime - (stats['failed_polls'] * 300)
        uptime_percent = max(0, min(100, (uptime_seconds / total_runtime) * 100))
    else:
        uptime_percent = 0
    
    # Count active inverters
    active_inverters = len(inverter_data) if inverter_data else 0
    
    # Last successful poll formatting - use timestamp with date
    if stats['last_successful_poll']:
        last_poll_dt = datetime.fromtimestamp(stats['last_successful_poll'])
        last_poll_str = last_poll_dt.strftime("%H:%M %m-%d-%y")
        last_poll_seconds = stats['last_successful_poll']
    else:
        last_poll_str = "Never"
        last_poll_seconds = None
    
    # Get route repairs count (session-based)
    route_repairs_count = getattr(cache, 'route_repairs_count', 0)
    
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
        "total_polls": stats['total_polls'],
        "consecutive_failures": stats['consecutive_failures'],
        "last_successful_poll": last_poll_str,
        "average_response_time": round(avg_response, 2),
        "active_inverters": active_inverters,
        "pvs_uptime_percent": round(uptime_percent, 1),
        "route_repairs_count": route_repairs_count,
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
    
    # Smart PVS health check
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
    if health_status not in ['healthy', 'route_fixed']:
        if health_status == 'backoff':
            remaining = int(cache.health_backoff_until - time.time())
            _LOGGER.info("PVS in backoff period, %ds remaining", remaining)
        else:
            _LOGGER.warning("PVS health check failed, skipping poll")
        update_diagnostic_stats(cache, False)
        return None
    
    # PVS is healthy, proceed with polling
    if health_status == 'route_fixed':
        _LOGGER.info("Route repair successful, retrying PVS polling immediately")
    else:
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


async def migrate_config_if_needed(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate config from old format (polling_interval_seconds, has_battery_system) to new format"""

    # Check if migration is needed
    old_data = entry.data
    old_options = entry.options

    needs_migration = (
        "polling_interval_seconds" in old_data or
        "has_battery_system" in old_data or
        "polling_interval_seconds" in old_options or
        "has_battery_system" in old_options
    )

    if not needs_migration:
        _LOGGER.debug("Config migration not needed - already using new format")
        return

    _LOGGER.info("Migrating config from old format to new day/night intervals...")

    # Migrate data section
    new_data = dict(old_data)

    # Migrate polling interval in data
    if "polling_interval_seconds" in old_data:
        old_interval = old_data["polling_interval_seconds"]
        new_data["daytime_polling_interval"] = old_interval
        del new_data["polling_interval_seconds"]
        _LOGGER.info("Migrated polling_interval_seconds=%d to daytime_polling_interval=%d", old_interval, old_interval)

    # Migrate battery system to nighttime interval in data
    if "has_battery_system" in old_data:
        had_battery = old_data["has_battery_system"]
        if had_battery:
            # Battery systems used to poll 24/7 at same interval
            daytime_interval = new_data.get("daytime_polling_interval", DEFAULT_POLLING_INTERVAL)
            new_data["nighttime_polling_interval"] = daytime_interval
            _LOGGER.info("Migrated has_battery_system=True to nighttime_polling_interval=%d (24/7 polling)", daytime_interval)
        else:
            # Non-battery systems didn't poll at night
            new_data["nighttime_polling_interval"] = 0
            _LOGGER.info("Migrated has_battery_system=False to nighttime_polling_interval=0 (disabled)")
        del new_data["has_battery_system"]

    # Migrate options section
    new_options = dict(old_options)

    # Migrate polling interval in options
    if "polling_interval_seconds" in old_options:
        old_interval = old_options["polling_interval_seconds"]
        new_options["daytime_polling_interval"] = old_interval
        del new_options["polling_interval_seconds"]
        _LOGGER.info("Migrated options polling_interval_seconds=%d to daytime_polling_interval=%d", old_interval, old_interval)

    # Migrate battery system to nighttime interval in options
    if "has_battery_system" in old_options:
        had_battery = old_options["has_battery_system"]
        if had_battery:
            daytime_interval = new_options.get("daytime_polling_interval", new_data.get("daytime_polling_interval", DEFAULT_POLLING_INTERVAL))
            new_options["nighttime_polling_interval"] = daytime_interval
            _LOGGER.info("Migrated options has_battery_system=True to nighttime_polling_interval=%d (24/7 polling)", daytime_interval)
        else:
            new_options["nighttime_polling_interval"] = 0
            _LOGGER.info("Migrated options has_battery_system=False to nighttime_polling_interval=0 (disabled)")
        del new_options["has_battery_system"]

    # Ensure new fields have defaults if not set
    if "daytime_polling_interval" not in new_data:
        new_data["daytime_polling_interval"] = DEFAULT_POLLING_INTERVAL
        _LOGGER.info("Added default daytime_polling_interval=%d", DEFAULT_POLLING_INTERVAL)

    if "nighttime_polling_interval" not in new_data:
        new_data["nighttime_polling_interval"] = 0
        _LOGGER.info("Added default nighttime_polling_interval=0 (disabled)")

    # Apply migration
    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options
    )

    _LOGGER.info("✅ Config migration completed successfully")




async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Enhanced SunPower from a config entry"""
    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP ===")
    entry_id = entry.entry_id

    hass.data[DOMAIN].setdefault(entry_id, {})

    # Create enhanced cache with diagnostics - REMOVED CALLBACK SETUP
    cache = SunPowerDataCache()

    # Migrate config from old format if needed
    await migrate_config_if_needed(hass, entry)

    # Initialize route repairs counter if route checking is enabled (valid gateway IP)
    route_gateway_ip = entry.data.get("route_gateway_ip", "")
    route_check_enabled = route_gateway_ip and route_gateway_ip != "0.0.0.0" and route_gateway_ip.strip() != ""
    if route_check_enabled:
        cache.route_repairs_count = 0
        _LOGGER.info("Route checking enabled with gateway %s - initialized repairs counter to 0", route_gateway_ip)
    else:
        _LOGGER.info("Route checking disabled - no gateway IP configured")

    polling_url = f"http://{entry.data['host']}/cgi-bin/dl_cgi?Command=DeviceList"

    # Get PVS serial last 5 characters for authentication (if provided)
    pvs_serial_last5 = entry.data.get("pvs_serial_last5", "").strip()
    auth_password = pvs_serial_last5 if pvs_serial_last5 else None

    if auth_password:
        _LOGGER.info("Authentication configured - PVS serial last 5 characters provided")
    else:
        _LOGGER.info("No authentication configured - will use unauthenticated requests")

    sunpower_monitor = SunPowerMonitor(entry.data['host'], auth_password=auth_password)
    
    # Default to 300 seconds, minimum 300 seconds for PVS safety
    daytime_polling_interval = max(300, entry.options.get("daytime_polling_interval", entry.data.get("daytime_polling_interval", DEFAULT_POLLING_INTERVAL)))
    nighttime_polling_interval = entry.options.get("nighttime_polling_interval", entry.data.get("nighttime_polling_interval", 0))
    
    _LOGGER.info("Creating coordinator with day=%ds, night=%ds intervals (minimum 300s for PVS protection)",
                 daytime_polling_interval, nighttime_polling_interval)

    async def async_update_data():
        """Enhanced data fetching with sunrise/sunset elevation logic"""
        
        notify_diagnostic_coordinator_started(hass, entry, cache)

        # Get host IP for cache operations
        host_ip = entry.data['host']

        # Sun state check with sunrise/sunset elevation - MOVED UP for interval determination
        try:
            sun_entity = hass.states.get("sun.sun")
            if sun_entity and sun_entity.attributes:
                elevation = float(sun_entity.attributes.get("elevation", -90))

                # Get sunrise and sunset thresholds with migration
                sunrise_elevation = entry.options.get("sunrise_elevation")
                sunset_elevation = entry.options.get("sunset_elevation")

                if sunrise_elevation is None or sunset_elevation is None:
                    old_elevation = entry.options.get("minimum_sun_elevation", 5)
                    if sunrise_elevation is None:
                        sunrise_elevation = old_elevation
                    if sunset_elevation is None:
                        sunset_elevation = old_elevation
                    _LOGGER.info("Migrating elevation settings: %s → sunrise=%s, sunset=%s",
                                old_elevation, sunrise_elevation, sunset_elevation)

                _LOGGER.debug("Sun elevation %.1f°, thresholds: sunrise=%.1f°, sunset=%.1f°",
                             elevation, sunrise_elevation, sunset_elevation)

            else:
                _LOGGER.warning("Sun entity unavailable, using fallback")
                elevation = calculate_sun_elevation_fallback()
                sunrise_elevation = entry.options.get("sunrise_elevation", 5)
                sunset_elevation = entry.options.get("sunset_elevation", 5)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Sun elevation calculation failed: %s", e)
            elevation = 15.0
            sunrise_elevation = 5
            sunset_elevation = 5

        # Get battery configuration from auto-detection
        has_battery, user_has_battery = get_battery_configuration(entry, cache)

        # Determine polling state
        should_poll, state_reason, active_threshold = determine_sun_polling_state(
            elevation, sunrise_elevation, sunset_elevation, has_battery
        )

        # Check if we should override night mode for nighttime polling
        if not should_poll and nighttime_polling_interval > 0:
            should_poll = True
            state_reason = "nighttime_polling_active"

        # Determine current polling interval based on day/night state
        if should_poll:
            if state_reason == "nighttime_polling_active":
                current_polling_interval = nighttime_polling_interval
            elif state_reason == "battery_system_active":
                # Battery systems poll 24/7 but use appropriate day/night intervals
                # Re-check sun elevation to determine which interval to use
                if elevation >= min(sunrise_elevation, sunset_elevation):
                    current_polling_interval = daytime_polling_interval  # Day mode
                else:
                    # Night mode - use nighttime interval if enabled, otherwise daytime
                    current_polling_interval = nighttime_polling_interval if nighttime_polling_interval > 0 else daytime_polling_interval
            else:
                current_polling_interval = daytime_polling_interval
        else:
            current_polling_interval = daytime_polling_interval  # fallback for cached data mode

        # Dynamically update coordinator interval
        new_interval = timedelta(seconds=current_polling_interval)
        if coordinator.update_interval != new_interval:
            _LOGGER.info(
                "Updating polling interval from %s to %s",
                coordinator.update_interval,
                new_interval,
            )
            coordinator.update_interval = new_interval

        # Determine mode string
        if state_reason == "nighttime_polling_active":
            mode = "nighttime"
        elif state_reason == "battery_system_active":
            if elevation >= min(sunrise_elevation, sunset_elevation):
                mode = "battery_day"
            else:
                mode = "battery_night"
        elif should_poll:
            mode = "daytime"
        else:
            mode = "nightmode_disabled"

        # Show diagnostic coordinator status
        # The coordinator's interval is now dynamic, so we pass its current value.
        notify_diagnostic_coordinator_status(hass, entry, cache, current_polling_interval,
                                           coordinator.update_interval.total_seconds(), mode, elevation)

        # Check cache file age using appropriate interval
        cached_data, cache_age = await load_cache_file(hass, host_ip)
        poll_tolerance = 30
        
        if cached_data and cache_age < (current_polling_interval - poll_tolerance):
            # Cache is fresh enough
            remaining_time = current_polling_interval - cache_age
            _LOGGER.info("Skipping poll - cache is only %ds old, waiting %ds more", cache_age, remaining_time)
            
            # Update cache object for compatibility
            cache.previous_pvs_sample = cached_data
            cache.previous_pvs_sample_time = time.time() - cache_age
            
            # Process cached data
            data = convert_sunpower_data(cached_data)
            is_valid, device_count, error_message = validate_converted_data(data)
            if is_valid:
                # Add diagnostic device
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                
                notify_using_cached_data(hass, entry, cache, "polling_interval_not_elapsed", cache_age, current_polling_interval)
                return data
            else:
                _LOGGER.warning("Cached data invalid, proceeding with fresh poll")

        # Handle night mode
        if not should_poll:
            _LOGGER.info("Night mode: %s - using cached data", convert_state_reason_to_text(state_reason))
            notify_night_mode_elevation(hass, entry, has_battery, cache, elevation, 
                                      sunrise_elevation, sunset_elevation, active_threshold, state_reason)
            
            if not cached_data:
                cached_data, cache_age = await load_cache_file(hass, host_ip)
            
            if cached_data:
                cache.previous_pvs_sample = cached_data
                cache.previous_pvs_sample_time = time.time() - cache_age
                
                data = convert_sunpower_data(cached_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if is_valid:
                    inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                    meter_data = data.get('Power Meter', {})
                    diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                    data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                    
                    _LOGGER.info("Night mode: Using cached data with %d devices", device_count)
                    notify_using_cached_data(hass, entry, cache, state_reason, cache_age)
                    return data
            
            _LOGGER.warning("Night mode: No cached data available")
            raise UpdateFailed(f"Night mode ({convert_state_reason_to_text(state_reason)}): No cached data available")
        
        elif should_poll and state_reason != "battery_system_active":
            # Day mode activated
            _LOGGER.info("Day mode activated (%s)", convert_state_reason_to_text(state_reason))
            cache.pvs_health_failures = 0
            cache.health_backoff_until = 0
            cache.last_health_check = 0
            
            notify_day_mode_elevation(hass, entry, cache, elevation, 
                                    sunrise_elevation, sunset_elevation, active_threshold, state_reason)

        # Polling attempt
        try:
            fresh_data = await poll_pvs_with_safety(sunpower_monitor, current_polling_interval, cache, hass, entry)
            
            if fresh_data:
                # Save to cache
                await save_cache_file(hass, host_ip, fresh_data)
                
                cache.previous_pvs_sample = fresh_data
                cache.previous_pvs_sample_time = time.time()
                
                # Convert and validate
                data = convert_sunpower_data(fresh_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if not is_valid:
                    raise UpdateFailed(f"Data conversion failed: {error_message}")

                # Check for ESS devices and poll ESS endpoint if needed (krbaker approach)
                if ESS_DEVICE_TYPE in data:  # Look for "Energy Storage System" in PVS data
                    _LOGGER.debug("Battery system detected, attempting ESS data poll")

                    try:
                        _LOGGER.warning("DEBUG: Attempting ESS endpoint call...")
                        ess_data = await sunpower_monitor.energy_storage_system_status_async()
                        _LOGGER.warning("DEBUG: ESS endpoint returned: %s", str(ess_data)[:500] if ess_data else "None")

                        if ess_data:
                            _LOGGER.debug("ESS data received, integrating with PVS data")
                            try:
                                data = convert_ess_data(ess_data, data)
                                _LOGGER.warning("DEBUG: ESS data integration successful")
                            except Exception as convert_error:
                                _LOGGER.error("DEBUG: ESS data conversion failed: %s", convert_error, exc_info=True)
                                # Don't re-raise - continue with PVS data
                        else:
                            _LOGGER.error("DEBUG: ESS endpoint returned no data")
                    except Exception as ess_error:
                        _LOGGER.error("DEBUG: ESS endpoint failed: %s", ess_error, exc_info=True)
                        # Continue with PVS-only data - don't fail the entire update

                # Check inverter health
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                if inverter_data:
                    check_inverter_health(hass, entry, cache, inverter_data)
                
                # Check firmware upgrades
                pvs_data = data.get(PVS_DEVICE_TYPE, {})
                if pvs_data:
                    check_firmware_upgrade(hass, entry, cache, pvs_data)
                    check_flash_memory_level(hass, entry, cache, pvs_data)
                
                # Add diagnostic device
                meter_data = data.get('Power Meter', {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                
                notify_data_update_success(hass, entry, cache, time.time())
                _LOGGER.info("SUCCESS: Fresh PVS data with %d devices (%d inverters)", 
                           device_count, len(inverter_data))
                return data
            else:
                # Poll failed - use cache
                _LOGGER.info("PVS poll failed, using cached data")
                if not cached_data:
                    cached_data, cache_age = await load_cache_file(hass, host_ip)
                    
                if cached_data:
                    cache.previous_pvs_sample = cached_data
                    cache.previous_pvs_sample_time = time.time() - cache_age
                    
                    data = convert_sunpower_data(cached_data)
                    is_valid, device_count, error_message = validate_converted_data(data)
                    if is_valid:
                        inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                        meter_data = data.get('Power Meter', {})
                        diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                        data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                        
                        notify_using_cached_data(hass, entry, cache, "PVS_health_check_failed", cache_age)
                        return data
                
                raise UpdateFailed("PVS offline and no cached data available")
                
        except Exception as e:
            _LOGGER.error("Polling failed: %s", e)
            notify_polling_failed(hass, entry, cache, polling_url, e)
            
            # Last resort cache
            if not cached_data:
                cached_data, cache_age = await load_cache_file(hass, host_ip)
                
            if cached_data:
                cache.previous_pvs_sample = cached_data
                cache.previous_pvs_sample_time = time.time() - cache_age
                
                data = convert_sunpower_data(cached_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if is_valid:
                    inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                    meter_data = data.get('Power Meter', {})
                    diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data, meter_data)
                    data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                    
                    notify_using_cached_data(hass, entry, cache, "polling_error", cache_age)
                    return data
            
            raise UpdateFailed(f"All data sources failed: {e}")

    # Create coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Enhanced SunPower PVS",
        update_method=async_update_data,
        update_interval=timedelta(seconds=daytime_polling_interval),
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER,
            cooldown=max(30, daytime_polling_interval // 4),
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
        notify_setup_warning(hass, entry, cache, polling_url, daytime_polling_interval)
        _LOGGER.info("Enhanced SunPower integration continuing with polling schedule")

    # Set up platforms AFTER coordinator is working
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP COMPLETE ===")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
