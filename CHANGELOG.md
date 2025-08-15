# Changelog

All notable changes to the Enhanced SunPower Home Assistant Integration will be documented in this file.

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
- **Professional Documentation**: Enhanced README with 80% emoji reduction for credible presentation
- **Config Flow Improvements**: Added naming options to Basic Settings page with backward compatibility

### Bug Fixes
- **Config Flow Submit Button**: Fixed missing variable definitions preventing successful configuration
- **Naming Options**: Restored `use_descriptive_names` and `use_product_names` functionality
- **Energy Dashboard**: Now shows proper "Inverter E001221370442207 Lifetime Power" format

## [v2025.8.7] - 2025-08-07

### Major Features
- **🌅 Sunrise/Sunset Elevation Split**: Separate thresholds for morning and evening optimization
- **🎯 Panel Orientation Support**: Perfect for east/west-facing panel installations
- **⚙️ UI Reorganization**: Sun elevation moved to basic setup, cleaner advanced options
- **📱 Enhanced Notifications**: Shows which threshold is active (sunrise/sunset/night coverage)
- **🔧 Smart Time Logic**: Morning uses sunrise threshold, evening uses sunset threshold
- **✅ Migration Support**: Auto-converts old single elevation to dual thresholds

## [v2025.7.31] - 2025-07-31

### Major Features
- **🕒 Human-Readable Time Display**: All notifications show user-friendly time formats
- **🛜 Automatic Route Setup/Repair**: Detects and fixes lost network routes for VLAN setups
- **⚙️ Configurable Gateway IP**: Route repair works with any network topology
- **📊 Enhanced Diagnostics**: 7 sensors with improved time display formatting
- **🔧 Context-Aware Alerts**: Route-specific notifications distinguish network vs PVS issues
- **✅ Production Tested**: Extensive validation on real VLAN networking scenarios

### Technical Improvements
- **📊 Diagnostic Dashboard**: 7 new sensors tracking integration reliability and performance
- **🔧 MPPT Sensor Bug Fixed**: Individual MPPT sensors now show real power values instead of "Unknown"
- **📦 50% Code Reduction**: const.py optimized, battery code separated for better organization
- **⚡ Faster Loading**: Solar-only systems load significantly less code
- **🏗️ Better Architecture**: Logical separation by functionality, improved maintainability

## [v2025.7.26] - 2025-07-26

### Initial Enhanced Release
- **📱 Mobile Notification System**: Direct alerts to your phone with smart fallback
- **🔧 Inverter Health Monitoring**: Individual inverter tracking with failure detection
- **🌞 Intelligent Solar Optimization**: Sun elevation-based polling with configurable thresholds
- **🔔 Multi-Channel Notifications**: Six separate notification streams with smart management
- **🛡️ Advanced PVS Protection**: Comprehensive health monitoring with TCP-based detection
- **⚡ Production Stability**: Extended real-world testing and validation
- **🔧 Enhanced Configuration**: Advanced options with user-friendly interface
- **📊 Modular Architecture**: Clean separation of concerns into focused modules

### Based on Original Work
This enhanced version builds upon [@krbaker's original integration](https://github.com/krbaker/hass-sunpower) with significant reliability and usability improvements while maintaining full compatibility with existing installations.
