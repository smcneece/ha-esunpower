"""Diagnostics support for Enhanced SunPower integration."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    SUNPOWER_COORDINATOR,
    SUNPOWER_HOST,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # Get coordinator from hass data
    coordinator = hass.data[DOMAIN][entry.entry_id][SUNPOWER_COORDINATOR]

    # Get cache object for diagnostic stats and raw PVS data
    cache = hass.data[DOMAIN][entry.entry_id].get("_cache")

    # Build diagnostic data - use defensive access for all keys
    diagnostics = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "host": entry.data.get("host", entry.options.get("host", "unknown")),
            "polling_interval": entry.options.get("polling_interval", entry.data.get("polling_interval", "unknown")),
            "password_configured": bool(entry.data.get("password", "")),
            "mobile_device": entry.options.get("mobile_device", entry.data.get("mobile_device", "not configured")),
            "flash_threshold_mb": entry.options.get("flash_threshold_mb", entry.data.get("flash_threshold_mb", "not configured")),
            "enable_debug_notifications": entry.options.get("enable_debug_notifications", entry.data.get("enable_debug_notifications", False)),
            "enable_route_checking": entry.options.get("enable_route_checking", entry.data.get("enable_route_checking", False)),
            "gateway_ip": entry.options.get("gateway_ip", entry.data.get("gateway_ip", "not configured")),
        },
        "coordinator_state": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
        },
        "device_summary": {},
        "diagnostic_stats": {},
        "raw_pvs_data": None,
    }

    # Add device count summary from coordinator data
    if coordinator.data:
        device_types = {}
        for device_type, devices in coordinator.data.items():
            if isinstance(devices, dict) and device_type != "_cache":
                device_types[device_type] = {
                    "count": len(devices),
                    "serials": list(devices.keys()),
                }
        diagnostics["device_summary"] = device_types

    # Access cache data for detailed diagnostics
    if cache:
        try:
            # Add diagnostic stats
            if hasattr(cache, "diagnostic_stats"):
                stats = cache.diagnostic_stats
                diagnostics["diagnostic_stats"] = {
                    "total_polls": stats.get("total_polls", 0),
                    "successful_polls": stats.get("successful_polls", 0),
                    "failed_polls": stats.get("failed_polls", 0),
                    "consecutive_failures": stats.get("consecutive_failures", 0),
                    "success_rate_percent": (stats.get("successful_polls", 0) / stats.get("total_polls", 1)) * 100 if stats.get("total_polls", 0) > 0 else 0,
                    "average_response_time_seconds": stats.get("average_response_time", 0),
                    "last_success_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.get("last_success_time", 0))) if stats.get("last_success_time", 0) > 0 else "Never",
                    "integration_uptime_seconds": time.time() - stats.get("integration_start_time", time.time()),
                }

            # Add raw PVS data (most recent sample)
            if hasattr(cache, "previous_pvs_sample") and cache.previous_pvs_sample:
                diagnostics["raw_pvs_data"] = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cache.previous_pvs_sample_time)) if hasattr(cache, "previous_pvs_sample_time") else "unknown",
                    "data": cache.previous_pvs_sample,
                }

            # Add inverter health tracking
            if hasattr(cache, "expected_inverters"):
                diagnostics["inverter_health"] = {
                    "expected_inverters": list(cache.expected_inverters) if cache.expected_inverters else [],
                    "failure_counts": cache.inverter_failure_counts if hasattr(cache, "inverter_failure_counts") else {},
                }

            # Add battery detection status
            if hasattr(cache, "battery_detected_once"):
                diagnostics["battery_detection"] = {
                    "battery_detected": cache.battery_detected_once,
                }

            # Add firmware tracking
            if hasattr(cache, "last_known_firmware"):
                diagnostics["firmware"] = {
                    "last_known_build": cache.last_known_firmware,
                }
        except Exception as e:
            diagnostics["cache_error"] = f"Could not access cache data: {str(e)}"

    return diagnostics
