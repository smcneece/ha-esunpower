"""SunPower PVS Health Check Module"""

import logging
import time

_LOGGER = logging.getLogger(__name__)


def initialize_inverter_tracking(cache, inverter_data):
    """Initialize inverter health tracking state"""
    if not hasattr(cache, 'inverter_health'):
        cache.inverter_health = {}

    # Initialize tracking for all inverters
    for serial in inverter_data.keys():
        if serial not in cache.inverter_health:
            # Don't assume working initially - determine from actual state
            # This prevents false failure notifications on startup
            cache.inverter_health[serial] = {
                'last_seen': time.time(),
                'consecutive_failures': 0,
                'total_failures': 0,
                'was_working': False,  # Start as unknown/not working to avoid false notifications
                'first_failure_time': None,
                'first_error_time': None,  # Track when persistent error state began
                'persistent_error_notified': False,  # Prevent repeated 24h notifications
            }
            _LOGGER.debug("Initialized tracking for new inverter %s with was_working=False", serial)


def reset_inverter_health_tracking(cache):
    """Reset inverter failure counts but preserve working state to avoid false failure notifications

    Called during integration startup to ensure clean state after disable/enable cycles
    """
    if hasattr(cache, 'inverter_health'):
        current_time = time.time()
        for serial, health in cache.inverter_health.items():
            # Clear failure counts but don't blindly set was_working = True
            # This prevents false failure notifications on startup
            health['consecutive_failures'] = 0
            health['total_failures'] = 0
            health['first_failure_time'] = None
            health['last_seen'] = current_time
            # Don't modify was_working - let normal health check determine current state
        _LOGGER.debug("Reset inverter failure tracking for %d inverters", len(cache.inverter_health))


def check_inverter_health(hass, entry, cache, current_inverter_data):
    """Check health of all inverters and track failures with batched notifications"""
    from .notifications import notify_batched_inverter_issues

    current_time = time.time()

    # Debug what data we're receiving
    _LOGGER.debug("Health check called with %d inverters",
                 len(current_inverter_data))

    # Initialize tracking if needed
    initialize_inverter_tracking(cache, current_inverter_data)

    # Collect notifications to batch them
    persistent_errors = []
    recoveries = []

    for serial, data in current_inverter_data.items():
        health = cache.inverter_health[serial]

        # Debug: Log the initial state of each inverter to identify the "last inverter" pattern
        _LOGGER.debug("Processing inverter %s: was_working=%s", serial, health['was_working'])

        # Check if inverter is working (has recent data and reasonable power)
        power_value = data.get('p_3phsum_kw', 0)

        # Handle both string and numeric power values
        try:
            if isinstance(power_value, str):
                power_float = float(power_value)
            elif isinstance(power_value, (int, float)):
                power_float = float(power_value)
            else:
                power_float = 0.0
            has_valid_power = True
        except (ValueError, TypeError):
            has_valid_power = False
            power_float = 0.0

        # RESTORED ORIGINAL LOGIC: Only flag failures for MISSING inverters, not STATE changes
        # If inverter is present in JSON (regardless of STATE), it's communicating
        # This matches the original github_staging logic that worked correctly
        inverter_state = data.get('STATE', '').lower()
        is_working = data.get('DATATIME') is not None  # Present with recent data = working

        # Enhanced debug logging to understand the notification pattern
        _LOGGER.debug("Inverter %s: STATE=%s, was_working=%s, consecutive_failures=%d, will_notify=%s",
                     serial, inverter_state, health['was_working'], health['consecutive_failures'],
                     (not is_working and health['was_working']))

        if is_working:
            # Inverter is working - reset error tracking
            health['last_seen'] = current_time
            health['was_working'] = True

            # Check for recovery from persistent error
            if health['first_error_time'] is not None:
                error_duration_hours = (current_time - health['first_error_time']) / 3600
                _LOGGER.info("Inverter %s recovered after %.1f hours in error state", serial, error_duration_hours)

                # Collect recovery for batching if we had notified about persistent error
                if health['persistent_error_notified']:
                    recoveries.append({
                        'serial': serial,
                        'duration_hours': int(error_duration_hours)
                    })

            # Reset error tracking
            health['first_error_time'] = None
            health['persistent_error_notified'] = False
            health['consecutive_failures'] = 0
            health['first_failure_time'] = None

        else:
            # Inverter is not working - track error duration
            if health['first_error_time'] is None:
                # Start tracking error state
                health['first_error_time'] = current_time
                _LOGGER.debug("Inverter %s entering error state, starting 24h timer", serial)
            else:
                # Check if error has persisted for 24+ hours
                error_duration = current_time - health['first_error_time']
                error_hours = error_duration / 3600

                if error_duration >= 86400 and not health['persistent_error_notified']:  # 24 hours
                    # Collect persistent error for batching
                    _LOGGER.warning("Inverter %s has persistent error for %.1f hours", serial, error_hours)
                    persistent_errors.append({
                        'serial': serial,
                        'duration_hours': int(error_hours)
                    })
                    health['persistent_error_notified'] = True

            # Update legacy tracking for compatibility
            health['was_working'] = False
            if health['consecutive_failures'] == 0:
                health['first_failure_time'] = current_time
            health['consecutive_failures'] += 1

    # Send batched notifications at the end
    if persistent_errors or recoveries:
        notify_batched_inverter_issues(hass, entry, cache, persistent_errors, recoveries)


def get_inverter_health_summary(cache):
    """Get summary of inverter health for diagnostics"""
    if not hasattr(cache, 'inverter_health'):
        return "No inverter health data available"

    total = len(cache.inverter_health)
    working = sum(1 for h in cache.inverter_health.values() if h['was_working'])
    failed = total - working

    if failed == 0:
        return f"All {total} inverters healthy"
    else:
        return f"{working}/{total} inverters healthy, {failed} failed"


def check_firmware_upgrade(hass, entry, cache, pvs_data):
    """Check for PVS firmware upgrades"""
    from .notifications import notify_firmware_upgrade

    current_time = time.time()

    for serial, data in pvs_data.items():
        swver = data.get('SWVER', '')

        # Initialize firmware tracking
        if not hasattr(cache, 'firmware_versions'):
            cache.firmware_versions = {}

        if serial not in cache.firmware_versions:
            cache.firmware_versions[serial] = {
                'current': swver,
                'last_check': current_time,
                'upgrade_notified': False
            }
        else:
            stored = cache.firmware_versions[serial]

            # Check for version change
            if swver != stored['current'] and swver:
                _LOGGER.info("PVS firmware upgrade detected: %s -> %s", stored['current'], swver)

                # Only notify if it's been more than 1 hour since last check
                if current_time - stored['last_check'] > 3600:
                    notify_firmware_upgrade(hass, entry, cache, stored['current'], swver)
                    stored['upgrade_notified'] = True

                # Update stored version
                stored['current'] = swver
                stored['last_check'] = current_time


def check_battery_system_health(hass, entry, cache, data):
    """Check battery system health and connectivity"""
    from .notifications import notify_battery_system_issue

    # Check for ESS devices
    ess_devices = data.get("Energy Storage System", {})
    battery_devices = data.get("Battery", {})
    sunvault_devices = data.get("SunVault", {})

    if not any([ess_devices, battery_devices, sunvault_devices]):
        return  # No battery system configured

    # Check if battery data is stale or missing
    current_time = time.time()

    # Initialize battery health tracking
    if not hasattr(cache, 'battery_health'):
        cache.battery_health = {
            'last_successful_poll': current_time,
            'consecutive_failures': 0,
            'total_failures': 0
        }

    battery_health = cache.battery_health

    # Check if we have valid battery data
    has_valid_data = False

    for device_type in ["Energy Storage System", "Battery", "SunVault"]:
        devices = data.get(device_type, {})
        for serial, device_data in devices.items():
            # Check for recent timestamp and valid state
            if (device_data.get('STATE', '').lower() in ['working', 'error'] and
                device_data.get('DATATIME') is not None):
                has_valid_data = True
                break
        if has_valid_data:
            break

    if has_valid_data:
        # Reset failure tracking
        if battery_health['consecutive_failures'] > 0:
            _LOGGER.info("Battery system connectivity restored after %d failures",
                        battery_health['consecutive_failures'])
            battery_health['consecutive_failures'] = 0

        battery_health['last_successful_poll'] = current_time
    else:
        # Battery system issue
        battery_health['consecutive_failures'] += 1
        battery_health['total_failures'] += 1

        # Notify on milestone failures
        if battery_health['consecutive_failures'] in [3, 6, 12, 24]:
            notify_battery_system_issue(hass, entry, cache, battery_health['consecutive_failures'])


def check_flash_memory_level(hass, entry, cache, pvs_data):
    """Check PVS flash memory levels and alert if usage exceeds threshold percentage."""
    from .notifications import notify_flash_memory_critical

    flash_threshold = entry.options.get("flash_memory_threshold_mb", 85)

    if flash_threshold <= 0:
        return

    for serial, data in pvs_data.items():
        if not hasattr(cache, 'flash_memory_alerts'):
            cache.flash_memory_alerts = {}

        if serial not in cache.flash_memory_alerts:
            cache.flash_memory_alerts[serial] = {
                'last_alert_time': 0,
                'alert_count': 0
            }

        alert_info = cache.flash_memory_alerts[serial]
        current_time = time.time()

        flash_usage_pct = data.get('flash_usage_percent')

        if flash_usage_pct is not None:
            try:
                flash_pct = int(flash_usage_pct)

                if flash_pct > flash_threshold:
                    if current_time - alert_info['last_alert_time'] > 86400:
                        notify_flash_memory_critical(hass, entry, cache, serial, f"{100 - flash_pct}%", f"{100 - flash_threshold}%")
                        alert_info['last_alert_time'] = current_time
                        alert_info['alert_count'] += 1
                        _LOGGER.warning("PVS %s flash memory critical: %d%% available (threshold: %d%%)",
                                      serial, 100 - flash_pct, 100 - flash_threshold)
                else:
                    alert_info['last_alert_time'] = 0

            except (ValueError, TypeError):
                _LOGGER.debug("Invalid flash usage value for PVS %s: %s", serial, flash_usage_pct)


def update_diagnostic_stats(cache, success, response_time=None):
    """Update diagnostic statistics for the integration"""
    current_time = time.time()

    # Initialize diagnostic stats with safe defaults
    if not hasattr(cache, 'diagnostic_stats') or cache.diagnostic_stats is None:
        cache.diagnostic_stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'average_response_time': 0.0,
            'last_success_time': 0,
            'last_failure_time': 0,
            'uptime_start': current_time
        }

    stats = cache.diagnostic_stats

    # Ensure all required keys exist (defensive programming)
    required_keys = {
        'total_polls': 0,
        'successful_polls': 0,
        'failed_polls': 0,
        'average_response_time': 0.0,
        'last_success_time': 0,
        'last_failure_time': 0,
        'uptime_start': current_time
    }

    for key, default_value in required_keys.items():
        if key not in stats:
            stats[key] = default_value

    stats['total_polls'] += 1

    if success:
        stats['successful_polls'] += 1
        stats['last_success_time'] = current_time

        if response_time is not None:
            # Update rolling average response time
            if stats.get('average_response_time', 0) == 0:
                stats['average_response_time'] = response_time
            else:
                # Weighted average (90% old, 10% new)
                stats['average_response_time'] = (stats['average_response_time'] * 0.9) + (response_time * 0.1)
    else:
        stats['failed_polls'] += 1
        stats['last_failure_time'] = current_time

def check_flash_wear_level(hass, entry, cache, pvs_data):
    """Monitor PVS flash wear percentage and send daily alerts when threshold exceeded

    Args:
        hass: Home Assistant instance
        entry: Config entry
        cache: Integration cache
        pvs_data: Dictionary of PVS devices from coordinator data
    
    Flash wear shows EMMC lifetime consumed (higher = more wear):
    - 0% = brand new flash storage
    - 50% = halfway through lifetime
    - 90% = approaching end of life (default alert threshold)
    - 100% = flash storage failed
    """
    # Get threshold from config (default 90%)
    flash_wear_threshold = entry.options.get("flash_wear_threshold", 90)
    
    # Skip if threshold is 0 (disabled)
    if flash_wear_threshold == 0:
        return
    
    for serial, data in pvs_data.items():
        # Initialize alert tracking for this PVS (keyed by serial + '_flash_wear')
        alert_key = f"{serial}_flash_wear"
        if alert_key not in cache.startup_notifications_sent:
            cache.startup_notifications_sent[alert_key] = {'last_alert_time': 0, 'alert_count': 0}
        
        alert_info = cache.startup_notifications_sent[alert_key]
        current_time = time.time()
        
        flashwear_pct = data.get('flashwear_percent')
        
        if flashwear_pct is not None:
            try:
                wear_pct = int(flashwear_pct)
                
                # Alert if flash wear exceeds threshold (higher wear = more consumed)
                if wear_pct >= flash_wear_threshold:
                    # Only alert once per 24 hours
                    if current_time - alert_info['last_alert_time'] > 86400:  # 24 hours
                        # Calculate remaining life
                        remaining_pct = 100 - wear_pct
                        
                        # Send notification
                        from .notifications import notify_flash_wear_critical
                        notify_flash_wear_critical(hass, entry, cache, serial, wear_pct, flash_wear_threshold, remaining_pct)
                        
                        alert_info['last_alert_time'] = current_time
                        alert_info['alert_count'] += 1
                        
                        _LOGGER.warning("PVS %s flash wear critical: %d%% used / %d%% remaining (threshold: %d%%)",
                                      serial, wear_pct, remaining_pct, flash_wear_threshold)
                else:
                    # Reset alert tracking when below threshold
                    alert_info['last_alert_time'] = 0
            
            except (ValueError, TypeError):
                _LOGGER.debug("Invalid flash wear value for PVS %s: %s", serial, flashwear_pct)
