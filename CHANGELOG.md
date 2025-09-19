# Changelog

All notable changes to the Enhanced SunPower Home Assistant Integration will be documented in this file.

## [unreleased]

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
