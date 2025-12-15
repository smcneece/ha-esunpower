# Changelog

All notable changes to the Enhanced SunPower Home Assistant Integration will be documented in this file.


## [v2025.12.3] - 12-15-2025

### Bug Fix: Multi-Module Battery Systems Not Detected (Issue #42)

**Fixed battery systems with 4+ modules being silently rejected during data processing**
- **Problem**: Battery systems with multiple modules (4-5+ batteries) were not creating entities in Home Assistant
- **Root Cause**: Serial validation in `data_processor.py` rejected device serials longer than 50 characters
- **Impact**: Large battery installations (like sid's 4-module system with 72-char serial) were completely ignored

**The Fix:**
- Increased serial validation limit from 50 to 150 characters
- Multi-module battery serials can be 70+ characters: base hub (12 chars) + each module (15 chars each)
- Still protects against truly corrupted data (>150 chars)
- Added explanatory comment for future maintainers

**Files Modified:**
- `data_processor.py`: Lines 221-226 - Increased serial length validation limit

**Serial Format Examples:**
- 2-module system: `00001D5A134A_M00122147A2165_M00122147A2157` (42 chars) - Always worked
- 4-module system: `00001C398F32_M00122132A10D3_M00122125A0B6F_M00122132A0EBD_M00122132A10D0` (72 chars) - Now works!

**User Impact:**
- Battery systems with 4+ modules now properly detected and create all ESS entities
- State of Charge, Power, Temperature, and all battery sensors now appear correctly
- No impact on existing installations (backward compatible)

**Issues Addressed:**
- Issue #42 - Fixed large multi-module battery systems not creating entities

---

## [v2025.12.2] - 12-12-2025

### Bug Fix: Stale Power Values at Night (Issue #41)

**Fixed inverters showing non-zero power values when offline at night**
- **Problem**: Cached inverters retained last production values (e.g., showing 1.7W at 11 PM when offline)
- **Root Cause**: Cache restoration preserved all field values including stale power readings from sunset
- **Impact**: Energy dashboards and graphs showed misleading "ghost production" during nighttime hours

**The Fix:**
- Added `_sanitize_cached_inverter()` function to zero out power-related fields when restoring from cache
- Zeroed fields: power (kW), current (A), voltage (V), frequency (Hz), MPPT power/current/voltage
- Preserved fields: lifetime production (cumulative, doesn't change), temperature, device info
- Applied during nighttime cache restoration when inverters go offline

**Files Modified:**
- `__init__.py`: Lines 516-553 - Added `_sanitize_cached_inverter()` function
- `__init__.py`: Lines 991-995 - Applied sanitization during cache restoration

**User Impact:**
- Inverter power sensors now correctly show 0W when panels offline at night
- Eliminates confusing "ghost production" in energy dashboards and graphs
- Cached inverter structure preserved (prevents entities from disappearing)
- Temperature and lifetime production remain accurate

**Issues Addressed:**
- Issue #41 - Fixed stale power values showing in nighttime graphs

---

### Bug Fix: Timestamp Accuracy (DATATIME Field)

**Fixed DATATIME timestamps to reflect actual PVS measurement time**
- **Problem**: DATATIME field was stamped with when integration processed data (datetime.utcnow()), not when PVS measured it
- **Root Cause**: pypvs provides actual measurement timestamp in `last_report_date`, but converter was ignoring it
- **Impact**: Cache files showed misleading timestamps, making it hard to diagnose stale data issues (Issue #39)

**The Fix:**
- Convert pypvs `last_report_date` (Unix timestamp) to DATATIME format instead of using current time
- Applies to: Inverters, Meters, ESS/Battery devices, Transfer Switches
- PVS/Gateway continues using current time (no `last_report_date` available)

**Files Modified:**
- `pypvs_converter.py`: Lines 9, 111, 145, 210, 238 - Added timezone import and fixed DATATIME conversion

**User Impact:**
- DATATIME now shows when PVS hardware measured the data, not when integration converted it
- Cache files accurately reflect measurement timestamps for diagnostics
- Helps identify stale cached data during Issue #39 debugging

**Issues Addressed:**
- Issue #39 - Improved diagnostic capability by showing accurate measurement timestamps

---

### Enhancement: Last Reported Timestamp Sensor (NEW)

**Added "Last Reported" sensor for each inverter showing when PVS last measured data**
- **Purpose**: Match pvs-hass functionality and provide visibility into data staleness (Issue #39)
- **Benefit**: Instantly see if inverter data is current or stale at a glance
- **Display**: Shows as relative time ("3 hours ago") in HA UI, click to see actual timestamp

**The Implementation:**
- Added INVERTER_LAST_REPORTED sensor using SensorDeviceClass.TIMESTAMP
- Reads from DATATIME field (now accurate thanks to timestamp fix above)
- Converts DATATIME string format to datetime object for HA timestamp display
- HA automatically displays as relative time with full date/time on click

**Files Modified:**
- `const.py`: Lines 604-612 - Added INVERTER_LAST_REPORTED sensor definition
- `sensor.py`: Lines 363-378 - Added DATATIME to datetime conversion for TIMESTAMP sensors

**User Impact:**
- Each inverter now has "Last Reported" sensor showing measurement age
- Easier to identify stale inverter data during Issue #39 debugging
- Matches pvs-hass feature parity

---

### Enhancement: Increased Inverter Sensor Precision (3 Decimals)

**Added 3 decimal precision to inverter sensors matching pvs-hass**
- **Purpose**: Show precise values and match pvs-hass for direct comparison (requested by user in Issue #39)
- **Benefit**: Better visibility during low light conditions, precise daily production tracking
- **Matches**: pvs-hass where they explicitly set 3 decimal precision

**The Fix:**
- Added `suggested_display_precision: 3` to inverter energy/current sensors:
  - Lifetime Production: 3 decimals (2,329.650 kWh)
  - Production Current: 3 decimals (0.005 A)
  - MPPT Current: 3 decimals (0.035 A)

**Files Modified:**
- `const.py`: Lines 530, 556, 584 - Added suggested_display_precision: 3 to INVERTER_NET_KWH, INVERTER_AMPS, and INVERTER_MPPT_A
- `sensor.py`: Line 293 - Added `suggested_display_precision` parameter to SunPowerSensor.__init__()
- `sensor.py`: Lines 327-330 - Added `suggested_display_precision` property to expose precision to Home Assistant
- `sensor.py`: Line 191 - Pass `suggested_display_precision` from sensor config during entity creation

**User Impact:**
- Lifetime production and current sensors now show 3 decimal places
- Matches pvs-hass display for easier comparison
- No action required - display automatically updates after integration reload

---

## [v2025.12.1] - 2025-12-07

### Bug Fix: Virtual Production Meter "KWh To Grid" Sensor

**Removed misleading "KWh To Grid" sensor from virtual production meters**
- **Problem**: Virtual production meters incorrectly created a "KWh To Grid" sensor that duplicated the "Lifetime Power" value
- **Root Cause**: Virtual meters don't have CT clamps and can't measure grid flow, but were creating `neg_ltea_3phsum_kwh` field anyway
- **Impact**: Users saw a misleading sensor showing the same value as production, not actual grid export

**The Fix:**
- Removed `neg_ltea_3phsum_kwh` field from virtual production meter creation
- Virtual meters now only show production-related sensors (Lifetime Power, Power, Frequency, etc.)
- Matches krbaker's original behavior

**Files Modified:**
- `data_processor.py`: Line 138 - Removed neg_ltea_3phsum_kwh from virtual meter

**User Impact:**
- Virtual production meter no longer shows misleading "KWh To Grid" sensor
- **BREAKING CHANGE**: Existing "KWh To Grid" entity on virtual meters will become unavailable - users should delete this orphaned entity from Settings → Devices & Services → Enhanced SunPower → Virtual Production Meter
- Only real consumption meters (with CT clamps) should have "KWh To Grid" sensors

---

### Bug Fix: Old Firmware 403 Error Messaging

**Improved error messages for old firmware 403 errors**
- **Problem**: Old firmware (BUILD < 61840) users experiencing 403 errors received confusing error messages about authentication
- **Root Cause**: Old firmware doesn't use authentication, so 403 errors indicate network/hardware issues, not auth problems
- **Impact**: Users were confused about whether they needed to configure authentication or restart their hardware

**The Fix:**
- Old firmware 403 errors now show clear network/hardware issue messages
- Error messages suggest specific recovery actions: "Try restarting your Raspberry Pi (if using proxy) and/or PVS"
- Eliminates false authentication error messages for old firmware
- New firmware (BUILD >= 61840) continues to handle 403 as potential auth errors with re-auth attempts

**Files Modified:**
- `__init__.py`: Lines 871-891 - Improved error messaging for old firmware 403 errors

**User Impact:**
- Old firmware users get actionable error messages with specific recovery steps
- No more confusion about authentication requirements on old firmware
- New firmware users unaffected - re-auth logic continues working as designed

**Issues Fixed:**
- Issue #35 - Old firmware 403 errors showing confusing messages

---

### Diagnostic Enhancement: pypvs Return Value Logging

**Added diagnostic logging to track pypvs library data returns (Issue #39)**
- **Problem**: Some users experiencing stuck inverter values (showing 0W or stale data from previous days)
- **Root Cause**: Unknown - investigating if pypvs library is returning empty inverter data
- **Diagnostic Tool**: New logging shows exactly what pypvs returns each poll cycle

**The Enhancement:**
- Logs inverter/meter/gateway counts from pypvs after each poll
- INFO level: Normal operation shows device counts
- WARNING level: Alerts when 0 inverters returned during daytime (sun above horizon)
- Helps diagnose whether stuck inverter issue is pypvs library bug or integration issue

**Files Modified:**
- `__init__.py`: Lines 783-795 - Added pypvs return value logging after polling

**User Impact:**
- Users experiencing stuck inverter issues can provide logs showing pypvs return counts
- Helps differentiate between pypvs library failures vs integration cache issues
- No functionality changes - purely diagnostic logging

**Log Examples:**
```
INFO [custom_components.sunpower] pypvs returned 24 inverters, 2 meters, gateway=present
WARNING [custom_components.sunpower] ⚠️ pypvs returned 0 inverters during daytime (sun elevation: 45.3°) - possible pypvs issue
```

**Issues Being Investigated:**
- Issue #39 - Stuck inverter values requiring HA restart to clear

---

## [v2025.11.10] - 2025-11-15

### Bug Fix: Battery SOC Display (100x Too High)

**Fixed battery state of charge showing 3100% instead of 31%**
- **Problem**: Battery SOC, Customer SOC, and SOH displaying 100x too high (3100% instead of 31%)
- **Root Cause**: pypvs v0.2.7 changed to return percentages already multiplied by 100, but our converter multiplied by 100 again
- **Impact**: Made battery charge levels misleading; displayed "3100%" when actual charge was 31%

**The Fix:**
- Removed `* 100` multiplication in pypvs_converter.py for SOC/SOH fields
- pypvs now provides percentages directly (0-100 range), no conversion needed
- Battery percentages now display correctly

**Files Modified:**
- `pypvs_converter.py`: Lines 190-192 - Removed percentage multiplication for soc_val, customer_soc_val, soh_val

**User Impact:** Battery control users with pypvs 0.2.7 - battery charge percentages now show correctly

---

## [v2025.11.9] - 2025-11-14

### CRITICAL Bug Fix: Deploy Script Breaking manifest.json

**Fixed deploy script silently stripping pypvs version requirement**
- **Problem**: Deploy script was using stale manifest data, causing `pypvs>=0.2.7` to revert to just `pypvs`
- **Root Cause**: Script loaded old staging manifest for version calculation, then used that stale data when writing updated manifest (instead of reloading after copying from VM)
- **Impact**: Users weren't getting pypvs 0.2.7 automatically, causing MPPT crashes and other issues. Affected all releases since pypvs requirement was added.

**The Fix:**
- Reload manifest.json after copying from VM to get current requirements
- Ensures pypvs version requirement (and all other fields) are preserved

**Files Modified:**
- `deploy_to_github.py`: Lines 380-382 - Reload manifest after copying before updating version

**⚠️ All Previous v2025.11.x Releases Affected:** If you installed any v2025.11.5-11.8 release, update to v2025.11.9 to get correct pypvs requirement!

---

## [v2025.11.8] - 2025-11-14

### CRITICAL Bug Fix: pvs_object Not Stored in hass.data

**Fixed battery control select entities not being created (final piece)**
- **Problem**: Even with battery detected and new firmware, select entities never created - log shows "Battery control requires new firmware (pypvs), skipping selects"
- **Root Cause**: `pvs_object` created during setup but never stored in `hass.data`, so `select.py` couldn't access it
- **Impact**: Battery control completely non-functional even after v2025.11.7 battery detection fix

**The Fix:**
- Store `pvs_object` in `hass.data[DOMAIN][entry.entry_id]` alongside coordinator
- `select.py` can now successfully retrieve `pvs_object` and create select entities

**Files Modified:**
- `__init__.py`: Line 1063 - Added `"pvs_object": pvs_object` to hass.data storage

---

## [v2025.11.7] - 2025-11-14

### CRITICAL Bug Fix: Battery Detection Completely Broken

**Fixed battery control select entities never being created**
- **Problem**: Battery control select entities (`select.battery_control_mode`, `select.battery_reserve_percentage`) never appeared, even with battery systems detected
- **Root Cause**: `select.py` checking for non-existent `coordinator.data["devices"]` instead of checking top-level device type keys
- **Impact**: Battery control feature completely non-functional since v2025.11.3

**The Fix:**
- Changed detection to check `coordinator.data.keys()` for battery device types
- Now correctly detects "Energy Storage System", "ESS", "Battery", etc. in coordinator data structure
- Matches how `sensor.py` and `binary_sensor.py` detect devices

**Files Modified:**
- `select.py`: Lines 46-51 - Fixed battery detection to check data structure keys

---

### CRITICAL Bug Fix: MPPT Backwards Compatibility Broken

**Fixed integration crash for users without pypvs 0.2.7**
- **Problem**: v2025.11.5 completely broken, all polling crashes with `AttributeError: 'PVSInverter' object has no attribute 'last_mppt_power_kw'`
- **Root Cause**: MPPT code assumed pypvs 0.2.7 attributes exist, didn't check for backwards compatibility
- **Impact**: Integration completely non-functional, no data polling, all entities unavailable

**The Fix:**
- Use `getattr()` with fallback for MPPT attributes (works with any pypvs version)
- Falls back to AC values if MPPT attributes don't exist (pypvs < 0.2.7)
- Home Assistant doesn't always auto-upgrade pypvs immediately, need backwards compatibility

**Files Modified:**
- `pypvs_converter.py`: Lines 107-109 - Added getattr() for MPPT fields with fallback

**⚠️ v2025.11.5 Users:** Update to v2025.11.6 immediately, v2025.11.5 is broken!

---

### Bug Fix: Old Firmware False Authentication Errors

**Fixed confusing "Authentication required" notifications for old firmware users**
- **Problem**: Users with old firmware (BUILD < 61840) receiving "The new firmware requires authentication but login failed" notifications when PVS temporarily returns HTTP 403 errors (bridge failures, network glitches)
- **Root Cause**: Legacy `SunPowerMonitor` code treating all 401/403 responses as authentication failures, even when no auth is configured (old firmware mode)
- **Impact**: Users unable to use automation scripts to recover from transient PVS/bridge failures, forced to reconfigure integration

**The Fix:**
- Old firmware mode now treats 401/403 as generic connection failures (not auth errors)
- Error message clarified: "PVS connection failed: HTTP 403 (old firmware should not require authentication)"
- Allows `consecutive_failures` counter to increment normally for automation-based recovery
- No more confusing "check PVS serial number" prompts for old firmware users

**Why This Happens:**
Old firmware doesn't require authentication, so HTTP 403 errors indicate:
- Raspberry Pi bridge offline/glitching
- Network connectivity issues
- PVS hardware temporarily unresponsive
- NOT an authentication problem

**Files Modified:**
- `sunpower.py`: Lines 143-144, 176-179 - Added old firmware detection and proper error handling for 401/403

**Issues Fixed:**
- Issue #35 - False authentication errors on old firmware with transient 403 responses

---

## [v2025.11.5] - 2025-11-14

### Bug Fix: Battery Control Select Entities Not Created (New Firmware)

**Fixed battery control select entities not appearing for new firmware users with batteries**
- **Problem**: Users with new firmware (BUILD >= 61840) and battery systems could not see `select.battery_control_mode` or `select.battery_reserve_percentage` entities
- **Root Cause**: Integration attempting to poll legacy ESS endpoint even for new firmware, causing AttributeError crash before select entities could be created
- **Impact**: Battery control feature completely non-functional for new firmware users

**The Fix:**
- Skip legacy ESS polling for new firmware (pypvs already includes ESS data in main response)
- Only call `sunpower_monitor.energy_storage_system_status_async()` when using old firmware
- Added debug logging to clarify when pypvs battery data is being used

**Files Modified:**
- `__init__.py`: Lines 910, 935-936 - Added check for `sunpower_monitor` before legacy ESS polling

**Issues Fixed:**
- Discussion #28 - Battery control entities not appearing for deltaxiii

---

### Enhancement: MPPT Data Now Uses DC Values

**Updated MPPT sensors to show actual DC voltage/current/power from solar panels**
- **Previous Behavior**: MPPT sensors showed AC values (~240V) as fallback when pypvs didn't provide DC data
- **New Behavior**: Uses actual DC MPPT data from pypvs v0.2.7+ (typically 30-60V DC from panels)
- **Requires**: pypvs >= 0.2.7 (automatically installed/updated by Home Assistant)

**MPPT Fields Now Accurate:**
- `v_mppt1_v`: DC voltage from panel (e.g., 57V instead of 240V AC)
- `i_mppt1_a`: DC current from panel
- `p_mppt1_kw`: DC power from panel

**Files Modified:**
- `pypvs_converter.py`: Lines 106-108 - Updated to use `last_mppt_voltage_v`, `last_mppt_current_a`, `last_mppt_power_kw` with AC fallback
- `manifest.json`: Line 16 - Updated pypvs requirement to >= 0.2.7

**Issues Fixed:**
- Issue #14 - MPPT voltage showing AC values instead of DC

---

## [v2025.11.4] - 2025-11-12

### Critical Bug Fix: krbaker Migration Statistics Issue

**Fixed negative lifetime energy values after migrating from krbaker integration**
- **Problem**: Users migrating from krbaker seeing massive negative energy spikes (e.g., -7,573 kWh)
- **Root Cause**: State class mismatch between krbaker (TOTAL) and Enhanced SunPower (TOTAL_INCREASING)
- **Impact**: Home Assistant statistics engine tried to reconcile the state class change, creating incorrect adjustments

**State Classes Reverted for Migration Compatibility:**
- `METER_TO_GRID`: Changed from `TOTAL_INCREASING` → `TOTAL` (matches krbaker)
- `INVERTER_NET_KWH`: Changed from `TOTAL_INCREASING` → `TOTAL` (matches krbaker)
- `METER_NET_KWH`: Already `TOTAL` (no change needed)

**Why This Matters:**
- `TOTAL` state class allows values to increase or decrease (handles PVS float precision variations)
- `TOTAL_INCREASING` enforces strictly increasing values (causes HA statistics reconciliation issues)
- Matching krbaker's state classes prevents HA from adjusting statistics during migration

**Existing Users:**
- If you already migrated and have negative spikes, you'll need to clean up HA statistics database
- See [MIGRATION.md](docs/MIGRATION.md) for statistics cleanup instructions
- New migrations after v2025.11.4 will not experience this issue

**Files Modified:**
- `const.py`: Lines 346, 529 - Reverted state classes to TOTAL

**Issues Fixed:**
- Issue #33 - Negative lifetime energy after krbaker migration

---

## [v2025.11.3] - 2025-11-10

### New Feature: Battery Control (SunVault)

**Added ability to control battery modes and reserve percentage directly from Home Assistant**
- New select entities for battery systems (requires new firmware BUILD >= 61840)
- Control battery operating mode: Self Supply, Cost Savings, Emergency Reserve
- Set minimum reserve percentage (10%-100% in 10% increments)
- Enable TOU (Time-of-Use) optimization via automations
- Real-time sync of current battery settings

**Select Entities Created (battery systems only):**
1. `select.battery_control_mode` - Switch between operating modes
2. `select.battery_reserve_percentage` - Set minimum battery reserve

**Battery Modes:**
- **Self Supply**: Use battery to offset home consumption (default)
- **Cost Savings**: Charge during off-peak, discharge during peak hours (TOU optimization)
- **Emergency Reserve**: Preserve battery for backup power only

**Example Automation (TOU):**
```yaml
automation:
  - alias: "Battery: Cost Savings During Peak Hours"
    trigger:
      - platform: time
        at: "15:00:00"
    condition:
      - condition: template
        value_template: "{{ now().month >= 10 or now().month <= 4 }}"
    action:
      - service: select.select_option
        target:
          entity_id: select.battery_control_mode
        data:
          option: "Cost Savings"
```

**How it works:**
- Integration polls battery config every polling interval
- Reads current mode from ESS status (already polled, no extra API call)
- Polls `min_customer_soc` separately (1 additional API call per poll)
- Select entities display current values in dropdowns
- User changes dropdown → writes to PVS → refreshes coordinator data
- Changes apply within seconds (PVS may delay if battery state prevents mode change)

**Safety Features:**
- Only created for systems with detected battery + new firmware
- Input validation (only allowed modes/percentages accepted)
- Warning logged if reserve set to 100% (battery won't discharge)
- All changes logged at INFO level for audit trail
- PVS may reject mode changes if battery charge too low (safety feature)

**Requirements:**
- SunVault or compatible battery system
- New firmware (BUILD >= 61840) with authentication
- Integration configured with PVS password (auto-detected during setup)

**Important Notes:**
- **Low battery behavior**: PVS may automatically revert from Emergency Reserve to Self Supply if battery charge is below the reserve threshold
- **100% reserve warning**: Setting reserve to 100% prevents battery from discharging for home use (backup only)
- **Mode change delays**: Changes may take a few moments to apply on PVS
- **Summer vs Winter**: TOU optimization most useful during winter months when solar production is lower

**Files Modified:**
- `select.py` (NEW): Lines 1-235 - Battery control select entities
- `__init__.py`: Line 109 (added "select" to PLATFORMS), Lines 934-966 (battery config polling)
- `const.py`: Battery mode constants

**Performance Impact:**
- +1 API call per poll for battery systems (min_customer_soc polling)
- Negligible memory impact (~80 bytes for battery_config data)

**Testing Status:**
- ✅ Syntax validated
- ✅ Entity creation logic verified
- ⚠️ Awaiting real-world testing with battery system

**Documentation:**
- See `battery_tou_automation_example.yaml` for comprehensive automation examples
- See `BATTERY-CONTROL-AUDIT.md` for detailed safety analysis and testing recommendations

**Credits:**
- Feature requested by @dlp688 (Discussion #28)
- Battery mode values confirmed by @maxroberts999 via testing
- API documentation from Reddit community and pypvs library

---

### Enhancement: New Inverter Discovery Notification

**Added notifications when new/replacement inverters are discovered**
- Users now receive notification when replacement or additional inverters are added
- Shows how many new inverters were discovered and total count
- Distinguishes between initial discovery (first time) and subsequent additions
- Uses `force_notify=True` so notifications always appear

**Example notification:**
> ☀️ New Inverters Detected!
>
> Enhanced SunPower discovered 2 new inverters and created all sensor entities.
>
> Total inverters now: 32

**How it works:**
- Stores list of known inverter serials in config entry (persists across HA restarts)
- Compares current inverters against this persistent list to identify genuinely new ones
- Only adds new inverters to the list, never removes (prevents false "new inverter" notifications when inverters temporarily go offline)
- Initial setup: Adds all inverters to known list and notifies once
- Later additions: Only notifies about genuinely new inverters not in the known list

**Important Notes:**
- **One-time migration notification:** On first update to v2025.11.3, you'll receive a notification about all your existing inverters as the system builds the initial known inverter list. This is expected and will only happen once.
- **Offline inverters:** Temporarily offline inverters (failures, nighttime issues) remain in the known list, so they won't trigger "new inverter" notifications when they recover
- **Replaced inverters:** Physically replaced inverters are correctly detected as new and trigger notifications
- **Old inverter cleanup:** Serial numbers of permanently removed inverters stay in the config (harmless, minimal storage). Delete and re-add the integration if you want to clean up historical serials.

**Files Modified:**
- `sensor.py`: Lines 103, 131-145, 215-275 - Persistent inverter tracking and notification logic

**Impact:**
- Users know immediately when new/replacement inverters come online
- No false "new inverter" notifications on HA restarts or temporary failures
- Helpful for confirming replacement inverters are recognized
- Works correctly with health monitoring (24-hour persistent error tracking)

---

### Bug Fix: RuntimeWarning in Coordinator Listener

**Fixed "coroutine was never awaited" warning in entity discovery**
- Home Assistant logs showed RuntimeWarning from update_coordinator.py
- Warning: "coroutine 'async_setup_entry.<locals>._async_add_entities_when_ready' was never awaited"
- Coordinator listener callback was async but called synchronously

**Root Cause:**
- `coordinator.async_add_listener()` expects a synchronous callback function
- We were passing an async function, which never got awaited
- Caused runtime warnings and potentially prevented dynamic discovery from working

**The Fix:**
- Changed listener callback from async to sync function
- Use `hass.async_create_task()` to schedule the async entity creation work
- Callback now properly executes without warnings

**Files Modified:**
- `sensor.py`: Lines 67-74 - Synchronous callback with scheduled async task
- `binary_sensor.py`: Lines 56-63 - Synchronous callback with scheduled async task

**Impact:**
- No more RuntimeWarning in logs
- Dynamic discovery now works reliably
- Proper async/await handling for entity creation

---

### Bug Fix: Dynamic Device Discovery Not Working

**Fixed new inverters not being auto-discovered after initial setup**
- When users replaced failed inverters, new units weren't automatically discovered
- Integration only listened for new devices during initial setup (when no data exists)
- Once data was present, the coordinator listener was never set up
- New inverters added later would never appear without deleting/re-adding the integration

**Root Cause:**
- `sensor.py` and `binary_sensor.py` only created coordinator listeners in the "no data" code path
- After initial setup with data present, no listener existed for ongoing device discovery
- The `created_entities` tracking system worked correctly, but was never called for new devices

**The Fix:**
- Moved coordinator listener setup outside the conditional block in both files
- Listener now always active, handling both initial setup AND ongoing discovery
- New inverters will auto-discover on next poll cycle (default: 5 minutes)

**Files Modified:**
- `sensor.py`: Lines 65-87 - Coordinator listener now always active
- `binary_sensor.py`: Lines 54-76 - Coordinator listener now always active

**Impact:**
- New inverters auto-discovered within one polling cycle (no integration reload needed)
- Replacement inverters appear automatically after PVS recognizes them
- Battery systems added later will be auto-discovered
- Users no longer need to delete/re-add integration for new devices

---

### Bug Fix: Firmware Upgrade Notification TypeError

**Fixed crash in firmware upgrade notification**
- When PVS firmware was upgraded, health check threw TypeError every 5 minutes
- Error: "notify_firmware_upgrade() takes 5 positional arguments but 6 were given"
- Notification system failed silently, users never received firmware upgrade alerts

**Root Cause:**
- `check_firmware_upgrade()` in `health_check.py` called notification function with 6 arguments
- `notify_firmware_upgrade()` in `notifications.py` only accepts 5 arguments
- Extra `serial` argument passed but not needed (notification uses entry.unique_id)

**The Fix:**
- Removed unnecessary `serial` argument from function call (health_check.py:290)
- Function signature now matches: `notify_firmware_upgrade(hass, entry, cache, old_version, new_version)`

**Files Modified:**
- `health_check.py`: Line 290 - Removed extra `serial` argument

**Impact:**
- Firmware upgrade notifications now work correctly
- No more repeated TypeError errors in logs during firmware updates
- Users will receive proper notification when PVS firmware is upgraded

---

## [v2025.11.2] - 2025-11-05

### Bug Fix: Dynamic Device Discovery Not Working

**Fixed new inverters not being auto-discovered after initial setup**
- When users replaced failed inverters, new units weren't automatically discovered
- Integration only listened for new devices during initial setup (when no data exists)
- Once data was present, the coordinator listener was never set up
- New inverters added later would never appear without deleting/re-adding the integration

**Root Cause:**
- `sensor.py` and `binary_sensor.py` only created coordinator listeners in the "no data" code path
- After initial setup with data present, no listener existed for ongoing device discovery
- The `created_entities` tracking system worked correctly, but was never called for new devices

**The Fix:**
- Moved coordinator listener setup outside the conditional block in both files
- Listener now always active, handling both initial setup AND ongoing discovery
- New inverters will auto-discover on next poll cycle (default: 5 minutes)

**Files Modified:**
- `sensor.py`: Lines 65-87 - Coordinator listener now always active
- `binary_sensor.py`: Lines 54-76 - Coordinator listener now always active

**Impact:**
- New inverters auto-discovered within one polling cycle (no integration reload needed)
- Replacement inverters appear automatically after PVS recognizes them
- Battery systems added later will be auto-discovered
- Users no longer need to delete/re-add integration for new devices

---

### Bug Fix: Firmware Upgrade Notification TypeError

**Fixed crash in firmware upgrade notification**
- When PVS firmware was upgraded, health check threw TypeError every 5 minutes
- Error: "notify_firmware_upgrade() takes 5 positional arguments but 6 were given"
- Notification system failed silently, users never received firmware upgrade alerts

**Root Cause:**
- `check_firmware_upgrade()` in `health_check.py` called notification function with 6 arguments
- `notify_firmware_upgrade()` in `notifications.py` only accepts 5 arguments
- Extra `serial` argument passed but not needed (notification uses entry.unique_id)

**The Fix:**
- Removed unnecessary `serial` argument from function call (health_check.py:290)
- Function signature now matches: `notify_firmware_upgrade(hass, entry, cache, old_version, new_version)`

**Files Modified:**
- `health_check.py`: Line 290 - Removed extra `serial` argument

**Impact:**
- Firmware upgrade notifications now work correctly
- No more repeated TypeError errors in logs during firmware updates
- Users will receive proper notification when PVS firmware is upgraded

---

## [v2025.11.1] - 2025-11-01

### Bug Fix: Home Assistant State Class Violations

**Fixed "state is not strictly increasing" warnings for lifetime power sensors**
- Home Assistant Recorder was logging warnings every 15-30 minutes
- Lifetime power values were decreasing by tiny amounts (0.000122 kWh) due to floating point precision
- Violated HA's `total_increasing` state class requirement (values must only increase)

**Root Cause:**
- PVS returns slightly different floating point values for lifetime energy across polls
- Rounding errors caused values like 1665.559204 → 1665.559082 (decrease of 0.000122 kWh)
- Home Assistant's statistics system rejected these as invalid decreases

**The Fix:**
- Round all lifetime energy values to 2 decimal places (0.01 kWh = 10 Wh precision)
- Applied to inverters, meters, and virtual meters in both pypvs and legacy methods
- Values now only change by minimum 0.01 kWh, eliminating float jitter

**Files Modified:**
- `pypvs_converter.py`: Lines 95, 133, 150, 152 - Round lifetime energy for new firmware
- `data_processor.py`: Lines 136, 138 - Round lifetime energy for virtual meters (old firmware)

**Impact:**
- No more "state class total_increasing" warnings in Home Assistant logs
- Energy statistics remain accurate (10 Wh precision is more than sufficient)
- Both new firmware (pypvs) and old firmware (dl_cgi) fixed

---

### Enhancement: Nighttime Error Suppression & Auth Session Management

**Contributor:** Special thanks to [@jtooley307](https://github.com/jtooley307) for these improvements (PR #30)

**Nighttime Login Error Suppression (Sun Elevation Aware)**
- Suppresses expected "Login to the PVS failed" errors when sun is below horizon
- Prevents log spam during nighttime hours when inverters are offline/asleep
- Only filters errors when sun elevation < 0 degrees (nighttime)
- Daytime authentication errors remain visible for troubleshooting
- Applies to both pypvs inverter and meter updater loggers

**Why This Matters:**
- pypvs library throws "login failed" errors when inverters don't respond at night
- PVS is accessible, meters work, authentication works - inverters are just offline
- Generated hundreds of error messages every night (every 5-10 minutes)
- Now logs are clean at night while preserving visibility of real daytime issues

**Proactive Authentication Refresh (New Firmware)**
- Changed auth refresh interval from 3600s (1 hour) to 600s (10 minutes)
- Prevents session expiration errors before they occur
- Logging changed from INFO to DEBUG (reduces log noise)
- Only affects new firmware (BUILD >= 61840) using pypvs

**Additional Logging Improvements:**
- "No inverters found" message changed from WARNING to DEBUG (expected at night)
- Proactive re-auth messages now at DEBUG level (reduces routine log noise)

**Files Modified:**
- `__init__.py`: Lines 173, 686-692, 697-733 - Auth refresh + nighttime filter with sun elevation
- `pypvs_converter.py`: Line 110 - Logging level improvement

**Impact:**
- Dramatically cleaner logs during nighttime hours (no more "login failed" spam)
- Reduced authentication session failures through proactive refresh
- Real authentication problems during daytime remain visible
- Debug logging for routine operations (enable if troubleshooting needed)

---

## [v2025.10.20] - 2025-10-27

### Bug Fix: Incorrect Authentication Notifications for Old Firmware

**Fixed misleading auth failure notifications for old firmware users (BUILD < 61840)**
- Users with old firmware (legacy dl_cgi) were receiving "Authentication Failed" notifications
- Error occurred when polling failed and error message contained auth-related keywords
- Old firmware does NOT require authentication, notification was incorrect and misleading
- Caused notification spam (every poll cycle) for users experiencing network issues

**Root Cause:**
- `_handle_polling_error()` function checked for auth-related keywords in ALL error messages
- Function is ONLY called for legacy dl_cgi method (old firmware, no auth required)
- If old firmware error message contained words like "authentication" or "check pvs serial", showed wrong notification
- Notification said "new firmware requires authentication" when user actually has OLD firmware

**The Fix:**
- Removed auth-checking logic from `_handle_polling_error()` function (__init__.py lines 457-461)
- Now only shows standard polling failure notification for old firmware
- Auth-related notifications only appear for new firmware (pypvs) where they're appropriate

**Impact:**
- Old firmware users (BUILD < 61840) no longer see misleading "Authentication Failed" spam
- Standard polling failure notifications still shown (appropriate for the actual problem)
- New firmware users unaffected (don't use this error handler)

**Error Notification (OLD - Incorrect):**
```
🔒 CRITICAL: Enhanced SunPower Authentication Failed!
The new firmware requires authentication but login failed.
```

**Error Notification (NEW - Correct):**
```
❌ Enhanced SunPower polling failed.
URL: http://192.168.1.x/cgi-bin/dl_cgi?Command=DeviceList
Error: [actual error message]
```

**Files Modified:**
- `__init__.py`: Lines 457-461 - Removed misleading auth checks from legacy error handler

**Issues Fixed:**
- Issue #27 (BUILD 61829 user receiving auth failure notification spam)

---

## [v2025.10.19] - 2025-10-25

### Resilience Improvement: Integration Setup Failure Handling

**Fixed integration complete failure when PVS temporarily unreachable during Home Assistant startup**
- Integration now survives temporary PVS unavailability during HA restart
- Previously: If PVS unreachable during `async_setup_entry`, entire integration failed to load
- Now: Setup continues gracefully, coordinator handles authentication retry on first poll
- Entities show "unavailable" until PVS responds, then populate normally

**Root Cause:**
- `async_setup_entry` called `await pvs_object.setup(auth_password=auth_password)` (line 568)
- If PVS unreachable (network lag, PVS rebooting, etc.), exception was re-raised (line 573)
- `raise` statement killed entire integration setup before coordinator could be created
- Coordinator's excellent retry/fallback logic never had a chance to run

**The Fix:**
- Removed `raise` statement that killed integration setup (__init__.py line 573)
- Changed error log level from ERROR to WARNING (temporary condition)
- Set `cache.last_auth_time = 0` to mark authentication needed
- Coordinator's first poll attempts authentication and handles retry gracefully
- Leverages existing proactive re-auth and error handling logic (PR #23)

**Impact:**
- Integration survives HA restarts even if PVS temporarily offline/busy
- No more "failed to setup" errors from network timing issues
- Entities show as "unavailable" until PVS responds, then auto-recover
- Better user experience during PVS firmware updates, reboots, or network lag

**Error Condition:**
```
OSError: [Errno 113] Connect call failed ('192.168.1.73', 443)
pypvs.exceptions.PVSError: General error
Error setting up entry None for sunpower
```

**Files Modified:**
- `__init__.py`: Lines 572-575 - Removed fatal `raise`, added graceful degradation with coordinator retry

**When This Occurs:**
- Home Assistant restarts while PVS is rebooting
- Network comes up slower than HA during startup
- PVS performing maintenance operations
- Brief network connectivity issues during HA startup
- Any scenario where PVS temporarily unreachable at exact moment of integration setup

---

### New Feature: Polling Control Switch

**User-controlled polling enable/disable for nighttime disk I/O reduction**
- New switch entity: `switch.sunpower_{serial}_polling_enabled`
- Default: ON (polling enabled)
- Turn OFF: Coordinator skips PVS poll, returns cached data without network traffic
- Turn ON: Resumes normal PVS polling
- Entities retain last known values when polling disabled

**Diagnostic Integration:**
- New `POLLING_STATUS` diagnostic sensor shows "Enabled" or "Disabled"
- Cached data notification explains when polling disabled by user
- Clear visibility into current polling state

**Use Case:**
- Reduce PVS disk I/O during nighttime hours (potential log writes, varserver operations)
- User control via automations based on sun elevation, time, or other triggers
- Inverters offline at night anyway - no fresh data to collect

**Implementation:**
- Switch stored in `config_entry.options["polling_enabled"]` (persists across restarts)
- Coordinator checks flag at start of each poll cycle
- Returns cached data without PVS communication when disabled
- Notifications sent when switch toggled (with clear explanation)

**Sample Automation (Sun-Based):**
```yaml
automation:
  - alias: "Disable PVS polling at sunset"
    trigger:
      - platform: sun
        event: sunset
        offset: "+00:30:00"  # 30 minutes after sunset
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.sunpower_{your_serial}_polling_enabled

  - alias: "Enable PVS polling before sunrise"
    trigger:
      - platform: sun
        event: sunrise
        offset: "-00:15:00"  # 15 minutes before sunrise
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.sunpower_{your_serial}_polling_enabled
```

**Sample Automation (Time-Based):**
```yaml
automation:
  - alias: "PVS polling schedule"
    trigger:
      - platform: time
        at: "20:00:00"  # 8 PM - disable
      - platform: time
        at: "06:00:00"  # 6 AM - enable
    action:
      - service: >
          {% if now().hour == 20 %}
            switch.turn_off
          {% else %}
            switch.turn_on
          {% endif %}
        target:
          entity_id: switch.sunpower_{your_serial}_polling_enabled
```

**Files Modified:**
- `switch.py`: New file - polling control switch implementation (lines 1-103)
- `notifications.py`: Added `notify_polling_enabled()` and `notify_polling_disabled()` functions (lines 524-547)
- `notifications.py`: Updated `notify_using_cached_data()` to detect polling disabled (lines 444-450)
- `const.py`: Added `POLLING_STATUS` diagnostic sensor definition (lines 671-679)
- `__init__.py`: Added polling check in coordinator `async_update_data()` (lines 603-615)
- `__init__.py`: Updated `create_diagnostic_device_data()` to include `polling_status` field (line 176, 216, 235)
- `__init__.py`: Registered switch platform (line 109)

**User Request:**
- Requested in Issue #25 as alternative to built-in sun elevation polling logic
- User control preferred over automatic behavior
- Addresses potential PVS disk wear concerns from continuous polling

---

## [v2025.10.18] - 2025-10-23

### CRITICAL Bug Fix: Additional None-Check and Notification Logic

**Fixed firmware_build None comparison in health checks**
- Fixed crash in `health_check.py` during flash memory monitoring
- Error: `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`
- Occurred every poll cycle when BUILD number unavailable (PVS5 systems, restricted networks)
- Non-fatal but filled logs with errors

**Fixed inverter discovery notification logic**
- Notification now fires only once on true first discovery (not on every HA restart)
- Added persistent flag `inverters_discovered_notified` to config entry
- Prevents notification at night when inverters offline (HA restart scenario)
- Debug log message when inverters rediscovered after restart

**Root Cause:**
- v2025.10.17 fixed config_flow.py firmware_build comparisons but missed health_check.py
- Flash memory threshold check: `85 if firmware_build >= 61840 else 0` crashed with None
- Inverter notification: `created_entities` set was in-memory only, cleared on every restart
- Entity recreation after restart triggered notification even though inverters not newly discovered

**The Fix:**
- Added `or 0` to firmware_build retrieval in health_check.py (line 362)
- Added persistent flag check before sending inverter notification (sensor.py lines 205-218)
- Updates config entry data to track notification sent across restarts

**Impact:**
- PVS5 users no longer see flash memory errors every poll cycle
- Inverter discovery notification fires once on true discovery, not every restart
- Clean logs, appropriate notifications

**Battery System Enhancement:**
- Added missing ESS lifetime energy sensors for Energy Dashboard
- `ESS_POS_LIFETIME_ENERGY` - Lifetime energy discharged (kWh)
- `ESS_NEG_LIFETIME_ENERGY` - Lifetime energy charged (kWh)
- Required for proper Energy Dashboard battery tracking

**Files Modified:**
- `health_check.py`: Line 362 - Added `or 0` for None-safe firmware_build comparison
- `sensor.py`: Lines 205-218 - Added persistent flag to track inverter discovery notification
- `battery_handler.py`: Lines 476-491 - Added missing ESS lifetime energy sensors

**Issues Fixed:**
- Discussion #21 (andreasplesch - PVS5 BUILD 5408 health check errors)
- Discussion #24 (cdug619 - Missing ESS lifetime energy sensors)

---

## [v2025.10.17] - 2025-10-22

### CRITICAL Bug Fix: Additional None-Check for Firmware Build

**Fixed remaining firmware_build None comparison crashes in config flow**
- Fixed crash in notifications step: `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`
- Fixed crash in options flow when updating configuration
- Affects PVS5 systems and scenarios where firmware detection returns None

**Root Cause:**
- v2025.10.16 fixed initial BUILD comparison but missed subsequent uses
- When legacy detection doesn't return BUILD number, `firmware_build = None`
- Line 416 (notifications step): `if firmware_build >= 61840:` → TypeError crash
- Line 675 (options flow): `if firmware_build >= 61840:` → TypeError crash

**The Fix:**
- Added `or 0` to firmware_build retrieval: `firmware_build = self._basic_config.get("firmware_build", 0) or 0`
- Treats None as 0 (old firmware behavior) for flash memory threshold logic
- Setup completes successfully when BUILD unavailable

**UI Improvement:**
- Removed outdated "Setup during daylight hours recommended" warnings
- Nighttime installation fully supported since v2025.10.14
- Cleaner config flow descriptions

**Impact:** PVS5 users and restricted network scenarios can now complete full setup without crashes

**Files Modified:**
- `config_flow.py`: Lines 416, 675 - Added `or 0` for None-safe firmware_build comparison
- `translations/en.json`: Removed daylight hours warnings (setup and options flows)

**Issues Fixed:**
- Discussion #21 (andreasplesch - PVS5 BUILD 5408)
- Issue #22 (Originalme - PVS5 BUILD 5408)

---

## [v2025.10.16] - 2025-10-22

### CRITICAL Bug Fix: Config Flow Crash on Timeout

**Fixed TypeError crash when supervisor/info times out or is unreachable**
- Fixed crash: `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`
- Config flow now properly falls back to legacy detection when supervisor/info unreachable
- Prevents setup failure when PVS network is restricted (filtered ports, firewalls, etc.)

**Root Cause:**
- When `/cgi-bin/dl_cgi/supervisor/info` times out or is blocked by firewall
- Function returns `build = None` with error message
- Line 142 tried to compare `None >= MIN_LOCALAPI_BUILD` → TypeError crash
- Config flow would fail with "Unknown error occurred"

**The Fix:**
- Added `or build is None` check before using build variable
- Forces fallback to legacy detection when build is None
- Config flow completes without crashing

**Impact:** Users with network restrictions (filtered ports, firewall rules) can now complete setup using legacy detection fallback

**Files Modified:**
- `config_flow.py`: Line 135 - Added None-check for build variable

---

## [v2025.10.15] - 2025-10-21

### CRITICAL Bug Fix: Setup Reliability

**Integration Setup Now Succeeds on First Attempt**
- Fixed "Failed to setup" error requiring integration reload to work
- Fixed "Invalid flow specified" errors during setup
- Removed pypvs discovery call that was timing out during setup
- Removed zeroconf auto-discovery that was causing setup conflicts
- Integration now uses serial number already validated in config flow
- Setup completes in seconds instead of timing out and failing

**Root Cause:**
- During setup, integration called `pvs_object.discover()` to get PVS serial number
- Discovery made multiple rapid requests to `/vars` endpoint
- PVS connection would timeout, causing setup failure
- User had to manually reload integration to retry setup
- Serial number was already collected and validated during config flow
- Zeroconf auto-discovery was running background processes that interfered with manual setup
- Multiple simultaneous discovery/setup processes caused "Invalid flow specified" errors

**The Fix:**
- Skip `discover()` call during setup
- Use serial number from `entry.unique_id` (already validated in config flow)
- Only call `pvs_object.setup()` for authentication (much faster)
- No more multiple rapid requests that could timeout
- Removed zeroconf auto-discovery - users manually add integration (more reliable)

**Impact:** **ALL users with new firmware (BUILD >= 61840)** - integration setup should now complete successfully on first attempt without requiring manual reload

**Files Modified:**
- `__init__.py`: Lines 556-565 - Removed `discover()` call, use serial from config flow
- `manifest.json`: Removed zeroconf section - no more auto-discovery

---

## [v2025.10.14] - 2025-10-20

### New Features

**Nighttime Installation Support**
- Setup now succeeds even when inverters are offline (nighttime installation)
- Dynamic entity discovery - entities created automatically when devices come online
- User notification when inverters discovered and all sensors created
- Coordinator listener pattern monitors for device availability
- No more "Install during daylight hours!" restriction

**Implementation:**
- Entity tracking prevents duplicate creation on coordinator updates
- Deferred entity creation for both sensors and binary sensors
- Hybrid field checking - only creates entities when field exists AND has value
- `notify_inverters_discovered()` notifies user when solar system fully monitored

**Impact:** Users can now install the integration anytime - entities will populate automatically at sunrise when inverters power on

**Files Modified:**
- `sensor.py`: Added coordinator listener, entity tracking, deferred creation logic
- `binary_sensor.py`: Same pattern for binary sensors
- `notifications.py`: Added `notify_inverters_discovered()` function
- `pypvs_converter.py`: Added STATE/STATEDESCR to ESS devices (was missing)

**Contributor:** Special thanks to [@jtooley307](https://github.com/jtooley307) for implementing this feature (PR #18)

---

### Technical Improvements

**Enhanced Exception Logging for Troubleshooting**
- Added full stack traces to config flow validation errors
- No user configuration required - visible in default Home Assistant logs
- Helps diagnose connection failures, authentication issues, and network problems
- Users can now provide complete error details in bug reports

**Impact:** Faster troubleshooting and diagnosis of setup issues without requiring debug mode

**Files Modified:**
- `config_flow.py`: Added `exc_info=True` to critical exception handlers (lines 53, 158, 172, 189)

---

## [v2025.10.13] - 2025-10-18

### Code Quality Improvements

**SunStrong Migration Moved to Standalone Tool (Experimental - Not Yet Released)**
- Removed in-integration migration code (converter.py deleted, __init__.py simplified)
- Created standalone Python script: `tools/migrate_from_sunstrong.py` (testing in progress)
- Cleaner integration code - no permanent migration logic in main codebase
- Migration tool will be announced after testing is complete

### New Features

**Transfer Switch Support (New Firmware)**
- Added transfer switch (PV Disconnect) device support for new firmware battery backup systems
- **Sensors**: Main breaker state, PV disconnect state, temperature, grid voltages (L1/L2), load voltages (L1/L2), supply voltage
- **Impact**: Battery backup users can now monitor transfer switch status in Home Assistant
- **File Modified**: pypvs_converter.py (lines 201-226) - Convert pypvs transfer_switches to legacy format
- **Note**: Sensor definitions already existed in const.py, just needed converter implementation

---

### CRITICAL Bug Fix: Battery SOC Showing Wrong Values (New Firmware)

**Battery State of Charge Fixed:**
- Fixed battery SOC showing 0.876% when it should show 87.6% (100x too small!)
- Fixed battery SOH (State of Health) showing wrong percentage
- Fixed customer SOC showing wrong percentage
- pypvs provides SOC as decimal (0-1), we weren't multiplying by 100 for percentage display

**Root Cause:**
- pypvs PVSESS model provides SOC/SOH as decimals: `0.876` = 87.6% charge
- pypvs_converter.py passed through raw decimal without conversion
- Result: "0.876%" displayed instead of "87.6%"
- Made batteries look nearly dead when they were actually healthy

**The Fix:**
- Multiply pypvs SOC/SOH values by 100 before conversion
- `soc_val * 100`, `customer_soc_val * 100`, `soh_val * 100`
- Now displays correct percentage values

**Impact:** **ALL new firmware users (BUILD >= 61840) with battery systems** - battery percentages now show correctly

**Files Modified:**
- `pypvs_converter.py`: Added percentage conversion for SOC/SOH fields (lines 178-181)

---

### Bug Fix: Missing Firmware/Hardware Versions (New Firmware)

**Firmware/Hardware Display Fixed:**
- Fixed "Firmware: Unknown Hardware: Unknown" showing for all inverters, meters, and ESS devices on new firmware
- Added placeholder values for pypvs devices until library provides actual firmware/hardware data
- pypvs library regression - old firmware dl_cgi provided these fields, new firmware pypvs doesn't

**Root Cause:**
- pypvs library models (PVSInverter, PVSESS, PVSMeter) don't include firmware/hardware version fields
- Only PVS Gateway provides software_version and hardware_version
- Old firmware dl_cgi provided: inverters (SWVER: "4.21.4", hw_version: "4403"), batteries (SWVER: "2.8", hw_version: "4.51")
- New firmware LocalAPI/varserver likely has this data but pypvs models don't extract it

**Temporary Fix (until pypvs updated):**
- Inverters: `SWVER: "pypvs"`, `HWVER: <model name>` (e.g., "AC_Module_Type_H")
- ESS devices: `SWVER: "pypvs"`, `HWVER: <model name>` (e.g., "SPWR-Equinox-model")
- Shows actual model instead of "Unknown" which looks broken to users

**Impact:** New firmware users (BUILD >= 61840) - devices now show placeholder firmware/hardware instead of "Unknown"

**GitHub Issue:** Opened issue with SunStrong/pypvs to add firmware/hardware fields to device models

**Files Modified:**
- `pypvs_converter.py`: Added SWVER/HWVER placeholders for inverters and ESS devices (lines 90-91, 175-176)

---

## [v2025.10.12] - 2025-10-16

### Bug Fix: New Firmware Battery Sensors (pypvs ESS Support)

**New Firmware Battery Sensors Fixed:**
- Fixed battery systems on new firmware (BUILD >= 61840) showing only "ESS State" binary sensor
- Added 15 new ESS sensor definitions that match pypvs PVSESS model field names
- pypvs ESS data now properly creates full battery sensor suite instead of just binary sensor

**Root Cause:**
- pypvs library DOES provide ESS data via PVSESS model with NEW field names (soc_val, customer_soc_val, power_3ph_kw, etc.)
- pypvs_converter.py successfully converted ESS data with these NEW field names
- BUT battery_handler.py ESS sensor definitions expected OLD field names (enclosure_humidity, agg_power, meter_a_current, etc.)
- sensor.py skips sensors when field doesn't exist in device data (lines 84-86)
- Result: All ESS sensors were skipped except binary sensor (which has no field validation)

**New Sensors Added (pypvs/new firmware only):**
- ESS State of Charge (soc_val) - Main battery charge percentage
- ESS Customer State of Charge (customer_soc_val) - Customer-visible SOC
- ESS State of Health (soh_val) - Battery degradation tracking
- ESS Power (power_3ph_kw) - Real-time battery charge/discharge rate
- ESS Battery Voltage (v_batt_v) - Total battery pack voltage
- ESS Inverter Temperature (t_invtr_degc) - Storage inverter thermal monitoring
- ESS Operating Mode (op_mode) - Current operational state
- ESS Charge/Discharge Limits (chrg_limit_pmax_kw, dischrg_lim_pmax_kw)
- ESS Cell Temperature Min/Max (min_t_batt_cell_degc, max_t_batt_cell_degc)
- ESS Cell Voltage Min/Max (min_v_batt_cell_v, max_v_batt_cell_v)
- ESS V1N/V2N Voltages (v1n_v, v2n_v)

**Impact:** New firmware users (BUILD >= 61840) with battery systems - now see full battery sensor suite instead of just binary sensor

**Files Modified:**
- `battery_handler.py`: Added 15 new pypvs ESS sensor definitions (lines 342-474)

---

### Bug Fix: Battery Detection on First Poll

**First-Poll Battery Detection Fixed:**
- Fixed battery systems not creating sensors until second integration restart
- Battery detection now checks fresh poll data immediately (was only checking cache)
- ESS endpoint now polled on first poll if batteries present in device list
- Fixes "only seeing ESS State binary sensor" issue for OLD firmware battery users

**Root Cause:**
- Battery detection relied on `cache.previous_pvs_sample` which is empty on first poll
- ESS endpoint was never polled until cache populated (required restart)
- Fresh data available but not checked for battery devices before ESS polling decision

**Impact:** Old firmware users (BUILD < 61840) with battery systems - ESS sensors now appear immediately on first restart

**Files Modified:**
- `__init__.py`: Added fresh data battery detection check (lines 858-868)

---

### New Features: Diagnostics Download

**Home Assistant Diagnostics Support:**
- Added native HA diagnostics download feature accessible from integration device page
- One-click download captures all troubleshooting data in single JSON file
- No Python installation or command-line access required - works on all platforms (Windows/Mac/Linux)

**Diagnostics Data Captured:**
- Complete raw PVS polling data (device list with all inverters, meters, batteries)
- Integration configuration (host, polling interval, thresholds, all settings)
- Coordinator state (update success, polling intervals, last update time)
- Device summary (counts by type: PVS, inverters, meters, batteries)
- Diagnostic stats (total polls, success rate, response times, consecutive failures)
- Battery detection status (if battery system was ever detected)
- Firmware tracking (last known BUILD number)
- Inverter health tracking (expected inverters, failure counts)

**Usage:** Navigate to integration device page → Click "Download diagnostics" → Share JSON file for support

**Files Added:**
- `diagnostics.py`: Comprehensive diagnostics data collection module

**Files Modified:**
- `__init__.py`: Added cache object to hass.data for diagnostics access

**Impact:** All users - simplifies troubleshooting and support requests

---

### Improvements: Automatic Re-Authentication (New Firmware)

**Automatic Session Recovery:**
- Added automatic re-authentication when PVS session cookies expire
- Transparent retry on authentication errors (401, 403, unauthorized)
- Prevents "authentication expired" repair notifications
- No user action required when sessions expire

**How It Works:**
1. Integration detects authentication error during polling
2. Automatically re-authenticates using stored password
3. Retries the poll operation seamlessly
4. Logs show: "⚠️ Authentication error detected" → "✅ Re-authentication successful"

**Cookie Inspection (Temporary):**
- Added debug logging to inspect PVS session cookie expiration times
- Helps understand PVS session behavior
- Will be removed once cookie behavior is documented

**Files Modified:**
- `__init__.py`: Added auth error detection and automatic retry logic (lines 749-790)
- `__init__.py`: Added cookie inspection logging after authentication (lines 619-634)

**Impact:** New firmware users (BUILD >= 61840) - prevents authentication interruptions from expired sessions

**Related Issue:** Addresses authentication stability issues similar to SunStrong Management pvs-hass#11

---

### Bug Fixes: Diagnostic Device Sensors

**PVS Uptime Sensor Fixed:**
- Fixed PVS Uptime showing 0% after integration restarts
- Changed calculation from broken time-based math to poll success rate
- Previous logic: `total_runtime - (failed_polls * 300)` resulted in negative values → 0%
- New logic: PVS Uptime now matches Poll Success Rate (both show same percentage)

**Consecutive Poll Failures Fixed:**
- Fixed sensor showing total failed polls instead of consecutive failures
- Now correctly resets to 0 on successful poll and increments only during consecutive failures

**Files Modified:**
- `__init__.py`: Lines 198-200 - Simplified uptime calculation to use success rate
- `__init__.py`: Line 228 - Fixed consecutive failures to use correct stat counter

**Impact:** All users - diagnostic sensors now report accurate values

---

### Improvements: Battery System Logging

**Reduced Log Spam:**
- Battery entity count now only logs at INFO when count changes (catches issues immediately)
- Normal ESS polling success moved to DEBUG level (was INFO every 30-60 seconds)
- First-time battery detection logs once at INFO: "Battery system detected - ESS polling will continue for all future polls"

**Enhanced Problem Detection:**
- Entity count changes logged at INFO: "Battery entity count changed: 3 → 0"
- Zero entities after processing logged at WARNING: "ESS data processed but no battery entities created (was 3)"
- Makes battery entity disappearance immediately visible without debug logging

**Impact:** Both old and new firmware - all SunVault/ESS battery users

**Files Modified:**
- `battery_handler.py`: Added one-time INFO log on first battery detection (lines 557-559)
- `__init__.py`: Changed ESS polling to only log INFO on entity count changes (lines 774-796)

**Debugging:** Enable debug logging to see every ESS poll attempt and result

---

## [v2025.10.11] - 2025-10-05

### New Features: Battery & Storage Health Monitoring

**ESS/Battery Sensors (New Firmware Only):**
Added 10 comprehensive battery sensors for pypvs users (BUILD >= 61840):
- State of Charge (SOC) - Current battery charge percentage
- State of Health (SOH) - Battery degradation tracking for long-term monitoring
- Power - Real-time battery charge/discharge rate (kW)
- Operating Mode - Current ESS operational state
- Battery Voltage - Total battery pack voltage
- Inverter Temperature - Storage inverter thermal monitoring
- Max Cell Temperature - Hottest battery cell temperature
- Min Cell Temperature - Coldest battery cell temperature
- Max Charge Power - System charge capability limit
- Max Discharge Power - System discharge capability limit

**PVS Flash Wear Monitoring:**
- Flash Wear % sensor - EMMC lifetime estimation (0x01 = 10%, 0x09 = 90%)
- Configurable daily alert threshold (default 90% wear = 10% remaining)
- Provides early warning before PVS storage failure
- Requires new firmware (BUILD >= 61840) with varserver query support

**Night-time Inverter Caching:**
- Inverters and virtual production meter now remain visible at night with last known daytime values
- Cache automatically preserves inverter data when they go offline after sunset
- Prevents entity unavailable/unknown states during night hours
- Works for both old and new firmware

**Automatic Discovery (Zeroconf):**
- Added PVS5 and PVS6 automatic discovery support
- Home Assistant now automatically detects PVS systems on network
- Pre-fills IP address during configuration for easier setup
- Works with both new and old firmware

**Dependency Updates:**
- Updated pypvs requirement to `>=0.2.4` (from unversioned)
- Ensures users get pypvs v0.2.4 bug fix: "Fixed sporadic issue while enumerating a PVS"
- Auto-updates on next HA restart/integration reload

### Critical Bug Fixes

**Battery Polling Stops After Hours (Issue #5):**
- **Problem:** Battery entities work initially but become unavailable after a few hours with no errors
- **Root Cause:** Battery detection re-checked every poll - when battery devices disappeared from PVS device list (STATE="error" is normal), ESS polling stopped entirely
- **Fix:** Battery detection now persistent once detected - ESS endpoint polled continuously regardless of PVS device list
- **Impact:** Both old and new firmware - all SunVault/ESS battery users
- **Files Modified:** `battery_handler.py` (lines 537-560), `__init__.py` (lines 153-154, 769-791)

**Health Check Startup Crash:**
- **Problem:** Integration blocked HA startup with error: "'set' object does not support item assignment"
- **Root Cause:** `cache.startup_notifications_sent` initialized as `set()` instead of `dict`
- **Fix:** Changed to dict initialization and updated all references from `.add()` to dict assignment
- **Impact:** Both old and new firmware - blocked flash wear/memory alerts and health checks
- **Files Modified:** `__init__.py` (line 141), `notifications.py` (line 250)

**Files Modified:**
- `pypvs_converter.py`: Fixed ESS converter to map all PVSESS model fields (lines 163-191)
- `const.py`: Added ESS_DEVICE_TYPE sensor definitions (lines 348-439), PVS_FLASH_WEAR sensor (lines 202-210)
- `__init__.py`: Added flashwear_type_b varserver query after pypvs update (lines 656-673), night-time inverter cache preservation (lines 694-718, 723-751), battery persistence fix (lines 153-154, 769-791), health check dict fix (line 141)
- `translations/en.json`: Added flash wear threshold labels and descriptions
- `manifest.json`: Added zeroconf discovery for PVS5/PVS6 systems (lines 21-28), updated pypvs requirement to >=0.2.4 (line 16)
- `battery_handler.py`: Persistent battery detection (lines 537-560)
- `notifications.py`: Fixed startup notification dict usage (line 250)

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
