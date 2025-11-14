# Migrating from krbaker SunPower Integration

**⚠️ CRITICAL: BACKUP YOUR SYSTEM FIRST!** This is a one-way migration process.

## Overview

Enhanced SunPower is a community-maintained fork of [@krbaker's original SunPower integration](https://github.com/krbaker/hass-sunpower) with new firmware support, improved reliability, and enhanced monitoring features.

**Entity Compatibility:**
- ✅ **100% backward compatible** - Same entity IDs as krbaker
- ✅ **History preserved** - No data loss during migration
- ✅ **Energy Dashboard** - Existing configurations continue working

**Breaking Changes:**
- **Binary Sensors**: Now use proper boolean states (`on`/`off`) instead of text values like `"working"`. May break existing automations that check for text values.

## Migration Steps

**⚠️ GO SLOW - Follow each step exactly**

### 1. Backup Your System

Before starting, create a full Home Assistant backup:
- **Settings** → **System** → **Backups** → **Create Backup**

### 2. Remove Original Integration

- Go to **Settings** → **Devices & Services**
- Find **"SunPower"** integration
- Click **three dots menu** → **Delete**

### 3. Remove Original HACS Repository

If you installed krbaker via HACS:
- Go to **HACS** → **Integrations**
- Find **"SunPower"** → **three dots** → **Remove**
- Also remove custom repo: **HACS** → **3 dots (top right)** → **Custom repositories** → delete krbaker repository

### 4. Restart Home Assistant

**DO NOT SKIP THIS STEP**
- Go to **Settings** → **System** → **Restart**

### 5. Install Enhanced SunPower

Follow the [Installation Instructions](README.md#install-via-hacs) in the main README.

### 6. Clean Up Old Virtual Devices (Battery Systems Only)

If you have a SunVault battery system:
- krbaker created "Virtual Battery" and "Virtual SunVault" devices
- These will appear as orphaned/unavailable after migration
- **Safe to delete manually** - Enhanced SunPower uses real ESS devices instead
- Go to **Settings** → **Devices & Services** → **Entities**
- Search for **"virtual"**
- Delete orphaned virtual battery entities

## What Changed?

### Binary Sensor States

**Old krbaker behavior:**
```yaml
# Binary sensor showed text values
- condition: state
  entity_id: binary_sensor.pvs_communication
  state: "working"  # ❌ This will break
```

**Enhanced SunPower behavior:**
```yaml
# Binary sensor shows proper boolean
- condition: state
  entity_id: binary_sensor.pvs_communication
  state: "on"  # ✅ Use this instead
```

**Fix your automations:**
- Search for automations using SunPower binary sensors
- Replace text checks (`"working"`, `"error"`) with boolean checks (`"on"`, `"off"`)

### Battery System Changes

**Old krbaker approach:**
- Created virtual aggregation devices from ESS endpoint
- Limited sensor coverage
- Virtual device complexity

**Enhanced SunPower approach:**
- Uses real ESS devices from PVS
- Comprehensive sensor suite (SOC, voltage, current, temperature, power flow)
- Better device organization
- More accurate data

**Note:** Some calculated sensors (power input/output based on amperage) may be unavailable due to pypvs library limitations.

## Known Migration Issues

### Issue: Negative Lifetime Energy Values

**Symptoms:**
- Energy Dashboard shows negative spike after migration
- Production meter shows large negative value

**Cause:**
- Home Assistant statistics database adjustment during migration gap
- More common if integration was offline for extended period before migrating

**Solution:**
1. **Clean up statistics manually:**
   - **Developer Tools** → **Statistics**
   - Find affected entity (usually production power meter)
   - Delete negative adjustment entries
   - HA will recalculate Energy Dashboard graphs

2. **Switch to inverter entities (recommended):**
   - More resilient during migrations
   - Better troubleshooting visibility
   - See [Energy Dashboard Setup](README.md#energy-dashboard-integration)

**Reference:** [HA Community: Change Energy Dashboard Values](https://community.home-assistant.io/t/change-energy-dashboard-values/464683)



## Need Help?

- **Troubleshooting Guide:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Report Issues:** [GitHub Issues](https://github.com/smcneece/ha-esunpower/issues)
- **Ask Questions:** [GitHub Discussions](https://github.com/smcneece/ha-esunpower/discussions)

## Success Stories

Over 20 users have successfully migrated from krbaker to Enhanced SunPower with preserved entity history and no data loss. The integration has been production-tested since August 2025 with systems ranging from 10-30+ inverters.
