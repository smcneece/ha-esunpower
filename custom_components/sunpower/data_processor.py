"""SunPower Data Processing Module - FINAL (No Coordinator References)

This module handles all data conversion and validation logic:
- Raw PVS JSON → Structured device data
- Virtual meter creation from inverter data (IP-safe)
- Comprehensive data validation and error handling
- Complete IP address detection across all ranges
- FIXED: No coordinator references or hardcoded values
"""

import logging
import ipaddress

from .const import (
    INVERTER_DEVICE_TYPE,
    METER_DEVICE_TYPE,
    PVS_DEVICE_TYPE,
    TRANSFER_SWITCH_DEVICE_TYPE,
)

_LOGGER = logging.getLogger(__name__)


def is_ip_address(serial):
    """Bulletproof IP address detection for all ranges"""
    try:
        # Handle None or non-string inputs
        if not serial or not isinstance(serial, str):
            return False
        
        # Try to parse as IP address
        ip = ipaddress.ip_address(serial.strip())
        
        # Check if it's a private IP address (most common for PVS)
        if ip.is_private:
            _LOGGER.debug("Detected private IP address: %s", serial)
            return True
        
        # Check if it's any other valid IP address
        _LOGGER.debug("Detected IP address: %s", serial)
        return True
        
    except (ipaddress.AddressValueError, ValueError, AttributeError):
        # Not an IP address
        return False


def generate_safe_virtual_serial(base_name, device_type):
    """Generate a safe serial name that won't create zombies"""
    import time
    timestamp = int(time.time())
    
    # Create unique, non-IP serial names
    safe_serial = f"{base_name}_{device_type.lower()}_{timestamp}"
    
    # Double-check it's not accidentally an IP
    if is_ip_address(safe_serial):
        # Extremely unlikely, but add extra suffix if needed
        safe_serial = f"safe_{safe_serial}_virtual"
    
    return safe_serial


def create_vmeter(data):
    """Create a virtual 'METER' that uses the sum of inverters - IP-SAFE VERSION"""
    kwh = 0.0
    kw = 0.0
    amps = 0.0
    freq = []
    volts = []
    state = "working"

    inverters = data.get(INVERTER_DEVICE_TYPE, {})
    if not inverters:
        _LOGGER.warning("No inverters found for virtual meter creation")
        return data

    # Calculate aggregated values from all inverters
    for _serial, inverter in inverters.items():
        try:
            if "STATE" in inverter and inverter["STATE"] != "working":
                state = inverter["STATE"]
            kwh += float(inverter.get("ltea_3phsum_kwh", "0"))
            kw += float(inverter.get("p_mppt1_kw", "0"))
            amps += float(inverter.get("i_3phsum_a", "0"))
            if "freq_hz" in inverter:
                freq.append(float(inverter["freq_hz"]))
            if "vln_3phavg_v" in inverter:
                volts.append(float(inverter["vln_3phavg_v"]))
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Error processing inverter %s data: %s", _serial, e)
            continue

    freq_avg = sum(freq) / len(freq) if len(freq) > 0 else 60.0
    volts_avg = sum(volts) / len(volts) if len(volts) > 0 else 240.0

    pvs_devices = data.get(PVS_DEVICE_TYPE, {})
    if not pvs_devices:
        _LOGGER.error("No PVS devices found for virtual meter creation")
        return data

    pvs_serial = next(iter(pvs_devices))
    
    # BULLETPROOF IP DETECTION: Check all IP address ranges
    if is_ip_address(pvs_serial):
        # PVS has IP address as serial - use completely safe alternative naming
        vmeter_serial = generate_safe_virtual_serial("virtual_production_meter", "meter")
        _LOGGER.warning("PVS has IP-based serial (%s), using safe virtual meter name: %s", 
                       pvs_serial, vmeter_serial)
    else:
        # Real PVS serial - safe to create virtual meter with "pv" suffix
        vmeter_serial = f"{pvs_serial}pv"
        
        # Double-check the result isn't accidentally an IP
        if is_ip_address(vmeter_serial):
            vmeter_serial = generate_safe_virtual_serial("virtual_production_meter", "meter")
            _LOGGER.warning("Virtual meter serial became IP-like, using safe alternative: %s", vmeter_serial)
        else:
            _LOGGER.debug("Creating virtual meter with real PVS serial: %s", vmeter_serial)
    
    # Create the virtual meter device
    try:
        data.setdefault(METER_DEVICE_TYPE, {})[vmeter_serial] = {
            "SERIAL": vmeter_serial,
            "TYPE": "PVS-METER-P",
            "STATE": state,
            "MODEL": "Virtual Production Meter",
            "DESCR": f"Virtual Production Meter {vmeter_serial}",
            "DEVICE_TYPE": "Power Meter",
            "interface": "virtual",
            "SWVER": "1.0",
            "HWVER": "Virtual",
            "origin": "virtual",
            # Fixed field names to match real power meters
            # Round lifetime energy to 2 decimals to prevent float jitter (HA total_increasing requirement)
            "net_ltea_3phsum_kwh": round(kwh, 2),  # Lifetime Power
            "p_3phsum_kw": kw,  # Power
            "neg_ltea_3phsum_kwh": round(kwh, 2),  # kWh To Grid (production meter shows all as export)
            "freq_hz": freq_avg,  # Frequency
            "i_a": amps,  # Amps
            "v12_v": volts_avg,  # Supply Volts
            # Additional diagnostic fields
            "s_3phsum_kva": kw,  # Apparent Power (simplified as kW for virtual meter)
            "tot_pf_rto": 1.0,  # Power Factor (assume perfect for solar production)
        }
        
        _LOGGER.info("Created virtual meter: %s (aggregated from %d inverters)", 
                    vmeter_serial, len(inverters))
    except Exception as e:
        _LOGGER.error("Failed to create virtual meter: %s", e)
    
    return data


def convert_sunpower_data(sunpower_data):
    """Convert PVS data into indexable format with bulletproof error handling
    
    Args:
        sunpower_data: Raw JSON data from PVS device_list endpoint
        
    Returns:
        dict: Structured data in format {device_type: {serial: device_data}}
        
    Example:
        Input: {"devices": [{"DEVICE_TYPE": "Inverter", "SERIAL": "ABC123", ...}]}
        Output: {"Inverter": {"ABC123": {"DEVICE_TYPE": "Inverter", ...}}}
    """
    data = {}
    
    # Bulletproof data validation
    try:
        if not sunpower_data:
            _LOGGER.error("convert_sunpower_data: sunpower_data is None or empty")
            return data
        
        if not isinstance(sunpower_data, dict):
            _LOGGER.error("convert_sunpower_data: sunpower_data is not a dict: %s", type(sunpower_data))
            return data
        
        if "devices" not in sunpower_data:
            _LOGGER.error("convert_sunpower_data: No 'devices' key in sunpower_data: %s", 
                         list(sunpower_data.keys()) if isinstance(sunpower_data, dict) else "N/A")
            return data
        
        devices = sunpower_data["devices"]
        if not isinstance(devices, list):
            _LOGGER.error("convert_sunpower_data: 'devices' is not a list: %s", type(devices))
            return data
        
        if not devices:
            _LOGGER.error("convert_sunpower_data: devices list is empty")
            return data
        
        _LOGGER.debug("convert_sunpower_data: Processing %d devices", len(devices))
        
    except Exception as e:
        _LOGGER.error("convert_sunpower_data: Validation failed: %s", e)
        return data
    
    # Process each device with comprehensive error handling
    device_count = 0
    for i, device in enumerate(devices):
        try:
            if not isinstance(device, dict):
                _LOGGER.warning("convert_sunpower_data: Device %d is not a dict: %s", i, type(device))
                continue
            
            device_type = device.get("DEVICE_TYPE")
            device_serial = device.get("SERIAL")
            
            if not device_type:
                _LOGGER.warning("convert_sunpower_data: Device %d missing DEVICE_TYPE: %s", i, 
                               str(device)[:100] if device else "None")
                continue
            
            if not device_serial:
                _LOGGER.warning("convert_sunpower_data: Device %d missing SERIAL: %s", i, 
                               str(device)[:100] if device else "None")
                continue
            
            # Validate device serial is reasonable (not obviously corrupted)
            if len(str(device_serial)) > 50:
                _LOGGER.warning("convert_sunpower_data: Device %d has suspiciously long serial: %s", 
                               i, str(device_serial)[:50])
                continue
            
            # Add device to data structure
            data.setdefault(device_type, {})[device_serial] = device
            device_count += 1
            
        except Exception as e:
            _LOGGER.warning("convert_sunpower_data: Error processing device %d: %s", i, e)
            continue
    
    if device_count == 0:
        _LOGGER.error("convert_sunpower_data: No valid devices processed from %d input devices", len(devices))
        return data
    
    _LOGGER.debug("convert_sunpower_data: Successfully processed %d devices", device_count)
    
    # Log device type summary for diagnostics
    try:
        device_types = []
        for device_type, devices_dict in data.items():
            device_types.append(f"{device_type}: {len(devices_dict)}")
        _LOGGER.info("convert_sunpower_data: Device types found: %s", ", ".join(device_types))
    except Exception as e:
        _LOGGER.warning("Device type summary failed: %s", e)
    
    # Create virtual meter with bulletproof error handling
    if PVS_DEVICE_TYPE in data and INVERTER_DEVICE_TYPE in data:
        try:
            create_vmeter(data)
            _LOGGER.debug("convert_sunpower_data: Virtual meter created successfully")
        except Exception as e:
            _LOGGER.error("convert_sunpower_data: Failed to create virtual meter: %s", e)
    else:
        missing_types = []
        if PVS_DEVICE_TYPE not in data:
            missing_types.append(PVS_DEVICE_TYPE)
        if INVERTER_DEVICE_TYPE not in data:
            missing_types.append(INVERTER_DEVICE_TYPE)
        _LOGGER.warning("convert_sunpower_data: Cannot create virtual meter - missing device types: %s", 
                       missing_types)
    
    return data


def validate_converted_data(data):
    """Validate that converted data is properly structured with bulletproof error handling
    
    Args:
        data: Converted data from convert_sunpower_data()
        
    Returns:
        tuple: (is_valid, device_count, error_message)
    """
    try:
        if not data:
            return False, 0, "No data provided"
        
        if not isinstance(data, dict):
            return False, 0, f"Data is not a dict: {type(data)}"
        
        # Count total devices (excluding status fields and metadata)
        device_count = 0
        try:
            for device_type, devices in data.items():
                # Skip any metadata fields that might start with underscore
                if str(device_type).startswith('_'):
                    continue
                
                if not isinstance(devices, dict):
                    return False, 0, f"Device type '{device_type}' is not a dict: {type(devices)}"
                
                # Validate each device has minimum required fields
                for serial, device_data in devices.items():
                    if not isinstance(device_data, dict):
                        return False, 0, f"Device '{serial}' data is not a dict: {type(device_data)}"
                    
                    if "DEVICE_TYPE" not in device_data:
                        return False, 0, f"Device '{serial}' missing DEVICE_TYPE"
                    
                    if "SERIAL" not in device_data:
                        return False, 0, f"Device '{serial}' missing SERIAL field"
                
                device_count += len(devices)
                
        except Exception as e:
            return False, 0, f"Error counting devices: {e}"
        
        if device_count == 0:
            return False, 0, "No devices found in converted data"
        
        # Check for minimum expected device types
        required_types = [PVS_DEVICE_TYPE]
        missing_required = [dt for dt in required_types if dt not in data]
        if missing_required:
            return False, device_count, f"Missing required device types: {missing_required}"
        
        return True, device_count, "Data validation successful"
        
    except Exception as e:
        return False, 0, f"Validation failed with exception: {e}"


def get_device_summary(data):
    """Get a summary of devices in the converted data with error protection
    
    Args:
        data: Converted data from convert_sunpower_data()
        
    Returns:
        dict: Summary with device counts by type
    """
    summary = {}
    
    try:
        if not data or not isinstance(data, dict):
            return summary
        
        for device_type, devices in data.items():
            # Skip metadata fields
            if str(device_type).startswith('_'):
                continue
                
            if isinstance(devices, dict):
                summary[device_type] = len(devices)
    except Exception as e:
        _LOGGER.warning("Device summary generation failed: %s", e)
    
    return summary


# EXPORT ALL REQUIRED FUNCTIONS for other modules
__all__ = [
    'convert_sunpower_data',
    'validate_converted_data', 
    'get_device_summary',
    'create_vmeter',
    'is_ip_address'
]

#