"""SunPower Integration Multi-Channel Notification System - FIXED NOTIFICATION TEXT"""

import hashlib
import logging
import time
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


def format_time_duration(seconds):
    """Convert seconds to human-readable duration (minutes/hours)"""
    try:
        seconds = int(seconds)
        
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours}h {remaining_minutes}m"
    except (ValueError, TypeError):
        return f"{seconds}s"  # Fallback to original format


def convert_state_reason_to_text(state_reason):
    """Convert state_reason codes to human-readable text"""
    reason_map = {
        "nighttime_polling_disabled": "nighttime mode",
        "daytime_polling_active": "daytime mode", 
        "battery_system_active": "battery system active",
        "above_sunrise_threshold": "above sunrise threshold",
        "above_sunset_threshold": "above sunset threshold", 
        "below_sunrise_threshold": "below sunrise threshold",
        "below_sunset_threshold": "below sunset threshold",
        "polling_interval_not_elapsed": "polling interval not elapsed",
        "PVS_health_check_failed": "PVS health check failed",
        "polling_error": "polling error"
    }
    
    return reason_map.get(state_reason, state_reason)


async def get_mobile_devices(hass):
    """Get list of available mobile app notification services"""
    mobile_devices = {}
    
    try:
        # Get all available services
        services = hass.services.async_services()
        notify_services = services.get('notify', {})
        
        for service_name in notify_services:
            if service_name.startswith('mobile_app_'):
                # Extract device name from service name
                device_name = service_name.replace('mobile_app_', '').replace('_', ' ').title()
                mobile_devices[service_name] = device_name
                
        _LOGGER.debug("Found %d mobile devices: %s", len(mobile_devices), list(mobile_devices.keys()))
        return mobile_devices
        
    except Exception as e:
        _LOGGER.error("Failed to get mobile devices: %s", e)
        return {}


async def send_mobile_notification(hass, message, title, mobile_service=None):
    """Send mobile notification with fallback to persistent"""
    if not mobile_service:
        return False
        
    try:
        # Try to send mobile notification
        await hass.services.async_call(
            "notify",
            mobile_service,
            {
                "message": message,
                "title": title,
                "data": {
                    "priority": "high",
                    "ttl": 0,
                    "channel": "Enhanced SunPower"
                }
            }
        )
        _LOGGER.debug("Mobile notification sent successfully via %s", mobile_service)
        return True
        
    except Exception as e:
        _LOGGER.warning("Mobile notification failed via %s: %s", mobile_service, e)
        return False


def safe_notify(hass, message, title="Enhanced SunPower", config_entry=None, 
               force_notify=False, is_general=False, is_debug=False, 
               notification_category="general", cache=None, add_timestamp=True):
    """Enhanced notification system with mobile support"""
    try:
        # Get notification settings from config
        if config_entry:
            show_general = config_entry.options.get("general_notifications", True)
            show_debug = config_entry.options.get("deep_debug_notifications", False)
            overwrite_general = config_entry.options.get("overwrite_general_notifications", True)
            mobile_device = config_entry.options.get("mobile_device")
            mobile_enabled = mobile_device is not None and mobile_device != "none"
        else:
            # Fallback defaults if no config available
            show_general = True
            show_debug = False
            overwrite_general = True
            mobile_enabled = False
            mobile_device = None
        
        # Determine notification level and if it should be shown
        if force_notify:
            # Essential notifications - always shown for safety
            show_notification = True
            notification_type = "critical"
            log_level = "warning"
        elif is_debug and show_debug:
            # Deep debug notifications - only if user enabled
            show_notification = True
            notification_type = "debug"
            log_level = "debug"
        elif is_general and show_general:
            # General status notifications - if user enabled
            show_notification = True
            notification_type = "general"
            log_level = "info"
        else:
            # Skip this notification
            return
        
        if not show_notification:
            return
        
        # Startup notification throttling - prevent spam in first 60 seconds
        if cache and hasattr(cache, 'startup_time'):
            time_since_startup = time.time() - cache.startup_time
            is_startup_period = time_since_startup < 60
            
            if is_startup_period and notification_type in ["general", "debug"]:
                startup_key = f"{notification_type}_{notification_category}_{message.split('.')[0]}"
                
                if startup_key in cache.startup_notifications_sent:
                    _LOGGER.debug("Skipping duplicate startup notification: %s", startup_key)
                    return
                else:
                    cache.startup_notifications_sent.add(startup_key)
        
        # FIXED: Only add timestamp if requested and not already in message
        final_message = message
        if add_timestamp and not any(time_indicator in message for time_indicator in ["@", "ago", "AM", "PM"]):
            timestamp = datetime.now().strftime("%I:%M:%S %p %m-%d-%Y").lstrip("0")
            final_message = f"{message} ({timestamp})"
        
        # Try mobile notification first for critical alerts
        mobile_sent = False
        if mobile_enabled and mobile_device and notification_type == "critical":
            # Use asyncio to send mobile notification
            import asyncio
            try:
                # Create task for mobile notification
                task = asyncio.create_task(
                    send_mobile_notification(hass, message, title, mobile_device)
                )
                # Don't wait for completion - fire and forget
                mobile_sent = True
                _LOGGER.debug("Mobile notification dispatched for critical alert")
            except Exception as e:
                _LOGGER.warning("Failed to dispatch mobile notification: %s", e)
        
        # MULTI-CHANNEL NOTIFICATION ID LOGIC
        if notification_type == "general" and overwrite_general:
            # Multi-channel overwrite - each category gets its own persistent notification
            notification_id = f"enhanced_sunpower_{notification_category}_status"
        elif notification_type == "critical":
            # Critical notifications by category for organization
            notification_id = f"enhanced_sunpower_critical_{notification_category}"
        else:
            # Debug notifications get unique IDs (no overwrite)
            unique_hash = hashlib.md5(f"{title}_{message}_{time.time()}".encode()).hexdigest()[:8]
            notification_id = f"enhanced_sunpower_debug_{unique_hash}"
        
        # Create the persistent notification
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": final_message,
                    "title": title,
                    "notification_id": notification_id
                }
            )
        )
        
        # Log at appropriate level with channel info
        log_message = f"[{notification_category.upper()}] {message}"
        if mobile_sent:
            log_message += " (mobile dispatched)"
            
        if log_level == "warning":
            _LOGGER.warning("Critical notification: %s", log_message)
        elif log_level == "debug":
            _LOGGER.debug("Debug notification: %s", log_message)
        else:
            _LOGGER.info("General notification: %s", log_message)
            
    except Exception as e:
        _LOGGER.warning("Failed to create notification: %s", e)


# ESSENTIAL NOTIFICATIONS (Always Shown - force_notify=True)

def notify_firmware_upgrade(hass, entry, cache, old_version, new_version):
    """ESSENTIAL: PVS firmware upgrade notifications"""
    msg = f"🔄 PVS FIRMWARE UPGRADED: {old_version} → {new_version}"
    # Use unique notification ID so it's never overwritten
    safe_notify(hass, msg, "Enhanced SunPower Firmware", entry, force_notify=True, 
               notification_category="firmware", cache=cache)


def notify_route_missing(hass, entry, cache):
    """ESSENTIAL: Route missing notification"""
    msg = f"🚨 CRITICAL: Route to PVS network missing! Attempting automatic repair..."
    safe_notify(hass, msg, "Enhanced SunPower Route", entry, force_notify=True, 
               notification_category="route", cache=cache)


def notify_route_repaired(hass, entry, cache):
    """ESSENTIAL: Route repair notification"""
    msg = f"✅ ROUTE REPAIRED: PVS network route restored automatically"
    safe_notify(hass, msg, "Enhanced SunPower Route", entry, force_notify=True, 
               notification_category="route", cache=cache)


def notify_pvs_unreachable_route_ok(hass, entry, cache):
    """ESSENTIAL: PVS unreachable but route exists"""
    msg = f"⚠️ PVS UNREACHABLE: Route exists but PVS not responding (hardware issue?)"
    safe_notify(hass, msg, "Enhanced SunPower Status", entry, force_notify=True, 
               notification_category="health", cache=cache)


def notify_pvs_offline(hass, entry, cache, reason):
    """ESSENTIAL: PVS offline notifications"""
    msg = f"🔴 PVS OFFLINE: {reason} - using cached data"
    safe_notify(hass, msg, "Enhanced SunPower Status", entry, force_notify=True, 
               notification_category="health", cache=cache)

def notify_inverter_failure(hass, entry, cache, inverter_serial, consecutive_failures):
    """ESSENTIAL: Inverter failure notifications"""
    msg = f"⚠️ INVERTER FAILURE: {inverter_serial} missing for {consecutive_failures} consecutive polls"
    safe_notify(hass, msg, "Enhanced SunPower Alert", entry, force_notify=True, 
               notification_category="inverter", cache=cache)

def notify_inverter_recovery(hass, entry, cache, inverter_serial, downtime_polls):
    """ESSENTIAL: Inverter recovery notifications"""
    msg = f"✅ INVERTER RECOVERED: {inverter_serial} back online after {downtime_polls} failed polls"
    safe_notify(hass, msg, "Enhanced SunPower Recovery", entry, force_notify=True, 
               notification_category="inverter", cache=cache)

def notify_flash_memory_critical(hass, entry, cache, available_mb, threshold_mb):
    """ESSENTIAL: Flash memory critical alert - UI + mobile"""
    msg = f"⚠️ PVS FLASH MEMORY CRITICAL: {available_mb:.1f}MB remaining (threshold: {threshold_mb}MB)"
    # This is critical hardware protection - always notify + mobile
    safe_notify(hass, msg, "Enhanced SunPower Critical", entry, force_notify=True, 
               notification_category="flash_memory", cache=cache)

def notify_polling_failed(hass, entry, cache, polling_url, error):
    """ESSENTIAL: Polling failure notifications"""
    err_msg = f"❌ Enhanced SunPower polling failed.\nURL: {polling_url}\nError: {str(error)}"
    safe_notify(hass, err_msg, "Enhanced SunPower Error", entry, force_notify=True, 
               notification_category="health", cache=cache)

def notify_setup_warning(hass, entry, cache, polling_url, polling_interval):
    """ESSENTIAL: Setup warning notifications"""
    next_retry_minutes = polling_interval // 60
    retry_text = "1 minute" if next_retry_minutes == 1 else f"{next_retry_minutes} minutes"
    
    warning_msg = (
        f"⚠️ Enhanced SunPower Integration Started with Warnings\n\n"
        f"Initial connection to PVS failed, but integration is running.\n\n"
        f"📡 PVS URL: {polling_url}\n"
        f"🔄 Will retry every {retry_text}\n"
        f"⏰ Persistent polling is active\n"
        f"✅ Integration will recover automatically when PVS responds"
    )
    safe_notify(hass, warning_msg, "Enhanced SunPower Setup", entry, force_notify=True, 
               notification_category="setup", cache=cache)


# GENERAL NOTIFICATIONS - POLLING CHANNEL (is_general=True, category="polling")

def notify_data_update_success(hass, entry, cache, last_poll_timestamp):
    """GENERAL: Successful data update"""
    
    if last_poll_timestamp > 0:
        last_poll_time_str = datetime.fromtimestamp(last_poll_timestamp).strftime("%H:%M:%S")
        msg = f"✅ Fresh data from PVS (poll completed @ {last_poll_time_str})"
        safe_notify(hass, msg, "Enhanced SunPower", entry, is_general=True, 
                   notification_category="polling", cache=cache, add_timestamp=False)
    else:
        msg = "✅ Fresh data from PVS (first poll since restart)"
        safe_notify(hass, msg, "Enhanced SunPower", entry, is_general=True, 
                   notification_category="polling", cache=cache)

def notify_using_cached_data(hass, entry, cache, reason, time_info=None, polling_interval=None):
    """GENERAL: Cached data usage - FIXED TEXT CONVERSION"""
    # Convert state_reason codes to readable text
    readable_reason = convert_state_reason_to_text(reason)

    if time_info:
        if isinstance(time_info, (int, float)):
            # Convert seconds to human-readable time
            time_str = format_time_duration(time_info)
            if polling_interval and reason == "polling_interval_not_elapsed":
                # Special case for interval not elapsed - show the interval setting
                interval_str = format_time_duration(polling_interval)
                msg = f"📦 Using cached data: polling interval set to {interval_str}, last poll {time_str} ago"
            else:
                msg = f"📦 Using cached data: {readable_reason} (last poll {time_str} ago)"
        else:
            # Handle remaining seconds case
            try:
                remaining_seconds = int(time_info)
                remaining_str = format_time_duration(remaining_seconds)
                msg = f"📦 Using cached data: {readable_reason} ({remaining_str} remaining)"
            except (ValueError, TypeError):
                msg = f"📦 Using cached data: {readable_reason} ({time_info} remaining)"
    else:
        msg = f"📦 Using cached data: {readable_reason}"
    safe_notify(hass, msg, "Enhanced SunPower", entry, is_general=True,
               notification_category="polling", cache=cache)


# DEBUG NOTIFICATIONS - SIMPLE DAY/NIGHT LOGIC

def notify_pvs_health_check_attempt(hass, entry, cache, host, max_retries):
    """DEBUG: Health check attempt notification"""
    msg = f"🔍 PVS Health Check: Testing {host} with {max_retries} attempts"
    safe_notify(hass, msg, "Enhanced SunPower Health", entry, is_debug=True, 
               notification_category="health", cache=cache)

def notify_setup_success(hass, entry, cache):
    """DEBUG: Successful setup notification"""
    msg = "✅ Enhanced SunPower integration setup successful"
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True, 
               notification_category="debug", cache=cache)

def notify_day_mode_elevation(hass, entry, cache, elevation, sunrise_elevation, sunset_elevation, active_threshold, state_reason):
    """DEBUG: Polling mode activation notification"""
    if state_reason == "daytime_polling_active":
        msg = f"☀️ Daytime polling enabled: Sun elevation {elevation:.1f}° ≥ {active_threshold:.1f}° threshold"
    elif state_reason == "nighttime_polling_active":
        msg = f"🌙 Nighttime polling enabled: Sun elevation {elevation:.1f}° (consumption tracking active)"
    elif state_reason == "battery_system_active":
        if elevation >= min(sunrise_elevation, sunset_elevation):
            msg = f"🔋 Battery system day polling: Sun elevation {elevation:.1f}° (24/7 monitoring active)"
        else:
            msg = f"🔋 Battery system night polling: Sun elevation {elevation:.1f}° (24/7 monitoring active)"
    else:
        msg = f"☀️ Daytime polling enabled: Sun elevation {elevation:.1f}°"

    safe_notify(hass, msg, "Enhanced SunPower", entry, is_debug=True,
               notification_category="daynight", cache=cache)

def notify_night_mode_elevation(hass, entry, has_battery, cache, elevation, sunrise_elevation, sunset_elevation, active_threshold, state_reason):
    """DEBUG: SIMPLE night mode activation"""
    if has_battery:
        if state_reason == "nighttime_polling_disabled":
            msg = f"🌙 Nighttime mode: Sun elevation {elevation:.1f}° < {active_threshold:.1f}° threshold - battery system continues polling"
        else:
            msg = f"🌙 Nighttime mode: Sun elevation {elevation:.1f}° - battery system continues polling"
    else:
        if state_reason == "nighttime_polling_disabled":
            msg = f"🌙 Nighttime mode: Sun elevation {elevation:.1f}° < {active_threshold:.1f}° threshold - solar polling disabled"
        else:
            msg = f"🌙 Nighttime mode: Sun elevation {elevation:.1f}° - solar polling disabled"
    
    safe_notify(hass, msg, "Enhanced SunPower", entry, is_debug=True, 
               notification_category="daynight", cache=cache)

def notify_diagnostic_coordinator_started(hass, entry, cache):
    """DEBUG: Coordinator cycle started"""
    current_time_str = datetime.now().strftime("%H:%M:%S")
    msg = f"🔄 DIAGNOSTIC: Coordinator cycle started at {current_time_str}"
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True,
               notification_category="debug", cache=cache, add_timestamp=False)

def notify_diagnostic_coordinator_status(hass, entry, cache, current_interval, coordinator_interval, mode, elevation):
    """DEBUG: Enhanced coordinator status with intervals and mode"""
    current_time_str = datetime.now().strftime("%I:%M:%S %p %m-%d-%Y")
    msg = (f"⚙️ COORDINATOR: current={current_interval}s, required={coordinator_interval:.1f}s, "
           f"mode={mode}, elevation={elevation:.1f}° ({current_time_str})")
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True,
               notification_category="debug", cache=cache, add_timestamp=False)

def notify_diagnostic_coordinator_creating(hass, entry, cache, polling_interval):
    """DEBUG: Coordinator creation details"""
    msg = f"⚙️ DIAGNOSTIC: Creating coordinator with {polling_interval}s interval"
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True, 
               notification_category="debug", cache=cache)
