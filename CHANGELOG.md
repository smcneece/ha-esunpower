# Changelog

All notable changes to the Enhanced SunPower Home Assistant Integration will be documented in this file.

## [v2025.10.10] - 2025-10-04

### Critical Fix: Firmware Auto-Detection in Options Flow

**Problem:**
- Integrations created before firmware detection was added were missing `firmware_build` and `uses_pypvs` fields
- Without these fields, integration defaulted to old firmware mode (no authentication)
- Serial number was saved but ignored because uses_pypvs=False
- Caused "Authentication required but no PVS serial provided" errors

**Fix:**
- Options flow now auto-detects firmware from supervisor/info during reconfigure
- Automatically saves firmware_build and uses_pypvs to entry.data
- Upgrades existing integrations to have proper firmware detection

**Files Modified:**
- `config_flow.py`:
  - Added firmware auto-detection in OptionsFlowHandler (lines 490-499)
  - Save firmware_build and uses_pypvs to entry.data (lines 602-605)

## [v2025.10.9] - 2025-10-04

### Critical Bug Fix: Reconfigure Serial Not Saved

**Problem:**
- PVS serial number entered via Reconfigure was validated but never saved to configuration
- User could see serial in UI but code couldn't find it during authentication
- Caused "Authentication required but no PVS serial provided" errors

**Fix:**
- Added `pvs_serial_last5` to options dict in OptionsFlowHandler (config_flow.py line 613)
- Serial now properly saved when user reconfigures integration
- Works with existing serial lookup code that checks both entry.options and entry.data

**Files Modified:**
- `config_flow.py`: Added serial to options dict (line 613)

## [v2025.10.8] - 2025-10-04

### Diagnostic Fixes, Memory/Flash Percentage Support & Configuration Bug Fix

**Configuration Bug Fix:**
- **Reconfigure Serial Number**: Fixed authentication failing when PVS serial entered via Reconfigure instead of initial setup
- **Smart Lookup**: Code now checks both `entry.options` (reconfigure) and `entry.data` (initial setup) for serial number
- **Impact**: New firmware users can now update serial number via reconfigure without "Authentication required" errors

**Diagnostic Tracking Fixes:**
- **Poll Success Rate Now Accurate**: Fixed order-of-operations bug where diagnostic device was created BEFORE updating success stats
- **Cached Data Counted as Success**: Coordinator now tracks cached data returns as successful polls (coordinator provided data successfully)
- **Field Name Mismatch Fixed**: Changed `last_successful_poll` to `last_success_time` to match display code
- **Result**: Diagnostic entities now show accurate real-time polling statistics (Poll Success Rate, Total Polls, Last Successful Poll, etc.)

**Old Firmware Protection:**
- **60-Second Minimum Enforced**: Old firmware (BUILD < 61840) now automatically enforces 60s minimum polling
- **Hardware Protection**: Prevents dangerous fast polling on legacy firmware that could stress PVS hardware
- **Config Flow Detection**: `_adjust_polling_for_old_firmware()` called after firmware detection in both setup paths
- **User Transparent**: Silently adjusts user input to safe values

**Memory/Flash Monitoring Improvements:**
- **New Sensors for New Firmware**: Added RAM Usage % and Flash Usage % sensors (pypvs only provides percentages, not KB)
- **Percentage-Based Flash Alerts**: New firmware users get flash alerts when usage > 85% (< 15% available) - configurable 0-100%
- **Firmware-Aware Config UI**: Setup shows "MB" for old firmware, "%" for new firmware with appropriate defaults
- **Old Firmware Unchanged**: KB-based monitoring continues working for BUILD < 61840 users
- **Smart Detection**: Integration automatically uses correct metric based on available data

**Data Availability Changes:**
- **New Firmware (BUILD ≥ 61840)**:
  - Memory Used KB: Shows 0 (data unavailable from varserver)
  - Flash Available KB: Shows 0 (data unavailable from varserver)
  - RAM Usage %: Shows actual percentage (0-100%)
  - Flash Usage %: Shows actual percentage (0-100%)
- **Old Firmware (BUILD < 61840)**:
  - Memory Used KB: Shows actual KB values
  - Flash Available KB: Shows actual KB values
  - Percentage sensors: Not created (data unavailable)

### Technical Details

**Files Modified:**
- `__init__.py`:
  - Fixed serial number lookup to check both entry.options and entry.data (line 541-543)
  - Fixed diagnostic stat tracking (lines 588-589, 635-636, 730-748)
  - Changed field name from `last_successful_poll` to `last_success_time` (lines 162, 743)
  - Moved stat tracking before diagnostic device creation (order-of-operations fix)
- `config_flow.py`:
  - Added `_adjust_polling_for_old_firmware()` function (lines 69-82)
  - Called in both setup paths (lines 268, 336)
  - Firmware-aware flash threshold UI: Shows MB/% units based on firmware (lines 412-423, 640-652)
  - Auto-converts old MB values to 85% default for new firmware users
- `pypvs_converter.py`:
  - Added `ram_usage_percent` and `flash_usage_percent` fields (lines 66-67)
  - Set KB values to "0" for new firmware (data unavailable from varserver)
- `health_check.py`:
  - Added percentage-based flash monitoring (lines 390-406)
  - Kept KB-based monitoring for old firmware (lines 408-421)
  - Uses firmware-aware threshold (85% for new, MB for old)
- `sensor.py`:
  - Skip KB sensors when value is "0" (lines 127-130)
  - Prevents creating ghost entities for new firmware users
- `const.py`:
  - Added `PVS_RAM_USAGE_PERCENT` sensor definition (lines 184-192)
  - Added `PVS_FLASH_USAGE_PERCENT` sensor definition (lines 193-201)

### Future Plans

**Old Firmware Support Removal (~2 weeks):**
- Will remove all BUILD < 61840 legacy code (dl_cgi, route checking, VLAN setup)
- Simplifies codebase significantly
- New firmware (varserver/pypvs) will be only supported method
- Users on old firmware should upgrade or freeze on final legacy-supporting version

## [v2025.10.7] - 2025-10-03

### New Firmware Polish & Refinements

**Authentication Experience:**
- **Suppressed pypvs Auth Warnings**: Hidden harmless "Unauthorized access. Retrying login..." messages from logs
- **Reason**: pypvs library retries authentication internally - warnings don't indicate errors
- **Result**: Clean logs, no GitHub issues from confused users seeing retry messages

**Polling Flexibility:**
- **10-Second Minimum Polling**: Reduced from 300 seconds to 10 seconds for new firmware (LocalAPI/varserver)
- **Battery System Protection**: Auto-adjusts to 20-second minimum when battery system detected
- **Configuration UI Updated**: Setup and options flows now show correct "10-3600 seconds" range
- **SunStrong Guidance**: Faster polling safe on new firmware due to improved varserver performance

**Entity Parity Restored:**
- **PVS Diagnostic Entities**: Added missing `dl_skipped_scans`, `dl_scan_time`, `dl_untransmitted` fields
- **Production Meter Amps**: Fixed meter type detection (p/c suffix) - production meters now always include Amps entity
- **Zero-Value Filtering**: Meters only create entities for non-zero fields (matches old dl_cgi behavior exactly)
- **Result**: Entity counts match legacy integration exactly

**Network Flexibility:**
- **Both Ports Supported**: WAN (192.168.1.73) and LAN (172.27.153.1) ports work with new firmware
- **No VLAN Required**: New firmware authentication eliminates need for network isolation
- **WAN Port Recommended**: Gets DHCP address, easier to discover than fixed LAN IP
- **Backward Compatible**: Old firmware still requires LAN port isolation (legacy behavior)

### Technical Details

**pypvs_converter.py Enhancements:**
- **PVS Model Extraction**: Correctly extracts "PVS6" from `hardware_version` field (gateway.model returns "PV-only")
- **Device Naming**: Prepends "PV Supervisor" to match legacy format exactly
- **Meter Type Detection**: Uses model suffix ('p'=production, 'c'=consumption) for field inclusion logic
- **Production Meters**: Always include `i_a` (Amps) if available
- **Consumption Meters**: Include per-leg data (i1_a, i2_a, p1_kw, p2_kw, v1n_v, v2n_v) only if non-zero

**Files Modified:**
- `__init__.py`: Added pypvs.pvs_fcgi logger suppression (line 28)
- `config_flow.py`: Changed hardcoded 300 to MIN_SUNPOWER_UPDATE_INTERVAL (line 224)
- `translations/en.json`: Updated polling interval descriptions to "10-3600 seconds"
- `pypvs_converter.py`: Added PVS diagnostic fields, fixed meter type detection

## [v2025.10.6] - 2025-10-03

### Major Feature: Intelligent Firmware Auto-Detection

**Supervisor/Info Auto-Detection:**
- **Automatic Firmware BUILD Detection**: Integration now queries `/cgi-bin/dl_cgi/supervisor/info` to detect firmware BUILD number
- **Smart Method Selection**: Automatically chooses pypvs (BUILD ≥61840) or legacy dl_cgi (BUILD <61840) based on detected firmware
- **Zero Configuration**: No manual firmware type selection required
- **Safety Fallback**: If LocalAPI (pypvs) fails even on new firmware, automatically falls back to legacy dl_cgi with warning log

**Password Auto-Detection:**
- **Automatic Serial Detection**: Full PVS serial number detected from supervisor/info endpoint
- **Auto-Extract Last 5 Characters**: Password automatically extracted and formatted in UPPERCASE
- **Pre-Fill Password Field**: Setup page 2 pre-fills with auto-detected password (new firmware only)
- **Skip for Old Firmware**: Password step completely skipped when BUILD < 61840 detected
- **Manual Override Available**: Users can still manually enter password if auto-detection fails

### New Firmware Support Enhancement

**pypvs Data Format Converter:**
- **New Module**: Created `pypvs_converter.py` to convert pypvs PVSData objects to legacy dl_cgi format
- **Seamless Integration**: Existing data_processor.py works unchanged for both firmware types
- **Complete Device Support**: Converts PVS gateway, inverters, power meters, and ESS/battery devices
- **Field Mapping**: Maps pypvs model attributes to dl_cgi field names (e.g., `last_report_kw` → `p_kw`)
- **Backward Compatible**: Old firmware path completely unchanged

### Critical Fixes

**Manifest Dependencies:**
- **Fixed**: Removed unused `bcrypt` and `requests` from requirements (inherited from pvs-hass but never used)
- **Fixed**: Added missing `simplejson` dependency (used in sunpower.py but not listed)
- **Kept**: `pypvs` dependency (correct - used for new firmware)
- **Note**: `aiohttp` automatically installed as pypvs dependency

**Authentication Routing:**
- **Fixed**: Old firmware (BUILD <61840) now gets `auth_password=None` instead of password value
- **Fixed**: Password only used when `uses_pypvs=True` to prevent auth errors on old firmware
- **Fixed**: Uppercase transformation for password to match serial format (e.g., "W3193" not "w3193")

### Diagnostic Improvements

**Dependency Logging:**
- **Added**: Startup logging of pypvs version and installation path for troubleshooting
- **Added**: aiohttp and simplejson version logging
- **Format**: Clear log messages show exact package versions and file locations

**Config Flow Logging:**
- **Enhanced**: Detailed firmware detection logs show BUILD number, method selected, serial, and password
- **Enhanced**: Fallback attempts logged with clear success/failure indicators
- **Enhanced**: Uses indicators (checkmark/X/warning) in logs for quick scanning

### Security & Stability

**Buggy Firmware Protection:**
- **Safety Net**: If pypvs fails validation on BUILD ≥61840, automatically tries legacy dl_cgi as fallback
- **SunStrong Issue Mitigation**: Handles known LocalAPI stability issues in some firmware versions (GitHub issue #7)
- **Graceful Degradation**: Integration stays functional even if new LocalAPI implementation has bugs
- **Detailed Error Messages**: Both methods' errors logged if both fail

**⚠️ Testing Status Update:**
- **Old Firmware (BUILD <61840)**: Fully tested on BUILD 61839 production system
- **New Firmware (BUILD ≥61840)**: COMPLETELY UNTESTED - awaiting user testing with additional safety fallbacks
- **Unknown Success Rate**: May work better than SunStrong's integration (which has reported issues) due to fallback mechanisms, but this is untested speculation

### Documentation Updates

**README.md:**
- Updated firmware compatibility section with BUILD threshold (61840) clearly stated
- Added password auto-detection details and uppercase format requirement
- Updated setup process to reflect 3-page flow with auto-detection
- Clarified authentication is automatic for both firmware types

**CLAUDE.md:**
- Added new firmware testing status with BUILD threshold details
- Documented supervisor/info endpoint and auto-detection logic
- Added pypvs_converter.py to architecture documentation

### Architecture Improvements

**Code Organization:**
- **Modular Design**: pypvs converter isolated in separate 140-line file (keeps data_processor.py clean)
- **Single Conversion Point**: All pypvs→legacy conversion happens in one function
- **No Existing Code Changes**: data_processor.py, battery_handler.py, health_check.py unchanged
- **Clean Imports**: Only 2 lines added to __init__.py (import and usage)

## [v2025.10.6] - 2025-10-02

### Major Architecture Change: pypvs Library Integration
- **Replaced Custom Varserver**: Removed custom `varserver.py` implementation in favor of official `pypvs` library from SunStrong
- **Guaranteed New Firmware Compatibility**: Now uses exact same authentication and communication code as proven working SunStrong integration
- **Automatic Library Installation**: Home Assistant automatically installs pypvs library - zero manual work for users
- **Two-Step Configuration**: Configuration flow now matches SunStrong pattern - validate first, then collect password
- **Dual-Mode Support**: Automatically detects firmware version during setup and uses appropriate method

### Critical Bug Fixes
- **Flash Memory Alerts Fixed**: Corrected three bugs preventing flash memory warnings from triggering
  - Fixed config key mismatch (`flash_memory_threshold` vs `flash_memory_threshold_mb`)
  - Fixed units conversion (PVS reports KB, threshold is MB - now converts correctly)
  - Fixed health checks skipped on cached data (now runs on both fresh and cached data)
- **Notification Formatting**: Cleaned up flash memory alert decimal places (was 57.541015625MB, now 57.5MB)

### Backward Compatibility
- **Old Firmware Fully Supported**: Legacy dl_cgi method preserved for firmware < 61840
- **Automatic Fallback**: Config validation tries pypvs first (new firmware), automatically falls back to dl_cgi (old firmware)
- **Zero Breaking Changes**: Existing installations continue working unchanged

### For New Firmware Users (61840+)
- ⚠️ **COMPLETELY UNTESTED**: Built from SunStrong's proven code but not yet tested on actual new firmware
- **Architecture Match**: Uses exact same pypvs library and patterns as working SunStrong integration
- **Beta Testers Needed**: If you have new firmware, please test and report results

## [v2025.10.5] - 2025-10-01

### New Firmware Support (61840+)
- **Varserver Support**: Added full varserver (FCGI) support for firmware 61840+ with automatic fallback to dl_cgi for older firmware
- **Cookie-Based Authentication**: Implemented session cookie authentication matching SunStrong's pypvs library
- **DeviceList via Varserver**: Efficient device data fetching from varserver with backward compatibility conversion

### Critical Authentication Fixes
- **Lowercase "basic" Header**: Fixed auth header to use lowercase "basic" per pypvs/RFC standard (was uppercase "Basic")
- **UTF-8 Encoding**: Changed from ASCII to UTF-8 encoding for authentication credentials
- **Cookie Jar Clearing**: Applied pypvs PR#7 fix to prevent aiohttp cookie caching interference
- **Required PVS Serial**: PVS serial number now required for all installations (firmware 61840+ requires authentication)

### Performance Improvements
- **Fast Varserver Probe**: Reduced varserver capability detection timeout from 120s to 10s to prevent startup delays
- **Skip First Health Check**: Health check now skipped on first poll after HA restart to prevent false backoff

### Bug Fixes
- **Startup Polling**: Fixed health check failure on first poll after restart causing 1-minute delay
- **Varserver Timeout**: Prevented long varserver probe from blocking integration startup on old firmware

## [v2025.10.7] - 2025-10-04

### Code Quality Improvements
- **Enhanced Error Logging**: Added HTTP status codes and response bodies to all PVS communication errors for better troubleshooting
- **Refactored Error Handling**: Broke down 104-line try-catch block into 7 focused error handling steps for easier debugging
- **Improved Documentation**: Added comprehensive docstrings to key functions and classes
- **Reduced Log Noise**: Changed email notification success messages from WARNING to DEBUG level

### Bug Fixes
- **Fixed Polling Failure Rate**: Corrected regression where `None` from health checks was treated as error instead of normal cache fallback
- **Eliminated False Notifications**: Removed spurious "PVS polling returned no data" errors during normal backoff periods
- **Fixed State Class Warning**: Changed communication_errors sensor from `TOTAL_INCREASING` to `TOTAL` to handle PVS counter resets
- **Increased Health Check Timeout**: Changed from 2s to 5s to improve reliability on slower networks

## [v2025.9.9] - 2025-09-29

###  Major Architecture Simplification
- **Simplified Polling System**: Removed complex day/night/elevation-based polling variations in favor of consistent 24/7 operation
- **Streamlined Config Flow**: Reduced from 3-page configuration to 2-page setup, removing unused elevation settings
- **Eliminated Solar Tracking**: Removed sunrise/sunset elevation controls
- **Unified Polling Logic**: Single polling interval for all conditions, dramatically simplifying codebase maintenance
- **Legacy Code Removal**: Eliminated hundreds of lines of complex conditional logic for cleaner, more reliable operation

###  Critical Bug Fix: Inverter Failure Notification Flood
- **Root Cause**: Code simplification accidentally removed nighttime dormancy understanding, causing all 30 inverters to trigger false failures
- **24-Hour Persistent Error Tracking**: Revolutionary approach that only alerts after 24+ hours of continuous problems
- **Eliminated False Positives**: Fixed critical regression where normal STATE="error" during inverter dormancy triggered 30+ notifications nightly
- **Smart Recovery Detection**: Automatic notifications when persistent issues resolve after extended periods
- **Batched Notifications**: Multiple inverter issues now grouped into single notification instead of 20+ separate emails
- **Gmail Rate Limit Protection**: Prevents overwhelming email services with notification floods that could lock accounts

###  Enhanced Varserver Migration Support (Future Firmware 61840+)
- **Complete Compatibility Layer**: Full varserver support for upcoming SunPower firmware migration
- **Minimal Dependencies**: Custom lightweight varserver wrapper avoids external library dependencies
- **Automatic Detection**: Seamlessly detects and enables varserver capabilities when firmware supports it
- **Zero Breaking Changes**: Maintains 100% backwards compatibility with existing dl_cgi endpoints
- **Battery System Enhancement**: Modern ESS data processing via authenticated varserver endpoints
- **FCGI Authentication**: Full support for ssm_owner + PVS serial authentication scheme

### 🔍 Restored Original Failure Detection Logic
- **Presence-Based Detection**: Returned to original github_staging logic of detecting missing inverters vs state changes
- **Context-Aware Monitoring**: Fixed regression that confused normal operational cycles with equipment failures
- **Eliminated State-Based Failures**: Stopped treating present inverters with STATE="error" as failed (normal at night)
- **Persistent Issue Focus**: Only genuine hardware problems that persist across multiple day/night cycles trigger alerts

## [v2025.9.8] - 2025-09-27

### New Feature: Email Notifications for Critical Alerts
- **Critical Alert Email System**: Send email notifications for critical hardware alerts alongside mobile notifications
- **Auto-Detection**: Automatically detects available email notification services (Gmail, SMTP, etc.)
- **Custom Recipients**: Optional email recipient override for dedicated notification accounts
- **Critical Alerts Only**: Emails sent only for essential alerts (PVS offline, inverter failures, flash memory critical)
- **Service Integration**: Works with any Home Assistant notify service (Gmail, Outlook, SMTP, etc.)
- **Clean Configuration**: Simply select email service to enable - no confusing toggles

### Critical Alerts That Trigger Emails
- ⚠️ **Flash Memory Critical**: When PVS storage drops below threshold
- 🔴 **PVS Offline**: System connectivity failures
- ⚠️ **Inverter Failures**: Individual inverter offline detection
- 🔑 **Authentication Errors**: PVS6 firmware authentication issues
- 🔧 **Hardware Issues**: Critical system protection alerts

## [v2025.9.7] - 2025-09-26

### ⚠️ Critical Bug Fixes
- **Fixed Config Flow Blocker**: Gateway IP field was incorrectly marked as required, preventing users from completing setup. Now properly optional for VLAN users only.
- **Battery System Serial Number Fix**: Completely resolved the critical bug where battery systems would show only "1 entity" instead of full sensor data. Fixed the serial number mismatch issue between DeviceList and ESS endpoints that was causing silent failures.

### New Feature: PVS6 Authentication Support
- **Future-Ready Authentication**: Prepared for upcoming SunPower firmware 61840+ that will require authentication
- **PVS Serial (Password) Field**: Added configuration field for last 5 characters of PVS serial number
- **Automatic Fallback Logic**: Tries unauthenticated first, then uses Basic Auth if needed (backward compatible)
- **Battery System Coverage**: Authentication applies to both main device polling and battery system endpoints
- **Zero Impact**: Works perfectly with current firmware, ready when authentication becomes mandatory

### PVS Serial Number Location
- **Physical Label**: Remove PVS cover to find serial number on device label
- **SunPower App**: Available under Profile tab → System Info
- **Config Flow**: Enter last 5 characters only (e.g., if serial is "ABC123XYZ78901", enter "78901")

### Technical Improvements
- **HTTP Basic Authentication**: Username "ssm_owner", password is last 5 chars of PVS serial
- **Smart Authentication Flow**: Attempts connection without auth first, adds auth on 401/403 responses
- **Comprehensive Coverage**: Both `/cgi-bin/dl_cgi?Command=DeviceList` and `/cgi-bin/dl_cgi/energy-storage-system/status` endpoints
- **Enhanced Error Messages**: Clear feedback when authentication fails or PVS serial needed
- **Robust Battery Handler**: Complete rewrite of battery data processing with defensive programming, comprehensive error handling, and detailed logging
- **Virtual Device Creation**: Creates operational battery devices from ESS data when physical device serials don't match

---

## [v2025.9.5] - 2025-09-24

###  Critical Bug Fixes
- **Fixed Battery System Regression**: Restored ESS endpoint polling that was missing from krbaker's original version
  - Battery systems now get proper sensor entities instead of sparse "1 entity" devices
  - Fixed device type mapping issues causing battery conversion failures ("Battery" vs "ESS BMS" types)
  - Added robust error handling to prevent integration crashes during ESS endpoint failures
  - Enhanced debug logging to diagnose ESS endpoint accessibility issues
  - Integration now works exactly like krbaker's version but with better error handling

###  Technical Improvements
- **Dual-endpoint polling**: Restored `/cgi-bin/dl_cgi/energy-storage-system/status` endpoint for detailed battery data
- **Enhanced sensor definitions**: Support for all battery device type variations
- **Comprehensive error handling**: ESS endpoint failures won't break entire integration
- **Debug diagnostics**: Enhanced logging for troubleshooting battery system issues

---

## [v2025.9.4] - 2025-09-23

###  Bug Fixes
- **Fixed Battery System Regression**: Restored ESS endpoint polling that was missing from krbaker's original version
  - Battery systems now get proper sensor entities instead of sparse "1 entity" devices
  - Added graceful fallback when ESS endpoint fails - basic sensors still created from PVS data
  - Battery devices show appropriate state information even during hardware error conditions

---

## [v2025.9.3] - Released

> **Note**: v2025.9.2 was released but had buggy day/night transition behavior (stuck in wrong polling modes). Rolled back to stable v2025.8.26 and rebuilt the features properly with comprehensive testing.

### 🆕 Major Features
- **Dynamic Day/Night Polling**: Complete redesign of polling interval management
  - **Daytime Polling Interval**: 300-3600 seconds for solar production monitoring
  - **Nighttime Polling Interval**: 0 (disabled) or 300-3600 seconds for consumption tracking
  - **Real-time Interval Switching**: Coordinator dynamically adjusts based on sun elevation
  - **Perfect for consumption monitoring** when solar panels aren't producing

### ⚠️ BREAKING CHANGES
- **Removed "Battery System" Toggle**: Replaced with automatic battery detection + separate nighttime interval
- **Automatic Migration**: Existing configurations are automatically updated on restart
  - `has_battery_system: true` → `nighttime_polling_interval: <same_as_daytime>`
  - `has_battery_system: false` → `nighttime_polling_interval: 0` (disabled)

### 🔧 Technical Improvements
- **Automatic Battery Detection**: Batteries detected from actual PVS device data, no manual toggle needed
- **Dynamic Coordinator Interval**: Home Assistant coordinator itself changes intervals in real-time
- **Enhanced Config Validation**: Prevents dangerous intervals (<300s) that could harm PVS hardware
- **Smart Battery Logic**: Battery systems use appropriate day/night intervals while maintaining 24/7 monitoring

### 🐛 Bug Fixes
- **Fixed Battery System Regression**: Restored ESS endpoint polling that was missing from krbaker's original version
  - Battery systems now get proper sensor entities instead of sparse "1 entity" devices
  - Added graceful fallback when ESS endpoint fails - basic sensors still created from PVS data
  - Battery devices show appropriate state information even during hardware error conditions
- **Fixed Battery Interval Logic**: Battery systems now properly use day/night intervals instead of always using daytime
- **Fixed Virtual Production Meter**: Removed erroneous "KWh To Home" sensor that always showed 0
- **Fixed Config Validation**: Nighttime intervals properly validated (0 or ≥300 seconds)
- **Fixed Battery Auto-Detection**: Tuple unpacking bug that caused false battery detection

### 🎨 Enhanced Debugging
- **Restored Coordinator Diagnostics**: Shows current/required intervals, mode, and elevation with precise timestamps
- **Improved Polling Notifications**: Correctly shows "Daytime/Nighttime/Battery" polling status
- **Enhanced Cache Notifications**: Shows current interval setting when using cached data
- **Better Mode Detection**: Clear differentiation between day, night, battery, and disabled modes

## [v2025.9.2] - 2025-01-15 [REMOVED]

> **Status**: This version was released but had buggy day/night polling transitions (would get stuck in wrong modes). Rolled back to v2025.8.26. All features rebuilt and working correctly in v2025.9.3.

## [v2025.9.1 - 09-13-2025]

### Bug Fixes
- **Virtual Production Meter**: Removed erroneous "KWh to Home" sensor that always showed 0
  - Virtual meters aggregate inverter data and cannot measure consumption direction
  - Reduces sensor clutter and user confusion
  - Real consumption meters still provide accurate bidirectional data

### User Interface Improvements
- **Enhanced Config Flow**: Added clear recommendations for naming options on setup page 2
  - "Use Descriptive Names" now shows "***Strongly recommended***" with improved formatting
  - "Use Product Names" now shows "***Not recommended***" with improved formatting
  
## [v2025.8.26] - 2025-08-29

### Critical Fixes
- **Small System Support**: Reduced minimum device requirement from 10 to 3 devices during setup
- **Proxy Compatibility**: Fixed TCP health checks for reverse proxy setups with custom ports
- **Windows Cache Files**: Fixed cache file creation when using host addresses with ports

### Impact
- Small solar systems (condos, townhomes, EV charging) can now complete setup
- Reverse proxy configurations work without manual intervention
- Cross-platform compatibility improved

## [v2025.8.25] - 2025-08-25

### Critical Fixes
- **Route Repair Retry Logic**: Fixed automatic recovery after route repair - integration now properly retries polling immediately after successful route restoration
- **Enhanced Logging**: Clear messages when route repair triggers automatic retry for better troubleshooting
- **Complete Automation**: No manual reload required after route failures - full hands-off recovery

### Code Maintenance
- **Removed Duplicate Battery Handler Functions**: Eliminated 100+ lines of redundant fallback code (`convert_ess_data_fallback()`, `get_battery_configuration_fallback()`, etc.)
- **Streamlined Battery Support**: Consolidated battery detection logic for better maintainability
- **Improved Code Organization**: Cleaner, more focused codebase structure

### Reliability Improvements
- **Bulletproof Route Handling**: Complete automatic detection, repair, and recovery sequence
- **Faster Recovery Times**: Route repair now triggers immediate polling retry instead of waiting for next cycle
- **Better Error Handling**: Enhanced status tracking for route repair operations
- **System Stability**: Reduced code complexity and memory overhead

## [v2025.9.3] - 2025-09-19

### Code Organization
- **Internal Refactoring**: Moved hardware monitoring functions from `__init__.py` to `health_check.py` for better code organization
- **Flash Memory Monitoring**: `check_flash_memory_level()` now properly located in health check module
- **Firmware Tracking**: `check_firmware_upgrade()` moved to health check module alongside other hardware monitoring
- **Diagnostic Stats**: `update_diagnostic_stats()` relocated to health check module for logical grouping
- **Maintainability**: Reduced `__init__.py` complexity by ~97 lines while preserving all functionality
- **No User Impact**: Internal reorganization only - all features work identically

### Major Features
- **Flash Memory Monitoring**: Critical alerts when PVS flash memory drops below configurable threshold (default: disabled, set MB value to enable)
- **Hardware Protection**: Prevents PVS failures by alerting before flash memory fills up completely
- **Smart Alert Logic**: Daily alert frequency with 5MB escalation (immediate alert if memory drops 5MB+ since last notification)
- **Existing Sensor Integration**: Uses existing "Flash Available" sensor data (KB) with threshold comparison in MB
- **Critical Alert System**: Flash memory alerts sent to both UI notifications and mobile devices (if enabled)
- **Recovery Detection**: Automatic alert reset when memory rises above threshold + 5MB buffer

### Bug Fixes
- **Cache Filename Persistence**: Fixed cache files using integration ID - now uses PVS IP address for consistent filenames across integration reinstalls
- **Route Repairs Diagnostic Sensor**: Fixed "Unavailable" status by correcting config data lookup (route_check_enabled stored in entry.data, not entry.options)
- **Config Flow UI Cleanup**: Removed redundant mobile notifications toggle - mobile device dropdown selection now controls alert sending (select device = enabled, "Disabled" = off)
- **Route Checking Simplification**: Removed separate route checking toggle - now controlled by Gateway IP field (empty = disabled, valid IP = enabled)
- **Config Page Organization**: Moved flash memory threshold to top of notifications page for better field spacing and visual flow
- **Config Flow Text Display**: Fixed missing text and labels on config flow pages 2 & 3 (Solar Configuration and Notifications)
- **Config Flow Organization**: Moved route checking options from Notifications page to Basic Setup page for better logical grouping
- **Translation Coverage**: Added complete translation entries for `solar` and `notifications` config flow steps

## [v2025.8.22] - 2025-08-16

### Bug Fixes
- **Diagnostic Sensor Display**: "Last Successful Poll" now shows timestamp with date (e.g., "14:29 08-16-25") for easy comparison with current time
- **Sensor Name Clarity**: Updated "Consecutive Failures" to "Consecutive Poll Failures" for better clarity

### Documentation
- **Configuration Table**: Added missing config options (Use Descriptive Names, Use Product Names, Replace Status Notifications)
- **Updated Screenshots**: Refreshed config page images to match current UI
- **Troubleshooting Guide**: Added poll success rate expectations section (90-95% normal)

## [v2025.8.21] - 2025-08-15

### Documentation Improvements
- **Energy Dashboard Screenshots Restored**: Added back missing production.png, consumption.png, and solar_panel_setup.png with setup guidance
- **Polling Range Display**: Enhanced config interface to clearly show "300-3600 seconds" range in help text
- **Professional Presentation**: Moved range info from unit field to description text for cleaner appearance
- **GitHub Sponsors Support**: Added sponsorship integration for community support

## [v2025.8.20] - 2025-08-14

### Bug Fixes
- **HACS Version Compatibility**: Fixed version format mismatch between Git tags and manifest for proper auto-notifications
- **Python Deployment Script**: Enhanced version parsing to handle both "v2025.8.x" and "2025.8.x" formats

## [v2025.8.18] - 2025-08-14

### Bug Fixes
- **Fixed diagnostic sensor updates**: "Last Successful Poll" sensor now properly shows real-time updates with human-readable formatting ("2m 30s ago" instead of raw seconds)
- **Improved diagnostic data flow**: Diagnostic statistics now update correctly during polling cycles
- **Enhanced error handling**: Better fallback behavior for diagnostic sensors during startup

### UI Improvements  
- **Cleaner diagnostic names**: Removed redundant "SunPower" prefix from all diagnostic sensor names for better dashboard readability
- **Professional presentation**: Streamlined sensor titles (e.g., "Poll Success Rate" instead of "SunPower Poll Success Rate")

### Technical Improvements
- **Real-time formatting**: Diagnostic time values now use the same human-readable format as notifications
- **Better data validation**: Enhanced diagnostic sensor value handling with proper null checks
- **Consistent naming**: All diagnostic sensors follow clean, professional naming conventions

## [v2025.8.17] - 2025-08-13

### Major Features
- **Entity Naming Compatibility**: Fixed energy dashboard entity naming to show proper inverter identification
- **Documentation**: Enhanced README
- **Config Flow Improvements**: Added naming options to Basic Settings page with backward compatibility

### Bug Fixes
- **Config Flow Submit Button**: Fixed missing variable definitions preventing successful configuration
- **Naming Options**: Restored `use_descriptive_names` and `use_product_names` functionality
- **Energy Dashboard**: Now shows proper "Inverter E001221370442207 Lifetime Power" format

## [v2025.8.7] - 2025-08-07

### Major Features
- **Sunrise/Sunset Elevation Split**: Separate thresholds for morning and evening optimization
- **Panel Orientation Support**: Perfect for east/west-facing panel installations
- **UI Reorganization**: Sun elevation moved to basic setup, cleaner advanced options
- **Enhanced Notifications**: Shows which threshold is active (sunrise/sunset/night coverage)
- **Smart Time Logic**: Morning uses sunrise threshold, evening uses sunset threshold
- **Migration Support**: Auto-converts old single elevation to dual thresholds

## [v2025.7.31] - 2025-07-31

### Major Features
- **Human-Readable Time Display**: All notifications show user-friendly time formats
- **Automatic Route Setup/Repair**: Detects and fixes lost network routes for VLAN setups
- **Configurable Gateway IP**: Route repair works with any network topology
- **Enhanced Diagnostics**: 7 sensors with improved time display formatting
- **Context-Aware Alerts**: Route-specific notifications distinguish network vs PVS issues
- **Production Tested**: Extensive validation on real VLAN networking scenarios

### Technical Improvements
- **Diagnostic Dashboard**: 7 new sensors tracking integration reliability and performance
- **MPPT Sensor Bug Fixed**: Individual MPPT sensors now show real power values instead of "Unknown"
- **50% Code Reduction**: const.py optimized, battery code separated for better organization
- **Faster Loading**: Solar-only systems load significantly less code
- **Better Architecture**: Logical separation by functionality, improved maintainability

## [v2025.7.26] - 2025-07-26

### Initial Enhanced Release
- **Mobile Notification System**: Direct alerts to your phone with smart fallback
- **Inverter Health Monitoring**: Individual inverter tracking with failure detection
- **Intelligent Solar Optimization**: Sun elevation-based polling with configurable thresholds
- **Multi-Channel Notifications**: Six separate notification streams with smart management
- **Advanced PVS Protection**: Comprehensive health monitoring with TCP-based detection
- **Production Stability**: Extended real-world testing and validation
- **Enhanced Configuration**: Advanced options with user-friendly interface
- **Modular Architecture**: Clean separation of concerns into focused modules

### Based on Original Work
This enhanced version builds upon [@krbaker's original integration](https://github.com/krbaker/hass-sunpower) with significant reliability and usability improvements while maintaining full compatibility with existing installations.
