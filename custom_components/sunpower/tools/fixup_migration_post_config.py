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
    print("🛑 Stopping Home Assistant Core...")
    try:
        result = subprocess.run(['ha', 'core', 'stop'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"⚠️  Warning: Could not stop HA Core: {result.stderr}")
            return False
        print("✅ Home Assistant Core stopped")
        time.sleep(5)
        return True
    except Exception as e:
        print(f"⚠️  Warning: Could not stop HA Core: {e}")
        return False


def start_home_assistant():
    """Start Home Assistant Core"""
    print("🚀 Starting Home Assistant Core...")
    try:
        result = subprocess.run(['ha', 'core', 'start'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"❌ ERROR: Could not start HA Core: {result.stderr}")
            return False
        print("✅ Home Assistant Core started")
        print("⏳ Waiting for Home Assistant to initialize (30 seconds)...")
        time.sleep(30)
        return True
    except Exception as e:
        print(f"❌ ERROR: Could not start HA Core: {e}")
        return False


def load_entity_registry():
    """Load Home Assistant entity registry"""
    if not ENTITY_REGISTRY_FILE.exists():
        print(f"❌ ERROR: Entity registry not found: {ENTITY_REGISTRY_FILE}")
        sys.exit(1)

    with open(ENTITY_REGISTRY_FILE, 'r') as f:
        return json.load(f)


def save_entity_registry(registry):
    """Save updated entity registry"""
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
    print(f"\n🗑️  Deleting duplicate entities (config_entry_id: {config_entry_id})...")

    original_count = len(registry['data']['entities'])

    # Keep track of what we're deleting
    deleted_entities = []

    # Filter out duplicates
    registry['data']['entities'] = [
        e for e in registry['data']['entities']
        if not (e.get('platform') == 'sunpower' and
                e.get('config_entry_id') == config_entry_id)
    ]

    deleted_count = original_count - len(registry['data']['entities'])
    print(f"✅ Deleted {deleted_count} duplicate entities")
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
        print(f"⚠️  Warning: Recorder database not found: {RECORDER_DB_FILE}")
        print("   Skipping database update (history may not be preserved)")
        return 0

    print(f"\n💾 Updating recorder database...")
    print(f"   Database: {RECORDER_DB_FILE}")

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
                print(f"   ✅ {old_entity_id}")
                print(f"      → {new_entity_id} ({stats_rows} stats, {states_rows} states)")

        conn.commit()
        conn.close()

        print(f"✅ Updated {total_rows} database rows")
        return total_rows

    except Exception as e:
        print(f"❌ ERROR updating database: {e}")
        return 0


# ===== MAIN SCRIPT =====

def main():
    print("=" * 70)
    print("SunStrong → Enhanced SunPower Migration Fix-Up (Post-Configuration)")
    print("=" * 70)
    print()

    # Verify HA config directory
    if not CONFIG_DIR.exists():
        print(f"❌ ERROR: Config directory not found: {CONFIG_DIR}")
        sys.exit(1)

    print(f"📁 Config directory: {CONFIG_DIR}")
    print(f"📄 Entity registry: {ENTITY_REGISTRY_FILE}")
    print(f"💾 Recorder database: {RECORDER_DB_FILE}")
    print()

    # Warn about backup
    print("⚠️  IMPORTANT: Create a Home Assistant backup before proceeding!")
    print("   Settings → System → Backups → Create Backup")
    print()
    response = input("Have you created a backup? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Migration cancelled. Please create a backup first.")
        sys.exit(0)
    print()

    # Get PVS info for gateway entities
    print("Please provide PVS information (for gateway entities):")
    pvs_serial = input("  PVS Serial Number: ").strip().upper()
    pvs_model = input("  PVS Model (pvs5/pvs6, default=pvs6): ").strip().lower() or "pvs6"
    print()

    # Stop Home Assistant
    if not stop_home_assistant():
        print()
        print("⚠️  WARNING: Could not stop Home Assistant Core")
        print("   Migration will continue, but there's a risk of file conflicts.")
        print()
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Migration cancelled.")
            sys.exit(0)
    print()

    # Load entity registry
    print("📖 Loading entity registry...")
    registry = load_entity_registry()
    print(f"✅ Loaded {len(registry['data']['entities'])} total entities")
    print()

    # Find Enhanced SunPower's config_entry_id
    print("🔍 Finding Enhanced SunPower config_entry_id...")
    enhanced_config_entry_id = get_enhanced_sunpower_config_entry_id(registry)

    if not enhanced_config_entry_id:
        print("❌ ERROR: Enhanced SunPower integration not found!")
        print("   Please configure Enhanced SunPower integration first, then re-run this script.")
        start_home_assistant()
        sys.exit(1)

    print(f"✅ Found Enhanced SunPower: {enhanced_config_entry_id}")
    print()

    # Delete duplicate entities
    duplicate_count = delete_duplicate_entities(registry, enhanced_config_entry_id)
    print()

    # Find SunStrong entities
    print("🔍 Finding SunStrong/orphaned entities...")
    sunstrong_entities = find_sunstrong_entities(registry)

    if not sunstrong_entities:
        print("✅ No SunStrong entities found - nothing to migrate!")
        save_entity_registry(registry)
        start_home_assistant()
        sys.exit(0)

    print(f"📊 Found {len(sunstrong_entities)} SunStrong entities to migrate")
    print()

    # Migrate entities
    print("🔄 Migrating entities...")
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

            # Track for database update
            entity_id_changes.append((old_id, new_id))

            migrated_count += 1
            print(f"✅ {device_type:15} {old_id}")
            print(f"   {'':15} → {new_id}")

        except Exception as e:
            error_count += 1
            print(f"❌ {old_entity_id}")
            print(f"   {'':15} ERROR: {e}")

    print()
    print(f"✅ Migrated {migrated_count} entities")
    if error_count > 0:
        print(f"❌ Errors: {error_count} entities")
    print()

    # Update recorder database
    if entity_id_changes:
        update_recorder_database(entity_id_changes)
        print()

    # Save entity registry
    print("💾 Saving entity registry...")
    save_entity_registry(registry)
    print("✅ Entity registry saved")
    print()

    # Restart Home Assistant
    if not start_home_assistant():
        print()
        print("⚠️  WARNING: Could not start Home Assistant Core")
        print("   Please manually start HA Core: ha core start")
        print()

    # Summary
    print("=" * 70)
    print("MIGRATION COMPLETE!")
    print("=" * 70)
    print(f"✅ Deleted duplicates: {duplicate_count} entities")
    print(f"✅ Migrated:           {migrated_count} entities")
    if error_count > 0:
        print(f"❌ Errors:             {error_count} entities")
    print()

    # Next steps
    print("📝 NEXT STEPS:")
    print("   1. Wait ~1 minute for Home Assistant to fully initialize")
    print("   2. Verify entities are working (Developer Tools → States)")
    print("   3. Check history preserved (click entity → History tab)")
    print("   4. Verify Energy Dashboard shows continuous data")
    print("   5. Delete SunStrong integration (Settings → Devices → SunStrong → Delete)")
    print()
    print("✨ Your entity history should be preserved with consistent naming!")
    print()


if __name__ == "__main__":
    main()
