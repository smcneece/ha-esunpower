"""The Enhanced SunPower integration with Sunrise/Sunset Elevation - SIMPLE SOLAR LOGIC"""

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
    DOMAIN,
    PVS_DEVICE_TYPE,
    INVERTER_DEVICE_TYPE,
    DIAGNOSTIC_DEVICE_TYPE,
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
    smart_pvs_health_check,
    check_inverter_health,
)

# Import notification functions
from .notifications import (
    safe_notify,
    notify_diagnostic_coordinator_started,
    notify_diagnostic_coordinator_creating,
    notify_day_mode_elevation,
    notify_night_mode_elevation,
    notify_setup_success,
    notify_data_update_success,
    notify_polling_failed,
    notify_setup_warning,
    notify_using_cached_data,
)

_LOGGER = logging.getLogger(__name__)

def check_firmware_upgrade(hass, entry, cache, pvs_data):
    """Check for PVS firmware upgrades and notify"""
    # Import notification function locally to avoid circular imports
    from .notifications import notify_firmware_upgrade
    
    if not pvs_data:
        return
    
    # Get the PVS device (should only be one)
    pvs_device = next(iter(pvs_data.values()), None)
    if not pvs_device:
        return
    
    current_firmware = pvs_device.get("SWVER")
    if not current_firmware:
        return
    
    # Initialize tracking on first successful poll
    if not cache.firmware_tracking_initialized:
        cache.last_known_firmware = current_firmware
        cache.firmware_tracking_initialized = True
        _LOGGER.info("Initialized firmware tracking: %s", current_firmware)
        return
    
    # Check for firmware change
    if cache.last_known_firmware and current_firmware != cache.last_known_firmware:
        _LOGGER.info("PVS firmware upgrade detected: %s → %s", cache.last_known_firmware, current_firmware)
        notify_firmware_upgrade(hass, entry, cache, cache.last_known_firmware, current_firmware)
        cache.last_known_firmware = current_firmware
    elif not cache.last_known_firmware:
        # Handle case where we didn't have firmware before
        cache.last_known_firmware = current_firmware


# Simplified battery configuration
def get_battery_configuration_simple(entry):
    """Simple battery configuration - no complex cache logic"""
    user_has_battery = entry.options.get("has_battery_system") or entry.data.get("has_battery_system", False)
    return user_has_battery, user_has_battery

def reset_battery_failure_tracking_simple(cache):
    """Simple battery tracking reset"""
    cache.battery_detection_failures = 0
    cache.battery_warning_sent = False

def handle_battery_detection_simple(hass, entry, data, cache, safe_notify, user_has_battery):
    """Simplified battery detection - no complex warnings"""
    if not user_has_battery:
        return
    _LOGGER.debug("Battery system enabled, detection logic simplified")

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
    """SIMPLE: Determine if polling should be active based on sun elevation - CLEANED UP
    
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
    # This gives the most generous polling window
    active_threshold = min(sunrise_threshold, sunset_threshold)
    
    # Simple day/night logic
    if elevation >= active_threshold:
        should_poll = True
        state_reason = "daytime_polling_active"
    else:
        should_poll = False
        state_reason = "nighttime_polling_disabled"
    
    return should_poll, state_reason, active_threshold


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
        
        # PVS health check tracking (DST-safe)
        self.pvs_health_failures = 0
        self.last_health_check = 0
        self.health_backoff_until = 0
        
        # Battery detection failure tracking
        self.battery_detection_failures = 0
        self.battery_warning_sent = False
        
        # Inverter health monitoring
        self.inverter_health_initialized = False
        self.expected_inverters = set()
        self.inverter_failure_counts = {}
        
        # Firmware tracking
        self.last_known_firmware = None
        self.firmware_tracking_initialized = False
        
        # NEW: Diagnostic tracking
        self.diagnostic_stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'consecutive_failures': 0,
            'last_successful_poll': None,
            'response_times': [],
            'integration_start_time': time.time(),
        }


def update_diagnostic_stats(cache, success, response_time=None):
    """Update diagnostic statistics for dashboard sensors"""
    stats = cache.diagnostic_stats
    
    # Update totals
    stats['total_polls'] += 1
    
    if success:
        stats['successful_polls'] += 1
        stats['consecutive_failures'] = 0
        stats['last_successful_poll'] = time.time()
        
        # Track response times (keep last 50 for average)
        if response_time:
            stats['response_times'].append(response_time)
            if len(stats['response_times']) > 50:
                stats['response_times'].pop(0)
    else:
        stats['failed_polls'] += 1
        stats['consecutive_failures'] += 1


def create_diagnostic_device_data(cache, inverter_data):
    """Create diagnostic device data for sensors - FIXED DATA FORMATS"""
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
        # Consider "up" time as time when we were successfully polling
        uptime_seconds = total_runtime - (stats['failed_polls'] * 300)  # Assume 300s poll interval
        uptime_percent = max(0, min(100, (uptime_seconds / total_runtime) * 100))
    else:
        uptime_percent = 0
    
    # Count active inverters vs total expected
    total_expected = len(cache.expected_inverters) if hasattr(cache, 'expected_inverters') else 0
    active_inverters = len(inverter_data) if inverter_data else 0
    
    # FIXED: Last successful poll as simple string (not timestamp object) - TIME CONVERSION FIX
    if stats['last_successful_poll']:
        time_ago = int(time.time() - stats['last_successful_poll'])
        # Use the time conversion function
        from .notifications import format_time_duration
        last_poll_str = format_time_duration(time_ago) + " ago"
    else:
        last_poll_str = "Never"
    
    # FIXED: Active inverters as simple number, not ratio string
    active_inverters_value = active_inverters
    
    # Create diagnostic device
    diagnostic_serial = "sunpower_diagnostics"
    diagnostic_device = {
        "SERIAL": diagnostic_serial,
        "MODEL": "Enhanced SunPower Diagnostics",
        "DESCR": "Enhanced SunPower Integration Diagnostics",
        "DEVICE_TYPE": DIAGNOSTIC_DEVICE_TYPE,
        "STATE": "working",
        "SWVER": "2025.8.7",
        "HWVER": "Virtual",
        "poll_success_rate": round(success_rate, 1),
        "total_polls": stats['total_polls'],
        "consecutive_failures": stats['consecutive_failures'],
        "last_successful_poll": last_poll_str,  # FIXED: Simple string with time conversion
        "average_response_time": round(avg_response, 2),
        "active_inverters": active_inverters_value,  # FIXED: Simple number
        "pvs_uptime_percent": round(uptime_percent, 1),
    }
    
    return diagnostic_serial, diagnostic_device


async def save_cache_file(hass: HomeAssistant, entry_id: str, pvs_data: dict):
    """Save PVS data to simple cache file - ASYNC COMPLIANT"""
    try:
        # Use HA storage directory for cache file
        storage_path = hass.config.path(".storage")
        cache_file = os.path.join(storage_path, f"sunpower_cache_{entry_id}.json")
        
        # Validate data before saving
        if not pvs_data or not isinstance(pvs_data, dict) or "devices" not in pvs_data:
            _LOGGER.warning("Invalid PVS data, not saving to cache")
            return False
        
        # FIXED: Use async file operations to avoid blocking the event loop
        def write_cache_file():
            with open(cache_file, 'w') as f:
                json.dump(pvs_data, f, indent=2)
            return True
        
        await hass.async_add_executor_job(write_cache_file)
        
        device_count = len(pvs_data.get("devices", []))
        _LOGGER.info("Saved PVS data to cache: %d devices", device_count)
        return True
        
    except Exception as e:
        _LOGGER.error("Failed to save cache file: %s", e)
        return False


async def load_cache_file(hass: HomeAssistant, entry_id: str):
    """Load PVS data from simple cache file - ASYNC COMPLIANT"""
    try:
        # Use HA storage directory for cache file
        storage_path = hass.config.path(".storage")
        cache_file = os.path.join(storage_path, f"sunpower_cache_{entry_id}.json")
        
        # Check if file exists using async
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
            _LOGGER.info("No cache file found: %s", cache_file)
            return None, 0
        
        # Validate cached data
        if not pvs_data or not isinstance(pvs_data, dict) or "devices" not in pvs_data:
            _LOGGER.warning("Invalid cached data, removing cache file")
            await hass.async_add_executor_job(lambda: os.remove(cache_file))
            return None, 0
        
        device_count = len(pvs_data.get("devices", []))
        _LOGGER.info("Loaded cached PVS data: %d devices, %.0fs old", device_count, cache_age)
        return pvs_data, cache_age
        
    except Exception as e:
        _LOGGER.error("Failed to load cache file: %s", e)
        return None, 0


async def poll_pvs_with_safety(sunpower_monitor, polling_interval, cache, hass, entry):
    """Poll PVS with existing safety protocols and diagnostic tracking"""
    
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
    if health_status != 'healthy':
        if health_status == 'backoff':
            remaining = int(cache.health_backoff_until - time.monotonic())
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Enhanced SunPower from a config entry with sunrise/sunset elevation"""
    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP (SUNRISE/SUNSET ELEVATION) ===")
    entry_id = entry.entry_id

    hass.data[DOMAIN].setdefault(entry_id, {})

    # Create enhanced cache with diagnostics
    cache = SunPowerDataCache()

    polling_url = f"http://{entry.data['host']}/cgi-bin/dl_cgi?Command=DeviceList"
    sunpower_monitor = SunPowerMonitor(entry.data['host'])
    
    # Default to 300 seconds, minimum 300 seconds for PVS safety
    polling_interval = max(300, entry.options.get("polling_interval_seconds", entry.data.get("polling_interval_seconds", DEFAULT_POLLING_INTERVAL)))
    
    _LOGGER.info("Creating coordinator with %ds interval (minimum 300s for PVS protection)", polling_interval)

    async def async_update_data():
        """Enhanced data fetching with SIMPLE sunrise/sunset elevation logic"""
        
        notify_diagnostic_coordinator_started(hass, entry, cache)
        
        # SMART POLL TIMING: Check cache file age first with tolerance
        cached_data, cache_age = await load_cache_file(hass, entry_id)
        poll_tolerance = 30  # Allow 30 second tolerance for timing precision
        
        if cached_data and cache_age < (polling_interval - poll_tolerance):
            # Cache is fresh enough, use it instead of polling
            remaining_time = polling_interval - cache_age
            _LOGGER.info("Skipping poll - cache is only %ds old (<%ds with %ds tolerance), waiting %ds more", 
                        cache_age, polling_interval, poll_tolerance, remaining_time)
            
            # Update cache object for compatibility
            cache.previous_pvs_sample = cached_data
            cache.previous_pvs_sample_time = time.time() - cache_age
            
            # Process cached data
            data = convert_sunpower_data(cached_data)
            is_valid, device_count, error_message = validate_converted_data(data)
            if is_valid:
                # Add diagnostic device
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                
                # Use cached data notification with time conversion
                notify_using_cached_data(hass, entry, cache, "polling interval not elapsed", cache_age)
                return data
            else:
                _LOGGER.warning("Cached data invalid, proceeding with fresh poll despite timing")
        else:
            if cached_data:
                _LOGGER.info("Cache is %ds old (>=%ds with %ds tolerance), proceeding with fresh poll", 
                            cache_age, polling_interval - poll_tolerance, poll_tolerance)
            else:
                _LOGGER.info("No cache file found, proceeding with fresh poll")
        
        # SIMPLE sun state check with sunrise/sunset elevation
        try:
            sun_entity = hass.states.get("sun.sun")
            if sun_entity and sun_entity.attributes:
                elevation = float(sun_entity.attributes.get("elevation", -90))
                
                # Get sunrise and sunset thresholds (with migration from old single threshold)
                sunrise_elevation = entry.options.get("sunrise_elevation")
                sunset_elevation = entry.options.get("sunset_elevation")
                
                # Migration: If no sunrise/sunset values but old minimum_sun_elevation exists
                if sunrise_elevation is None or sunset_elevation is None:
                    old_elevation = entry.options.get("minimum_sun_elevation", 5)
                    sunrise_elevation = old_elevation if sunrise_elevation is None else sunrise_elevation
                    sunset_elevation = old_elevation if sunset_elevation is None else sunset_elevation
                    _LOGGER.info("Migrating from minimum_sun_elevation=%s to sunrise=%s, sunset=%s", 
                                old_elevation, sunrise_elevation, sunset_elevation)
                
                _LOGGER.debug("Sun elevation %.1f°, sunrise threshold: %.1f°, sunset threshold: %.1f°", 
                             elevation, sunrise_elevation, sunset_elevation)
                
            else:
                _LOGGER.warning("Sun entity unavailable, using fallback calculation")
                elevation = calculate_sun_elevation_fallback()
                sunrise_elevation = entry.options.get("sunrise_elevation", 5)
                sunset_elevation = entry.options.get("sunset_elevation", 5)
                _LOGGER.info("Fallback sun elevation: %.1f° (sunrise: %.1f°, sunset: %.1f°)", 
                            elevation, sunrise_elevation, sunset_elevation)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Sun elevation calculation failed: %s, using safe fallback", e)
            elevation = 15.0
            sunrise_elevation = 5
            sunset_elevation = 5

        # Get battery configuration
        has_battery, user_has_battery = get_battery_configuration_simple(entry)
        reset_battery_failure_tracking_simple(cache)

        # SIMPLE: Determine polling state using cleaned up logic
        should_poll, state_reason, active_threshold = determine_sun_polling_state(
            elevation, sunrise_elevation, sunset_elevation, has_battery
        )

        # Handle night mode (when polling disabled)
        if not should_poll:
            _LOGGER.info("Night mode: %s - using cached data", state_reason)
            notify_night_mode_elevation(hass, entry, has_battery, cache, elevation, 
                                      sunrise_elevation, sunset_elevation, active_threshold, state_reason)
            
            # Load cache file (may be same as above check, but ensure we have it)
            if not cached_data:
                cached_data, cache_age = await load_cache_file(hass, entry_id)
            
            if cached_data:
                # Update cache object for compatibility
                cache.previous_pvs_sample = cached_data
                cache.previous_pvs_sample_time = time.time() - cache_age
                
                data = convert_sunpower_data(cached_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if is_valid:
                    # Add diagnostic device
                    inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                    diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data)
                    data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                    
                    _LOGGER.info("Night mode: Using cached data with %d devices", device_count)
                    notify_using_cached_data(hass, entry, cache, f"{state_reason} - solar polling disabled", cache_age)
                    return data
            
            # No cache file - fail gracefully
            _LOGGER.warning("Night mode: No cached data available")
            raise UpdateFailed(f"Night mode ({state_reason}): No cached data available")
        
        elif should_poll and state_reason != "battery_system_active":
            # Day mode activated - reset health check state
            _LOGGER.info("Day mode activated (%s) - resetting health check state for fresh start", state_reason)
            cache.pvs_health_failures = 0
            cache.health_backoff_until = 0
            cache.last_health_check = 0
            
            notify_day_mode_elevation(hass, entry, cache, elevation, 
                                    sunrise_elevation, sunset_elevation, active_threshold, state_reason)

        # Polling attempt (only reached if cache check didn't return or night mode failed)
        try:
            # Try to poll PVS (with diagnostic tracking)
            fresh_data = await poll_pvs_with_safety(sunpower_monitor, polling_interval, cache, hass, entry)
            
            if fresh_data:
                # Poll successful - save to cache file
                await save_cache_file(hass, entry_id, fresh_data)
                
                # Update cache object for compatibility
                cache.previous_pvs_sample = fresh_data
                cache.previous_pvs_sample_time = time.time()
                
                # Convert and validate
                data = convert_sunpower_data(fresh_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if not is_valid:
                    raise UpdateFailed(f"Data conversion failed: {error_message}")
                
                # Check inverter health after successful poll
                inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                if inverter_data:
                    check_inverter_health(hass, entry, cache, inverter_data)
                
                # Check for firmware upgrades after successful poll
                pvs_data = data.get(PVS_DEVICE_TYPE, {})
                if pvs_data:
                    check_firmware_upgrade(hass, entry, cache, pvs_data)
                
                # Add diagnostic device
                diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data)
                data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                
                # Handle battery detection
                try:
                    handle_battery_detection_simple(hass, entry, data, cache, safe_notify, user_has_battery)
                except Exception as error:
                    _LOGGER.error("Battery detection handler failed: %s", error)
                
                # Success notification
                notify_data_update_success(hass, entry, cache, time.time())
                _LOGGER.info("SUCCESS: Fresh PVS data with %d devices (%d inverters)", 
                           device_count, len(inverter_data))
                return data
            else:
                # Poll failed (health check failed) - use cache file
                _LOGGER.info("PVS poll failed, attempting to use cached data")
                if not cached_data:
                    cached_data, cache_age = await load_cache_file(hass, entry_id)
                    
                if cached_data:
                    # Update cache object for compatibility
                    cache.previous_pvs_sample = cached_data
                    cache.previous_pvs_sample_time = time.time() - cache_age
                    
                    data = convert_sunpower_data(cached_data)
                    is_valid, device_count, error_message = validate_converted_data(data)
                    if is_valid:
                        # Add diagnostic device
                        inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                        diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data)
                        data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                        
                        _LOGGER.info("Using cached data with %d devices", device_count)
                        notify_using_cached_data(hass, entry, cache, "PVS health check failed", cache_age)
                        return data
                
                # No cache available - fail gracefully
                _LOGGER.warning("No cached data available after PVS failure")
                raise UpdateFailed("PVS offline and no cached data available")
                
        except Exception as e:
            _LOGGER.error("Polling attempt failed: %s", e)
            notify_polling_failed(hass, entry, cache, polling_url, e)
            
            # Last resort - try cache file
            if not cached_data:
                cached_data, cache_age = await load_cache_file(hass, entry_id)
                
            if cached_data:
                # Update cache object for compatibility
                cache.previous_pvs_sample = cached_data
                cache.previous_pvs_sample_time = time.time() - cache_age
                
                data = convert_sunpower_data(cached_data)
                is_valid, device_count, error_message = validate_converted_data(data)
                if is_valid:
                    # Add diagnostic device
                    inverter_data = data.get(INVERTER_DEVICE_TYPE, {})
                    diag_serial, diag_device = create_diagnostic_device_data(cache, inverter_data)
                    data[DIAGNOSTIC_DEVICE_TYPE] = {diag_serial: diag_device}
                    
                    _LOGGER.info("Error fallback: Using cached data with %d devices", device_count)
                    notify_using_cached_data(hass, entry, cache, "polling error - using cache", cache_age)
                    return data
            
            # No fallback available
            _LOGGER.error("All data sources failed - no cached data available")
            raise UpdateFailed(f"All data sources failed: {e}")

    # Create coordinator with proper debouncer (back to standard DataUpdateCoordinator)
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

    # Initial setup
    try:
        _LOGGER.info("Attempting initial Enhanced SunPower data fetch...")
        await coordinator.async_config_entry_first_refresh()
        
        notify_setup_success(hass, entry, cache)
        _LOGGER.info("Enhanced SunPower integration setup completed successfully")
        
    except Exception as startup_error:
        _LOGGER.warning("Initial Enhanced SunPower data fetch failed: %s", startup_error)
        notify_setup_warning(hass, entry, cache, polling_url, polling_interval)
        _LOGGER.info("Enhanced SunPower integration continuing with polling schedule")

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("=== ENHANCED SUNPOWER INTEGRATION STARTUP COMPLETE (SUNRISE/SUNSET) ===")
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
