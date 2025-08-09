"""SunPower PVS Health Check Module with Route Check Integration"""

import asyncio
import logging
import time

_LOGGER = logging.getLogger(__name__)


async def check_route_exists(target_network="172.27.153.0/24"):
    """Check if route to PVS network exists in routing table"""
    try:
        result = await asyncio.create_subprocess_exec(
            'ip', 'route', 'show', target_network,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5.0)
        
        # Check if route exists in output
        route_exists = target_network.encode() in stdout
        _LOGGER.debug("Route check for %s: exists=%s", target_network, route_exists)
        return route_exists
        
    except asyncio.TimeoutError:
        _LOGGER.warning("Route check timed out")
        return False
    except Exception as e:
        _LOGGER.warning("Route check failed: %s", e)
        return False


async def add_pvs_route(target_network="172.27.153.0/24", gateway=None):
    """Add route to PVS network with configurable gateway"""
    if gateway is None:
        gateway = "192.168.1.80"  # Default fallback
        
    try:
        result = await asyncio.create_subprocess_exec(
            'ip', 'route', 'add', target_network, 'via', gateway,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10.0)
        
        if result.returncode == 0:
            _LOGGER.info("Successfully added route: %s via %s", target_network, gateway)
            return True
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            _LOGGER.error("Failed to add route: %s", error_msg)
            return False
            
    except asyncio.TimeoutError:
        _LOGGER.error("Route add command timed out")
        return False
    except Exception as e:
        _LOGGER.error("Route add failed: %s", e)
        return False


async def tcp_connect_test(host, port=80, timeout=2):
    """Fast TCP connect test to check if PVS is reachable"""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False


async def smart_pvs_health_check(host, cache, hass, entry, max_retries=2, backoff_minutes=1):
    """
    Smart PVS health check with optional route checking
    Returns: 'healthy', 'unreachable', 'backoff', 'route_fixed'
    """
    # Import notification functions locally to avoid circular imports
    from .notifications import notify_pvs_health_check_attempt, notify_route_missing, notify_route_repaired
    
    current_time = time.time()  # Use regular time
    
    # Check if we're in backoff period
    if current_time < cache.health_backoff_until:
        remaining = int(cache.health_backoff_until - current_time)
        _LOGGER.debug("PVS health check in backoff period, %d seconds remaining", remaining)
        return 'backoff'
    
    # Show health check attempt (DEBUG level)
    notify_pvs_health_check_attempt(hass, entry, cache, host, max_retries)
    
    # Get user's polling interval for adaptive timeout
    polling_interval = max(300, entry.options.get("polling_interval_seconds", entry.data.get("polling_interval_seconds", 300)))
    tcp_timeout = min(5.0, polling_interval // 10)
    
    # Perform TCP connect test with retries
    tcp_success = False
    for attempt in range(max_retries):
        _LOGGER.debug("PVS health check attempt %d/%d for %s (timeout: %.1fs)", 
                     attempt + 1, max_retries, host, tcp_timeout)
        
        if await tcp_connect_test(host, timeout=tcp_timeout):
            tcp_success = True
            break
        
        # Failed - wait 1 second before retry (except on last attempt)
        if attempt < max_retries - 1:
            await asyncio.sleep(1)
    
    # TCP test results
    if tcp_success:
        # Success - reset failure counter
        if cache.pvs_health_failures > 0:
            _LOGGER.info("PVS health check recovered after %d failures", cache.pvs_health_failures)
            cache.pvs_health_failures = 0
        cache.last_health_check = current_time
        return 'healthy'
    
    # TCP failed - check if route checking is enabled
    route_check_enabled = entry.options.get("route_check_enabled", False)
    
    if route_check_enabled:
        _LOGGER.info("TCP failed, checking route status (route check enabled)")
        
        # Check if route exists
        route_exists = await check_route_exists()
        
        if not route_exists:
            # Route is missing - this explains the TCP failure
            _LOGGER.error("CRITICAL: Route to PVS network is missing!")
            notify_route_missing(hass, entry, cache)
            
            # Get user's configured gateway (with fallback)
            gateway_ip = entry.options.get("route_gateway_ip", "192.168.1.80")
            
            # Attempt to repair the route
            _LOGGER.info("Attempting to repair missing route using gateway %s...", gateway_ip)
            route_added = await add_pvs_route(gateway=gateway_ip)
            
            if route_added:
                _LOGGER.info("Route repair successful, testing PVS connection...")
                notify_route_repaired(hass, entry, cache)
                
                # Test TCP again after route repair
                if await tcp_connect_test(host, timeout=tcp_timeout):
                    _LOGGER.info("PVS reachable after route repair!")
                    cache.pvs_health_failures = 0
                    cache.last_health_check = current_time
                    return 'route_fixed'
                else:
                    _LOGGER.warning("PVS still unreachable after route repair")
            else:
                _LOGGER.error("Route repair failed")
        else:
            # Route exists but TCP still fails - PVS actually down
            _LOGGER.warning("Route exists but PVS unreachable - PVS likely offline")
            from .notifications import notify_pvs_unreachable_route_ok
            notify_pvs_unreachable_route_ok(hass, entry, cache)
    else:
        _LOGGER.debug("TCP failed, route checking disabled")
    
    # All TCP attempts failed
    cache.pvs_health_failures += 1
    cache.last_health_check = current_time
    
    # Set backoff period using regular time
    cache.health_backoff_until = current_time + (backoff_minutes * 60)
    
    _LOGGER.warning("PVS health check failed after %d attempts, backing off for %d minutes", 
                   max_retries, backoff_minutes)
    
    return 'unreachable'


def initialize_inverter_tracking(cache, inverter_data):
    """Initialize inverter health tracking from first successful poll"""
    if not hasattr(cache, 'inverter_health_initialized') or not cache.inverter_health_initialized:
        # Get all inverter serials from current data
        inverter_serials = set(inverter_data.keys())
        
        # Initialize tracking dictionaries
        cache.expected_inverters = inverter_serials.copy()
        cache.inverter_failure_counts = {serial: 0 for serial in inverter_serials}
        cache.inverter_health_initialized = True
        
        _LOGGER.info("Initialized inverter health tracking for %d inverters: %s", 
                    len(inverter_serials), sorted(list(inverter_serials)))
        
        return len(inverter_serials)
    
    return len(cache.expected_inverters)


def check_inverter_health(hass, entry, cache, current_inverter_data):
    """
    Check inverter health and send notifications for failures/recoveries
    Smart adaptation to new inverters and panel changes
    """
    # Import notification functions locally to avoid circular imports
    from .notifications import notify_inverter_failure, notify_inverter_recovery
    
    if not current_inverter_data:
        _LOGGER.debug("No inverter data provided for health check")
        return
    
    # Initialize tracking if this is the first successful poll
    total_inverters = initialize_inverter_tracking(cache, current_inverter_data)
    
    current_serials = set(current_inverter_data.keys())
    expected_serials = cache.expected_inverters.copy()
    
    # Check for missing inverters (failure detection)
    missing_inverters = expected_serials - current_serials
    for missing_serial in missing_inverters:
        # Increment failure count
        cache.inverter_failure_counts[missing_serial] += 1
        failure_count = cache.inverter_failure_counts[missing_serial]
        
        _LOGGER.debug("Inverter %s missing (failure count: %d)", missing_serial, failure_count)
        
        # Send alert after 5 consecutive failures
        if failure_count == 5:
            _LOGGER.warning("Inverter %s has failed 5 consecutive polls - sending alert", missing_serial)
            notify_inverter_failure(hass, entry, cache, missing_serial, failure_count)
    
    # Check for recovered inverters
    present_inverters = current_serials & expected_serials
    for present_serial in present_inverters:
        if cache.inverter_failure_counts.get(present_serial, 0) >= 5:
            # This inverter was considered failed but is now back
            downtime_polls = cache.inverter_failure_counts[present_serial]
            cache.inverter_failure_counts[present_serial] = 0
            
            _LOGGER.info("Inverter %s recovered after %d failed polls", present_serial, downtime_polls)
            notify_inverter_recovery(hass, entry, cache, present_serial, downtime_polls)
        else:
            # Reset failure count for present inverters
            cache.inverter_failure_counts[present_serial] = 0
    
    # Smart adaptation - detect new inverters (panel replacements)
    new_inverters = current_serials - expected_serials
    if new_inverters:
        _LOGGER.info("Detected %d new inverters (panel replacements?): %s", 
                    len(new_inverters), sorted(list(new_inverters)))
        
        # Add new inverters to tracking
        for new_serial in new_inverters:
            cache.expected_inverters.add(new_serial)
            cache.inverter_failure_counts[new_serial] = 0
        
        # Optional: Remove inverters that have been missing for a very long time (30+ failures)
        # This handles permanent panel removals vs temporary communication issues
        permanently_missing = []
        for serial, failure_count in cache.inverter_failure_counts.items():
            if failure_count >= 30 and serial not in current_serials:
                permanently_missing.append(serial)
        
        if permanently_missing:
            _LOGGER.info("Removing %d permanently missing inverters from tracking: %s", 
                        len(permanently_missing), permanently_missing)
            for serial in permanently_missing:
                cache.expected_inverters.discard(serial)
                cache.inverter_failure_counts.pop(serial, None)
    
    # Log health summary (debug level)
    active_count = len(present_inverters)
    missing_count = len(missing_inverters)
    new_count = len(new_inverters)
    
    _LOGGER.debug("Inverter health: %d active, %d missing, %d new (total expected: %d)", 
                 active_count, missing_count, new_count, len(cache.expected_inverters))


def get_inverter_health_summary(cache):
    """Get a summary of current inverter health status"""
    if not hasattr(cache, 'inverter_health_initialized') or not cache.inverter_health_initialized:
        return "Inverter health tracking not initialized"
    
    total_expected = len(cache.expected_inverters)
    failed_count = sum(1 for count in cache.inverter_failure_counts.values() if count >= 5)
    warning_count = sum(1 for count in cache.inverter_failure_counts.values() if 1 <= count < 5)
    healthy_count = total_expected - failed_count - warning_count
    
    return {
        "total_expected": total_expected,
        "healthy": healthy_count,
        "warning": warning_count,  # 1-4 consecutive failures
        "failed": failed_count,    # 5+ consecutive failures
        "failure_counts": cache.inverter_failure_counts.copy()
    }
