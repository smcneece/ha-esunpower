#!/usr/bin/env python3
"""
SunStrong → Enhanced SunPower Migration Fix-Up Script (Post-Configuration)

This script handles migration AFTER Enhanced SunPower has been configured.
It fixes the duplicate entity problem and preserves history.

USAGE:
1. Install Enhanced SunPower integration files
2. Restart Home Assistant
3. Configure Enhanced SunPower integration (creates config_entry with duplicates)
4. Disable SunStrong integration
5. Run this script: python3 fixup_migration_post_config.py
6. Script will automatically:
   - Stop HA Core
   - Delete duplicate entities
   - Adopt migrated SunStrong entities
   - Update recorder database (preserve history)
   - Restart HA Core

WARNING: This modifies core.entity_registry and home-assistant_v2.db
Create a backup before running!
"""

import json
import sys
import subprocess
import time
import sqlite3
from pathlib import Path
from datetime import datetime

# ===== CONFIGURATION =====
CONFIG_DIR = Path("/config")
ENTITY_REGISTRY_FILE = CONFIG_DIR / ".storage" / "core.entity_registry"
RECORDER_DB_FILE = CONFIG_DIR / "home-assistant_v2.db"

# Create timestamped log file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = CONFIG_DIR / f"sunstrong_migration_{TIMESTAMP}.log"
REGISTRY_BACKUP_BEFORE = CONFIG_DIR / f"entity_registry_before_{TIMESTAMP}.json"
REGISTRY_BACKUP_AFTER = CONFIG_DIR / f"entity_registry_after_{TIMESTAMP}.json"

# ===== LOGGING FUNCTIONS =====

def log(message, also_print=True):
    """Write to log file and optionally print to stdout"""
    with open(LOG_FILE, 'a') as f:
        f.write(f"{message}\n")
    if also_print:
        print(message)

def log_entity_details(entity, prefix=""):
    """Log detailed entity information"""
    log(f"{prefix}entity_id: {entity.get('entity_id')}")
    log(f"{prefix}unique_id: {entity.get('unique_id')}")
    log(f"{prefix}platform: {entity.get('platform')}")
    log(f"{prefix}config_entry_id: {entity.get('config_entry_id')}")
    log(f"{prefix}disabled_by: {entity.get('disabled_by')}")
    log(f"{prefix}device_id: {entity.get('device_id')}")

def log_registry_snapshot(registry, label):
    """Log registry statistics snapshot"""
    entities = registry['data']['entities']

    log(f"\n{'='*70}")
    log(f"REGISTRY SNAPSHOT: {label}")
    log(f"{'='*70}")
    log(f"Total entities: {len(entities)}")

    # Count by platform
    platforms = {}
    for e in entities:
        platform = e.get('platform', 'unknown')
        platforms[platform] = platforms.get(platform, 0) + 1

    log("\nEntities by platform:")
    for platform, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
        log(f"  {platform}: {count}")

    # Count by config_entry_id for sunpower platform
    sunpower_by_config = {}
    sunpower_disabled = 0
    for e in entities:
        if e.get('platform') == 'sunpower':
            config_id = e.get('config_entry_id')
            if config_id:
                sunpower_by_config[config_id] = sunpower_by_config.get(config_id, 0) + 1
            else:
                sunpower_by_config['NULL'] = sunpower_by_config.get('NULL', 0) + 1

            if e.get('disabled_by') is not None:
                sunpower_disabled += 1

    if sunpower_by_config:
        log("\nSunPower entities by config_entry_id:")
        for config_id, count in sunpower_by_config.items():
            log(f"  {config_id}: {count}")
        log(f"\nSunPower disabled entities: {sunpower_disabled}")

    log(f"{'='*70}\n")

# Field mapping: SunStrong → Enhanced SunPower
INVERTER_FIELD_MAP = {
    "current_power_production": "p_3phsum_kw",
    "lifetime_production": "ltea_3phsum_kwh",
    "production_current": "i_3phsum_a",
    "production_voltage": "vln_3phavg_v",
    "frequency": "freq_hz",
    "temperature": "t_htsnk_degc",
}

GATEWAY_FIELD_MAP = {
    "gateway_uptime": "dl_uptime",
    "ram_usage": "ram_usage_percent",
    "flash_usage": "flash_usage_percent",
    "cpu_usage": "dl_cpu_load",
}

METER_FIELD_MAP = {
    "lte_3ph_kwh": "net_ltea_3phsum_kwh",
    "pos_lte_kwh": "pos_ltea_3phsum_kwh",
}

# ===== HELPER FUNCTIONS =====

def stop_home_assistant():
    """Stop Home Assistant Core"""
    log("🛑 Stopping Home Assistant Core...")
    try:
        result = subprocess.run(['ha', 'core', 'stop'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log(f"⚠️  Warning: Could not stop HA Core: {result.stderr}")
            return False
        log("✅ Home Assistant Core stopped")
        time.sleep(5)
        return True
    except Exception as e:
        log(f"⚠️  Warning: Could not stop HA Core: {e}")
        return False


def start_home_assistant():
    """Start Home Assistant Core"""
    log("🚀 Starting Home Assistant Core...")
    try:
        result = subprocess.run(['ha', 'core', 'start'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log(f"❌ ERROR: Could not start HA Core: {result.stderr}")
            return False
        log("✅ Home Assistant Core started")
        log("⏳ Waiting for Home Assistant to initialize (30 seconds)...")
        time.sleep(30)
        return True
    except Exception as e:
        log(f"❌ ERROR: Could not start HA Core: {e}")
        return False


def load_entity_registry():
    """Load Home Assistant entity registry"""
    if not ENTITY_REGISTRY_FILE.exists():
        log(f"❌ ERROR: Entity registry not found: {ENTITY_REGISTRY_FILE}")
        sys.exit(1)

    with open(ENTITY_REGISTRY_FILE, 'r') as f:
        return json.load(f)


def save_entity_registry(registry, backup_path=None):
    """Save updated entity registry and optionally create backup"""
    if backup_path:
        log(f"\n💾 Saving registry backup: {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(registry, f, indent=2)
        log(f"✅ Backup saved")

    with open(ENTITY_REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)


def get_enhanced_sunpower_config_entry_id(registry):
    """Find Enhanced SunPower's config_entry_id"""
    for entity in registry['data']['entities']:
        if (entity.get('platform') == 'sunpower' and
            entity.get('config_entry_id') is not None):
            return entity['config_entry_id']
    return None


def find_sunstrong_entities(registry):
    """Find all SunStrong entities (platform: sunstrong_pvs OR orphaned sunpower)"""
    sunstrong_entities = []
    for entity in registry['data']['entities']:
        # Find entities that are either:
        # 1. SunStrong platform
        # 2. sunpower platform with null config_entry_id (orphaned from previous migration)
        if (entity.get('platform') == 'sunstrong_pvs' or
            (entity.get('platform') == 'sunpower' and entity.get('config_entry_id') is None)):
            sunstrong_entities.append(entity)
    return sunstrong_entities


def delete_duplicate_entities(registry, config_entry_id):
    """Remove entities created by Enhanced SunPower (the duplicates)"""
    log(f"\n{'='*70}")
    log(f"DELETION PHASE")
    log(f"{'='*70}")
    log(f"Target config_entry_id: {config_entry_id}")

    original_count = len(registry['data']['entities'])
    log(f"Registry entity count BEFORE deletion: {original_count}")

    # Find entities that match deletion criteria
    entities_to_delete = [
        e for e in registry['data']['entities']
        if (e.get('platform') == 'sunpower' and
            e.get('config_entry_id') == config_entry_id)
    ]

    log(f"\nFound {len(entities_to_delete)} entities matching deletion criteria:")
    log(f"(platform='sunpower' AND config_entry_id='{config_entry_id}')\n")

    # Log each entity being deleted (first 10 for brevity in stdout, all in log)
    for i, entity in enumerate(entities_to_delete):
        also_print = i < 10  # Only print first 10 to stdout
        log(f"\n[DELETE #{i+1}] {entity.get('entity_id')}", also_print=also_print)
        log_entity_details(entity, prefix="  ")

    if len(entities_to_delete) > 10:
        log(f"\n... ({len(entities_to_delete) - 10} more entities logged to file only)")

    # Filter out duplicates
    log(f"\nApplying deletion filter...")
    registry['data']['entities'] = [
        e for e in registry['data']['entities']
        if not (e.get('platform') == 'sunpower' and
                e.get('config_entry_id') == config_entry_id)
    ]

    new_count = len(registry['data']['entities'])
    deleted_count = original_count - new_count

    log(f"\nRegistry entity count AFTER deletion: {new_count}")
    log(f"Deleted: {deleted_count} entities")

    if deleted_count != len(entities_to_delete):
        log(f"⚠️  WARNING: Mismatch! Expected to delete {len(entities_to_delete)} but deleted {deleted_count}")

    log(f"{'='*70}\n")

    return deleted_count


def convert_inverter_entity(entity):
    """Convert inverter entity IDs"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.mi_'):
        return None, None, None

    # Extract serial and field
    # Format: sensor.mi_E00122142080335_current_power_production
    parts = entity_id.replace('sensor.mi_', '').split('_', 1)
    if len(parts) != 2:
        return None, None, None

    serial, old_field = parts
    new_field = INVERTER_FIELD_MAP.get(old_field, old_field)

    new_entity_id = f"sensor.sunpower_inverter_{serial.lower()}_{new_field}"
    new_unique_id = f"{serial.upper()}_inverter_{new_field}"

    return entity_id, new_entity_id, new_unique_id


def convert_gateway_entity(entity, pvs_serial, pvs_model="pvs6"):
    """Convert gateway entity IDs"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.pvs_gateway_'):
        return None, None, None

    # Extract field
    field_key = entity_id.replace('sensor.pvs_gateway_', '')
    new_field = GATEWAY_FIELD_MAP.get(field_key, field_key)

    new_entity_id = f"sensor.pv_supervisor_{pvs_model.lower()}_{pvs_serial.lower()}_{new_field}"

    # Extract serial from unique_id if available
    parts = unique_id.split('_', 1)
    if len(parts) == 2:
        serial, old_field = parts
        new_unique_id = f"{serial}_pvs_{new_field}"
    else:
        new_unique_id = f"{pvs_serial}_pvs_{new_field}"

    return entity_id, new_entity_id, new_unique_id


def convert_meter_entity(entity):
    """Convert meter entity IDs"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.meter_'):
        return None, None, None

    # Extract serial and field
    # Format: sensor.meter_PVS6M22283193p_lte_3ph_kwh
    parts = entity_id.replace('sensor.meter_', '').split('_', 1)
    if len(parts) != 2:
        return None, None, None

    serial, old_field = parts
    new_field = METER_FIELD_MAP.get(old_field, old_field)

    new_entity_id = f"sensor.sunpower_power_meter_{serial.lower()}_{new_field}"
    new_unique_id = f"{serial.upper()}_meter_{new_field}"

    return entity_id, new_entity_id, new_unique_id


def convert_ess_entity(entity):
    """Convert ESS entity IDs"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.ess_'):
        return None, None, None

    # Extract serial and field
    # Format: sensor.ess_00001D5A134A_soc_val
    parts = entity_id.replace('sensor.ess_', '').split('_', 1)
    if len(parts) != 2:
        return None, None, None

    serial, field_key = parts

    # ESS fields mostly match, no mapping needed
    new_entity_id = f"sensor.sunpower_ess_{serial.lower()}_{field_key}"
    new_unique_id = f"{serial.upper()}_ess_{field_key}"

    return entity_id, new_entity_id, new_unique_id


def convert_transfer_switch_entity(entity):
    """Convert transfer switch entity IDs"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.transfer_switch_'):
        return None, None, None

    # Extract serial and field
    parts = entity_id.replace('sensor.transfer_switch_', '').split('_', 1)
    if len(parts) != 2:
        return None, None, None

    serial, field_key = parts

    new_entity_id = f"sensor.sunpower_transfer_switch_{serial.lower()}_{field_key}"
    new_unique_id = f"{serial.upper()}_transfer_switch_{field_key}"

    return entity_id, new_entity_id, new_unique_id


def update_recorder_database(entity_id_changes):
    """Update entity_id in recorder database for history preservation"""
    if not RECORDER_DB_FILE.exists():
        log(f"⚠️  Warning: Recorder database not found: {RECORDER_DB_FILE}")
        log("   Skipping database update (history may not be preserved)")
        return 0

    log(f"\n💾 Updating recorder database...")
    log(f"   Database: {RECORDER_DB_FILE}")

    try:
        conn = sqlite3.connect(str(RECORDER_DB_FILE))
        cursor = conn.cursor()

        total_rows = 0

        for old_entity_id, new_entity_id in entity_id_changes:
            # Update statistics metadata (uses statistic_id column, not entity_id)
            cursor.execute(
                "UPDATE statistics_meta SET statistic_id = ? WHERE statistic_id = ?",
                (new_entity_id, old_entity_id)
            )
            stats_rows = cursor.rowcount

            # Update states metadata
            cursor.execute(
                "UPDATE states_meta SET entity_id = ? WHERE entity_id = ?",
                (new_entity_id, old_entity_id)
            )
            states_rows = cursor.rowcount

            total_rows += stats_rows + states_rows

            if stats_rows > 0 or states_rows > 0:
                log(f"   ✅ {old_entity_id}")
                log(f"      → {new_entity_id} ({stats_rows} stats, {states_rows} states)")

        conn.commit()
        conn.close()

        log(f"✅ Updated {total_rows} database rows")
        return total_rows

    except Exception as e:
        log(f"❌ ERROR updating database: {e}")
        return 0


# ===== MAIN SCRIPT =====

def main():
    log("=" * 70)
    log("SunStrong → Enhanced SunPower Migration Fix-Up (Post-Configuration)")
    log("=" * 70)
    log(f"Log file: {LOG_FILE}")
    log(f"Timestamp: {TIMESTAMP}")
    log("")

    # Verify HA config directory
    if not CONFIG_DIR.exists():
        log(f"❌ ERROR: Config directory not found: {CONFIG_DIR}")
        sys.exit(1)

    log(f"📁 Config directory: {CONFIG_DIR}")
    log(f"📄 Entity registry: {ENTITY_REGISTRY_FILE}")
    log(f"💾 Recorder database: {RECORDER_DB_FILE}")
    log(f"📝 Before backup: {REGISTRY_BACKUP_BEFORE}")
    log(f"📝 After backup: {REGISTRY_BACKUP_AFTER}")
    log("")

    # Warn about backup
    log("⚠️  IMPORTANT: Create a Home Assistant backup before proceeding!")
    log("   Settings → System → Backups → Create Backup")
    log("")
    response = input("Have you created a backup? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        log("❌ Migration cancelled. Please create a backup first.")
        sys.exit(0)
    log("")

    # Get PVS info for gateway entities
    log("Please provide PVS information (for gateway entities):")
    pvs_serial = input("  PVS Serial Number: ").strip().upper()
    pvs_model = input("  PVS Model (pvs5/pvs6, default=pvs6): ").strip().lower() or "pvs6"
    log(f"  PVS Serial: {pvs_serial}")
    log(f"  PVS Model: {pvs_model}")
    log("")

    # Stop Home Assistant
    if not stop_home_assistant():
        log("")
        log("⚠️  WARNING: Could not stop Home Assistant Core")
        log("   Migration will continue, but there's a risk of file conflicts.")
        log("")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            log("❌ Migration cancelled.")
            sys.exit(0)
    log("")

    # Load entity registry
    log("📖 Loading entity registry...")
    registry = load_entity_registry()
    log(f"✅ Loaded {len(registry['data']['entities'])} total entities")
    log("")

    # Save "BEFORE" backup and snapshot
    save_entity_registry(registry, backup_path=REGISTRY_BACKUP_BEFORE)
    log_registry_snapshot(registry, "BEFORE MIGRATION")

    # Find Enhanced SunPower's config_entry_id
    log("🔍 Finding Enhanced SunPower config_entry_id...")
    enhanced_config_entry_id = get_enhanced_sunpower_config_entry_id(registry)

    if not enhanced_config_entry_id:
        log("❌ ERROR: Enhanced SunPower integration not found!")
        log("   Please configure Enhanced SunPower integration first, then re-run this script.")
        start_home_assistant()
        sys.exit(1)

    log(f"✅ Found Enhanced SunPower: {enhanced_config_entry_id}")
    log("")

    # Delete duplicate entities
    duplicate_count = delete_duplicate_entities(registry, enhanced_config_entry_id)

    # Log snapshot after deletion
    log_registry_snapshot(registry, "AFTER DELETION")

    # Find SunStrong entities
    log("🔍 Finding SunStrong/orphaned entities...")
    sunstrong_entities = find_sunstrong_entities(registry)

    if not sunstrong_entities:
        log("✅ No SunStrong entities found - nothing to migrate!")
        save_entity_registry(registry, backup_path=REGISTRY_BACKUP_AFTER)
        start_home_assistant()
        sys.exit(0)

    log(f"📊 Found {len(sunstrong_entities)} SunStrong entities to migrate")
    log("")

    # Migrate entities
    log("🔄 Migrating entities...")
    entity_id_changes = []
    migrated_count = 0
    error_count = 0

    for entity in sunstrong_entities:
        try:
            old_entity_id = entity['entity_id']

            # Determine entity type and convert
            if old_entity_id.startswith('sensor.mi_'):
                old_id, new_id, new_uid = convert_inverter_entity(entity)
                device_type = "Inverter"
            elif old_entity_id.startswith('sensor.pvs_gateway_'):
                old_id, new_id, new_uid = convert_gateway_entity(entity, pvs_serial, pvs_model)
                device_type = "Gateway"
            elif old_entity_id.startswith('sensor.meter_'):
                old_id, new_id, new_uid = convert_meter_entity(entity)
                device_type = "Power Meter"
            elif old_entity_id.startswith('sensor.ess_'):
                old_id, new_id, new_uid = convert_ess_entity(entity)
                device_type = "ESS"
            elif old_entity_id.startswith('sensor.transfer_switch_'):
                old_id, new_id, new_uid = convert_transfer_switch_entity(entity)
                device_type = "Transfer Switch"
            else:
                continue  # Unknown type, skip

            if not new_id or not new_uid:
                continue

            # Update entity
            entity['entity_id'] = new_id
            entity['unique_id'] = new_uid
            entity['platform'] = 'sunpower'
            entity['config_entry_id'] = enhanced_config_entry_id  # Link to Enhanced!
            entity['disabled_by'] = None  # Re-enable migrated entity (was disabled by SunStrong)

            # Track for database update
            entity_id_changes.append((old_id, new_id))

            migrated_count += 1
            log(f"✅ {device_type:15} {old_id}")
            log(f"   {'':15} → {new_id}")

        except Exception as e:
            error_count += 1
            log(f"❌ {old_entity_id}")
            log(f"   {'':15} ERROR: {e}")

    log("")
    log(f"✅ Migrated {migrated_count} entities")
    if error_count > 0:
        log(f"❌ Errors: {error_count} entities")
    log("")

    # Log snapshot after migration
    log_registry_snapshot(registry, "AFTER MIGRATION")

    # Update recorder database
    if entity_id_changes:
        update_recorder_database(entity_id_changes)
        log("")

    # Save entity registry and "AFTER" backup
    log("💾 Saving entity registry...")
    save_entity_registry(registry, backup_path=REGISTRY_BACKUP_AFTER)
    log("✅ Entity registry saved")
    log("")

    # Restart Home Assistant
    if not start_home_assistant():
        log("")
        log("⚠️  WARNING: Could not start Home Assistant Core")
        log("   Please manually start HA Core: ha core start")
        log("")

    # Summary
    log("=" * 70)
    log("MIGRATION COMPLETE!")
    log("=" * 70)
    log(f"✅ Deleted duplicates: {duplicate_count} entities")
    log(f"✅ Migrated:           {migrated_count} entities")
    if error_count > 0:
        log(f"❌ Errors:             {error_count} entities")
    log("")
    log(f"📝 Log file: {LOG_FILE}")
    log(f"📝 Before backup: {REGISTRY_BACKUP_BEFORE}")
    log(f"📝 After backup: {REGISTRY_BACKUP_AFTER}")
    log("")

    # Next steps
    log("📝 NEXT STEPS:")
    log("   1. Wait ~1 minute for Home Assistant to fully initialize")
    log("   2. Verify entities are working (Developer Tools → States)")
    log("   3. Check history preserved (click entity → History tab)")
    log("   4. Verify Energy Dashboard shows continuous data")
    log("   5. Delete SunStrong integration (Settings → Devices → SunStrong → Delete)")
    log("")
    log("✨ Your entity history should be preserved with consistent naming!")
    log("")


if __name__ == "__main__":
    main()
