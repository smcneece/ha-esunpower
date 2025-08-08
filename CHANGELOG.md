# Changelog

All notable changes to the Enhanced SunPower Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.8.7] - 2025-08-08

### Added
- 🌅 **Sunrise/Sunset Elevation Control** - Separate thresholds for morning and evening optimization
- 🎯 **Panel Orientation Support** - Perfect for east/west-facing panel installations
- 🔧 **Smart Time Logic** - Morning uses sunrise threshold, evening uses sunset threshold
- ✅ **Migration Support** - Auto-converts old single elevation to dual thresholds
- 📱 **Enhanced Notifications** - Shows which threshold is active in debug mode
- ⚙️ **UI Reorganization** - Sun elevation moved to basic setup, cleaner advanced options

### Changed
- Simplified day/night logic - removed overcomplicated morning/evening time boundaries
- Updated notification messages for clearer day/night status
- Improved configuration flow with better elevation guidance

### Fixed
- Removed confusing "evening mode at 2 PM" logic
- Simplified state determination to work year-round regardless of sunrise/sunset times

## [2025.7.31] - 2025-07-31

### Added
- 🕒 **Human-Readable Time Display** - All notifications show user-friendly time formats
- 🛜 **Automatic Route Repair** - Detects and fixes lost network routes for VLAN setups
- ⚙️ **Configurable Gateway IP** - Route repair works with any network topology
- 📊 **Enhanced Diagnostics** - 7 sensors with improved time display formatting
- 🔧 **Context-Aware Alerts** - Route-specific notifications distinguish network vs PVS issues

### Changed
- Time display format: "50 minutes ago" instead of "3039s ago"
- Improved diagnostic sensor formatting and reliability
- Enhanced route checking logic for VLAN environments

### Fixed
- Time conversion in all notification channels
- Route detection accuracy in complex network setups

## [2025.7.26] - 2025-07-26

### Added
- 📱 **Mobile Notification System** - Direct alerts to your phone with smart fallback
- 🔧 **Individual Inverter Health Monitoring** - Per-panel failure detection and recovery alerts
- 🌞 **Intelligent Solar Optimization** - Sun elevation-based polling with configurable thresholds
- 🔔 **Multi-Channel Notifications** - Six separate notification streams with smart management
- 🛡️ **Advanced PVS Protection** - Comprehensive health monitoring with TCP-based detection
- 📊 **Diagnostic Dashboard** - 7 new sensors tracking integration reliability and performance
- ⚡ **Production Stability** - Extended real-world testing and validation
- 🔧 **Enhanced Configuration** - Advanced options with user-friendly interface
- 📊 **Modular Architecture** - Clean separation of concerns into focused modules

### Changed
- Minimum polling interval increased from 60s to 300s for PVS hardware protection
- Binary sensors now use proper boolean states (on/off) instead of text values
- Improved error handling and graceful degradation throughout

### Fixed
- MPPT sensor values now show real power instead of "Unknown"
- Entity creation issues during startup
- Binary sensor state formatting for Home Assistant standards

### Security
- Enhanced PVS protection with intelligent backoff and health checking
- Reduced integration stress on PVS hardware

## Based on Original Work

This enhanced version builds upon [@krbaker's original integration](https://github.com/krbaker/hass-sunpower) with significant reliability and usability improvements while maintaining full compatibility with existing installations.

---

**Legend:**
- 🌅 Solar Features
- 📱 Mobile/Notifications  
- 🔧 System Health
- 📊 Diagnostics
- ⚙️ Configuration
- 🛡️ Protection/Security
- ✅ Compatibility
