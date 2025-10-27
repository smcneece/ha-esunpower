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


# Removed day/night state conversion - simplified polling only


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


async def get_email_notification_services(hass):
    """Get list of available email notification services"""
    email_services = {}

    try:
        # Get all available services
        services = hass.services.async_services()
        notify_services = services.get('notify', {})

        # Look for specific email notification service patterns only
        email_patterns = [
            'smtp',
            'email',
            'gmail',
            'outlook',
            'sendmail',
            'mailgun',
            'sendgrid',
            'ses',
            'mail'  # Added 'mail' pattern
        ]

        # Services to explicitly exclude (not email)
        exclude_patterns = [
            'alexa',
            'mobile_app_',
            'html5',
            'persistent_notification',
            'telegram',
            'discord',
            'slack',
            'pushbullet',
            'pushover',
            'clicksend',
            'twilio',
            'signal'
        ]

        for service_name in notify_services:
            service_lower = service_name.lower()

            # Skip explicitly excluded services
            if any(pattern in service_lower for pattern in exclude_patterns):
                continue

            # Check for email-related patterns
            is_email_service = any(pattern in service_lower for pattern in email_patterns)

            if is_email_service:
                # Format service name for display
                display_name = service_name.replace('_', ' ').title()
                email_services[service_name] = display_name
            elif service_name not in ['persistent_notification', 'html5']:
                # Include other notify services that might be email (but mark them)
                display_name = service_name.replace('_', ' ').title()
                email_services[service_name] = f"{display_name} (notify service)"

        _LOGGER.debug("All notify services: %s", list(notify_services.keys()))
        _LOGGER.debug("Found %d email services: %s", len(email_services), list(email_services.keys()))
        return email_services

    except Exception as e:
        _LOGGER.error("Failed to get email notification services: %s", e)
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


async def send_email_notification(hass, message, title, email_service=None, email_recipient=None):
    """Send email notification via configured email service"""
    if not email_service or email_service == "none":
        return False

    try:
        # Prepare email data
        email_data = {
            "message": message,
            "title": title,
            "data": {
                "priority": "high"
            }
        }

        # Add custom recipient if provided (non-empty)
        if email_recipient and email_recipient.strip():
            email_data["target"] = email_recipient.strip()
            _LOGGER.debug("Using custom email recipient: %s", email_recipient.strip())
        else:
            _LOGGER.debug("Using email service default recipient (no target specified)")

        # Send email notification
        _LOGGER.debug("Attempting email via service: %s, data: %s", email_service, email_data)
        await hass.services.async_call(
            "notify",
            email_service,
            email_data
        )
        _LOGGER.debug("Email notification sent successfully via %s", email_service)
        return True

    except Exception as e:
        _LOGGER.warning("Email notification failed via %s: %s", email_service, e)
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
            email_service = config_entry.options.get("email_notification_service")
            email_enabled = email_service is not None and email_service != "none"
            email_recipient = config_entry.options.get("email_notification_recipient", "")
        else:
            # Fallback defaults if no config available
            show_general = True
            show_debug = False
            overwrite_general = True
            mobile_enabled = False
            mobile_device = None
            email_service = None
            email_enabled = False
            email_recipient = ""
        
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
                    cache.startup_notifications_sent[startup_key] = True  # Dict, not set
        
        # FIXED: Only add timestamp if requested and not already in message
        final_message = message
        if add_timestamp and not any(time_indicator in message for time_indicator in ["@", "ago", "AM", "PM"]):
            timestamp = datetime.now().strftime("%I:%M:%S %p %m-%d-%Y").lstrip("0")
            final_message = f"{message} ({timestamp})"
        
        # Try mobile and email notifications first for critical alerts
        mobile_sent = False
        email_sent = False

        if notification_type == "critical":
            import asyncio

            # Try mobile notification
            if mobile_enabled and mobile_device:
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

            # Try email notification
            _LOGGER.debug("Email check: enabled=%s, service=%s, type=%s", email_enabled, email_service, notification_type)
            if email_enabled and email_service and email_service != "none":
                try:
                    _LOGGER.info("Dispatching email notification for critical alert")
                    # Create task for email notification
                    task = asyncio.create_task(
                        send_email_notification(hass, message, title, email_service, email_recipient)
                    )
                    # Don't wait for completion - fire and forget
                    email_sent = True
                    _LOGGER.info("Email notification dispatched for critical alert")
                except Exception as e:
                    _LOGGER.warning("Failed to dispatch email notification: %s", e)
            else:
                _LOGGER.debug("Email notification skipped: enabled=%s, service=%s", email_enabled, email_service)
        
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



# notify_pvs_offline function removed - unused function

# Legacy individual notification functions removed - replaced by notify_batched_inverter_issues()




def notify_batched_inverter_issues(hass, entry, cache, persistent_errors, recoveries):
    """ESSENTIAL: Batched inverter notifications for UI, mobile, and email"""
    messages = []

    # Build persistent error message
    if persistent_errors:
        if len(persistent_errors) == 1:
            error = persistent_errors[0]
            messages.append(f"🔴 PERSISTENT INVERTER ISSUE: {error['serial']} in error state for {error['duration_hours']} hours")
        else:
            error_serials = [error['serial'] for error in persistent_errors]
            max_hours = max(error['duration_hours'] for error in persistent_errors)
            messages.append(f"🔴 PERSISTENT INVERTER ISSUES: {len(persistent_errors)} inverters in error state for 24+ hours ({', '.join(error_serials[:3])}{'...' if len(error_serials) > 3 else ''})")

    # Build recovery message
    if recoveries:
        if len(recoveries) == 1:
            recovery = recoveries[0]
            messages.append(f"✅ INVERTER RECOVERED: {recovery['serial']} back online after {recovery['duration_hours']} hours")
        else:
            recovery_serials = [recovery['serial'] for recovery in recoveries]
            messages.append(f"✅ INVERTERS RECOVERED: {len(recoveries)} inverters back online ({', '.join(recovery_serials[:3])}{'...' if len(recovery_serials) > 3 else ''})")

    # Send combined message
    if messages:
        combined_message = " | ".join(messages)
        title = "Enhanced SunPower Critical Alert" if persistent_errors else "Enhanced SunPower Recovery"
        safe_notify(hass, combined_message, title, entry, force_notify=True,
                   notification_category="inverter", cache=cache)

def notify_flash_memory_critical(hass, entry, cache, serial, available_mb, threshold_mb):
    """ESSENTIAL: Flash memory critical alert - UI + mobile"""
    msg = f"⚠️ PVS {serial} FLASH MEMORY CRITICAL: {available_mb:.1f}MB remaining (threshold: {threshold_mb:.0f}MB)"
    # This is critical hardware protection - always notify + mobile
    safe_notify(hass, msg, "Enhanced SunPower Critical Alert", entry, force_notify=True,
               notification_category="flash_memory", cache=cache)

def notify_flash_wear_critical(hass, entry, cache, serial, wear_pct, threshold_pct, remaining_pct):
    """ESSENTIAL: Flash wear critical alert - UI + mobile"""
    msg = f"⚠️ PVS {serial} FLASH WEAR CRITICAL: {wear_pct}% used / {remaining_pct}% remaining (threshold: {threshold_pct}%)"
    # This is critical hardware protection - always notify + mobile
    safe_notify(hass, msg, "Enhanced SunPower Critical Alert", entry, force_notify=True,
               notification_category="flash_wear", cache=cache)

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

def test_email_notification(hass, entry, cache):
    """TEST: Send test email notification to verify configuration"""
    msg = "📧 TEST: Email notification system is working correctly!"
    safe_notify(hass, msg, "Enhanced SunPower Email Test", entry, force_notify=True,
               notification_category="email_test", cache=cache)

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
    # Check if polling is disabled via switch
    polling_enabled = entry.options.get("polling_enabled", True)
    if not polling_enabled:
        msg = "📦 Using cached data: Polling disabled by user (switch off) - PVS not being polled"
        safe_notify(hass, msg, "Enhanced SunPower", entry, is_general=True,
                   notification_category="polling", cache=cache)
        return

    # Simplified polling - just use reason directly
    readable_reason = reason

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

def notify_inverters_discovered(hass, entry, cache, inverter_count):
    """ESSENTIAL: Notify when inverters are discovered after initial setup"""
    msg = (f"☀️ Inverters Detected!\n\n"
           f"Enhanced SunPower has discovered {inverter_count} inverter{'s' if inverter_count != 1 else ''} "
           f"and created all sensor entities.\n\n"
           f"Your solar system is now fully monitored.")
    
    safe_notify(hass, msg, "Enhanced SunPower Setup", entry, force_notify=True,
               notification_category="setup", cache=cache)

# Removed day/night elevation notification functions - simplified polling only

def notify_diagnostic_coordinator_started(hass, entry, cache):
    """DEBUG: Coordinator cycle started"""
    current_time_str = datetime.now().strftime("%H:%M:%S")
    msg = f"🔄 DIAGNOSTIC: Coordinator cycle started at {current_time_str}"
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True,
               notification_category="debug", cache=cache, add_timestamp=False)

def notify_diagnostic_coordinator_status(hass, entry, cache, current_interval, coordinator_interval, mode):
    """DEBUG: Simplified coordinator status"""
    current_time_str = datetime.now().strftime("%I:%M:%S %p %m-%d-%Y")
    msg = (f"⚙️ COORDINATOR: interval={current_interval}s, simplified_polling "
           f"({current_time_str})")
    safe_notify(hass, msg, "Enhanced SunPower Debug", entry, is_debug=True,
               notification_category="debug", cache=cache, add_timestamp=False)

# notify_diagnostic_coordinator_creating function removed - imported but never called

def notify_battery_system_issue(hass, entry, cache, consecutive_failures):
    """ESSENTIAL: Battery system connectivity issues"""
    msg = (f"⚠️ SunVault Connectivity Issue\n\n"
           f"{consecutive_failures} consecutive polling failures detected. "
           f"Battery data may be temporarily unavailable.\n\n"
           f"This usually resolves automatically - if persistent, check network connectivity.")

    safe_notify(hass, msg, "Enhanced SunPower Battery Alert", entry, force_notify=True,
               notification_category="battery", cache=cache)

async def notify_polling_disabled(hass, entry, serial):
    """INFO: Polling disabled notification"""
    msg = (f"⏸️ PVS Polling Disabled\n\n"
           f"PVS {serial} will not be polled until polling is re-enabled.\n\n"
           f"Entities will retain last known values. "
           f"Use this to reduce PVS disk I/O during nighttime hours.")

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "message": msg,
            "title": "Enhanced SunPower Polling Status",
            "notification_id": f"sunpower_polling_disabled_{serial}"
        },
        blocking=False
    )

async def notify_polling_enabled(hass, entry, serial):
    """INFO: Polling enabled notification"""
    msg = (f"▶️ PVS Polling Enabled\n\n"
           f"PVS {serial} polling has been resumed.\n\n"
           f"Normal data collection will continue.")

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "message": msg,
            "title": "Enhanced SunPower Polling Status",
            "notification_id": f"sunpower_polling_enabled_{serial}"
        },
        blocking=False
    )
