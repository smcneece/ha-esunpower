# SunStrong → Enhanced SunPower Migration Tool

Automatically migrate your SunStrong (pvs-hass) entities to Enhanced SunPower while preserving all historical data!

## Why Migrate?

Enhanced SunPower offers significant improvements over SunStrong:
- **Transfer switch support** - Monitor PV disconnect and backup system
- **Better battery monitoring** - 17 comprehensive ESS sensors
- **Active development** - Regular updates and bug fixes
- **Community support** - Growing user base and feature requests
- **Proven stability** - Extensive testing on both firmware versions

## Before You Start

**⚠️ IMPORTANT: Create a backup first!**
1. Go to Settings → System → Backups
2. Click "Create Backup"
3. Wait for backup to complete
4. **Only then** proceed with migration

## Migration Steps

### Step 1: Install Enhanced SunPower (DO NOT CONFIGURE YET!)

**Install the integration but don't set it up yet:**

See the install instructions on our github page: 


**⚠️ STOP HERE! Do not add the integration yet!**

### Step 2: Disable SunStrong Integration

1. **Disable SunStrong Integration** (DO NOT DELETE YET!)
   - Go to Settings → Devices & Services
   - Find "SunStrong PVS Monitoring"
   - Click the three dots → "Disable"
   - Entities will become "orphaned" but history is preserved

### Step 3: Run Migration Script

**The migration script is now available at:**
```
/config/custom_components/sunpower/tools/migrate_from_sunstrong.py
```

1. **Open Terminal Add-on** (Settings → Add-ons → Terminal - may also be on left menu bar of Home Assistant)

2. **Navigate to tools directory:**
   ```bash
   cd /config/custom_components/sunpower/tools
   ```

3. **Run the script:**
   ```bash
   python3 migrate_from_sunstrong.py
   ```

   Or run directly without changing directories:
   ```bash
   python3 /config/custom_components/sunpower/tools/migrate_from_sunstrong.py
   ```

3. **Follow the prompts:**
   - Confirm you have a backup
   - Provide PVS serial number (for gateway entities)
   - Provide PVS model (pvs5 or pvs6)
   - Review migration plan
   - Confirm migration

4. **Watch the progress:**
   ```
   ✅ Inverter        sensor.mi_e00122142080335_current_power_production
                      → sensor.sunpower_inverter_e00122142080335_p_3phsum_kw
   ✅ Power Meter     sensor.meter_pvs6m22283193p_3_phase_power
                      → sensor.sunpower_power_meter_pvs6m22283193p_p_3phsum_kw
   ...
   ```

### Step 4: Configure Enhanced SunPower

**Now it's safe to set up the integration:**

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Enhanced SunPower"
4. Follow setup wizard:
   - **Page 1:** Enter PVS IP address and polling interval
   - **Page 2:** Confirm password (auto-detected for new firmware)
   - **Page 3:** Configure notifications and advanced settings

### Step 5: Verify Migration

1. **Check Entity States:**
   - Developer Tools → States
   - Search for "sunpower"
   - Verify entities are updating with current data

2. **Check History:**
   - Click on any migrated entity
   - View "History" tab
   - Historical data should be intact!

3. **Test Automations:**
   - Your existing automations should work unchanged
   - Entity IDs have been updated automatically

### Step 6: Clean Up

1. **Delete SunStrong Integration:**
   - Settings → Devices & Services
   - Find "SunStrong PVS Monitoring"
   - Click three dots → "Delete"

2. **Remove SunStrong from HACS** (optional):
   - HACS → Integrations
   - Find "SunStrong"
   - Three dots → "Remove"

## What Gets Migrated?

### ✅ Fully Supported (100% compatibility)

- **Inverters** - All 6 sensors migrate perfectly
  - Current power, lifetime energy, voltage, current, frequency, temperature
- **Power Meters** - All sensors migrate
  - 3-phase power, lifetime energy, voltage, current, power factor, etc.
- **ESS/Battery** - All 17 sensors migrate
  - SOC, SOH, power, voltage, temperatures, charge limits, cell voltages
- **Transfer Switches** - All 8 sensors migrate (NEW!)
  - Main breaker state, PV disconnect, grid/load voltages, temperature
- **Gateway/PVS** - All 4 sensors migrate
  - Uptime, RAM usage, flash usage, CPU load

### ⚠️ Field Name Changes

These sensors are migrated but with updated field names (history preserved):
- **Inverter:** `current_power_production` → `p_3phsum_kw`
- **Meter:** `lte_3ph_kwh` → `net_ltea_3phsum_kwh`
- **Gateway:** `gateway_uptime` → `dl_uptime`

### ❌ Not Migrated (No Equivalent)

- **last_reported** (timestamp) - Not in Enhanced SunPower
- **voltage_3ph_v**, **current_3ph_a** - Aggregate values not tracked

### ⚠️ Known Limitations

**Battery SOC/SOH Historical Discontinuity (Battery Systems Only)**

If you have a battery system, you'll notice a visual discontinuity in the historical graphs for these sensors:
- `soc_val` (State of Charge)
- `customer_soc_val` (Customer State of Charge)
- `soh_val` (State of Health)

**Why this happens:**
- SunStrong stores these values as decimals (0-1 range) → Example: 0.876
- Enhanced SunPower stores them as percentages (0-100 range) → Example: 87.6%

**What you'll see:**
```
Historical graph shows values around 0.876
                                        ↓ JUMP at migration point
Current data shows values around 87.6%
```

**Is this a problem?**
- ❌ **Visual only** - Your historical data is NOT lost, just scaled differently
- ✅ **New data is correct** - Enhanced SunPower shows proper percentages (87.6% not 0.876%)
- ✅ **Automations work** - The underlying data is still valid for comparisons

**Workaround:**
If the graph discontinuity bothers you, create new "custom template sensors" that multiply old values by 100 for display purposes only. Ask in GitHub Discussions for template examples.

## Troubleshooting

### Migration Script Errors

**"Entity registry not found"**
- Make sure you're running the script on the Home Assistant system
- Check that `/config/.storage/core.entity_registry` exists

**"No SunStrong entities found"**
- SunStrong might already be deleted (check Settings → Devices)
- Migration already completed successfully

**"Permission denied"**
- Run as root in Terminal add-on: `sudo python3 /config/custom_components/sunpower/tools/migrate_from_sunstrong.py`

### After Migration

**Entities show "Unavailable"**
- Make sure Enhanced SunPower integration is installed and configured
- Restart Home Assistant
- Check that PVS IP address is correct in configuration

**History is missing**
- History is preserved in the database - may take time to load
- Check Developer Tools → Statistics for the entity
- Historical data queries can be slow on first load

**Automations not working**
- Check automation YAML - entity IDs should auto-update
- Manually update any hard-coded entity IDs in scripts
- Reload automations: Developer Tools → YAML → Automations

## Rollback (if needed)

If something goes wrong:

1. **Restore from backup:**
   - Settings → System → Backups
   - Select backup created before migration
   - Click "Restore"

2. **Re-enable SunStrong:**
   - Settings → Devices & Services
   - Find "SunStrong PVS Monitoring"
   - Click "Enable"

## Get Help

- **GitHub Issues:** https://github.com/smcneece/ha-esunpower/issues
- **Home Assistant Community:** Tag posts with "sunpower" or "esunpower"
- **Include diagnostics:** Settings → Devices → Enhanced SunPower → Download diagnostics

## Success Story Template

Share your migration success! Post in HA Community or GitHub Discussions:

```
Migrated from SunStrong to Enhanced SunPower successfully!

System:
- PVS Model: [pvs5/pvs6]
- Firmware: [BUILD number]
- Entities migrated: [X inverters, X meters, X battery sensors]

Results:
✅ All historical data preserved
✅ Automations working perfectly
✅ [New features you're enjoying]

Migration time: [X minutes]
```
