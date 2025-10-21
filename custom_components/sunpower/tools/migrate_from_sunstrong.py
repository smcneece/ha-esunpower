#!/usr/bin/env python3
"""
SunStrong → Enhanced SunPower Migration Tool

USAGE (Home Assistant Terminal):
1. Create backup: Settings → System → Backups → Create Backup
2. Install Enhanced SunPower integration (but don't configure yet)
3. Restart Home Assistant
4. Disable SunStrong integration (Settings → Devices → SunStrong → Disable)
5. Run: python3 /config/custom_components/sunpower/tools/migrate_from_sunstrong.py
6. Script will automatically stop HA, migrate entities, and restart HA
7. Configure Enhanced SunPower integration
8. Delete SunStrong integration

This script converts SunStrong entity_ids and unique_ids to Enhanced SunPower format
while preserving all historical data in the recorder database.

NOTE: This script will automatically stop and restart Home Assistant Core to prevent
registry file conflicts. Your SSH terminal session will remain active.
"""

import json
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

# ===== CONFIGURATION =====
# Path to HA config directory (auto-detect or override)
if len(sys.argv) > 1:
    CONFIG_DIR = Path(sys.argv[1])
else:
    CONFIG_DIR = Path("/config")

ENTITY_REGISTRY_FILE = CONFIG_DIR / ".storage" / "core.entity_registry"

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

# ESS fields mostly match - no mapping needed


# ===== HELPER FUNCTIONS =====

def stop_home_assistant():
    """Stop Home Assistant Core to prevent registry file conflicts"""
    print("🛑 Stopping Home Assistant Core...")
    try:
        result = subprocess.run(['ha', 'core', 'stop'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"⚠️  Warning: Could not stop HA Core: {result.stderr}")
            return False
        print("✅ Home Assistant Core stopped")
        # Wait for shutdown to complete
        time.sleep(5)
        return True
    except Exception as e:
        print(f"⚠️  Warning: Could not stop HA Core: {e}")
        return False


def start_home_assistant():
    """Start Home Assistant Core after migration"""
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


def find_sunstrong_entities(registry):
    """Find all SunStrong entities"""
    sunstrong_entities = []
    for entity in registry['data']['entities']:
        if entity.get('platform') == 'sunstrong_pvs':
            sunstrong_entities.append(entity)
    return sunstrong_entities


def convert_inverter_entity(entity):
    """Convert inverter entity to Enhanced SunPower format"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.mi_'):
        return None, None

    # Extract serial from unique_id (format: SERIAL_field_key)
    parts = unique_id.split('_', 1)
    if len(parts) != 2:
        return None, None
    serial, old_field = parts

    # Map field name
    new_field = INVERTER_FIELD_MAP.get(old_field, old_field)

    # Build new IDs
    new_entity_id = f"sensor.sunpower_inverter_{serial.lower()}_{new_field}"
    new_unique_id = f"{serial}_inverter_{new_field}"

    return new_entity_id, new_unique_id


def convert_meter_entity(entity):
    """Convert meter entity to Enhanced SunPower format"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.meter_'):
        return None, None

    # Extract serial from unique_id
    parts = unique_id.split('_', 1)
    if len(parts) != 2:
        return None, None
    serial, old_field = parts

    # Map field name
    new_field = METER_FIELD_MAP.get(old_field, old_field)

    # Build new IDs
    new_entity_id = f"sensor.sunpower_power_meter_{serial.lower()}_{new_field}"
    new_unique_id = f"{serial}_meter_{new_field}"

    return new_entity_id, new_unique_id


def convert_gateway_entity(entity, pvs_serial="UNKNOWN", pvs_model="pvs6"):
    """Convert gateway entity to Enhanced SunPower format"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.pvs_gateway_'):
        return None, None

    # Extract field key
    field_key = entity_id.replace('sensor.pvs_gateway_', '')

    # Map field name
    new_field = GATEWAY_FIELD_MAP.get(field_key, field_key)

    # Build new IDs
    new_entity_id = f"sensor.pv_supervisor_{pvs_model.lower()}_{pvs_serial.lower()}_{new_field}"

    # Extract original serial from unique_id if present
    parts = unique_id.split('_', 1)
    if len(parts) == 2:
        serial, old_field = parts
        new_unique_id = f"{serial}_pvs_{new_field}"
    else:
        new_unique_id = f"{pvs_serial}_pvs_{new_field}"

    return new_entity_id, new_unique_id


def convert_ess_entity(entity):
    """Convert ESS entity to Enhanced SunPower format"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.ess_'):
        return None, None

    # Extract serial from unique_id
    parts = unique_id.split('_', 1)
    if len(parts) != 2:
        return None, None
    serial, field_key = parts

    # Build new IDs (ESS fields mostly identical)
    new_entity_id = f"sensor.sunpower_ess_{serial.lower()}_{field_key}"
    new_unique_id = f"{serial}_ess_{field_key}"

    return new_entity_id, new_unique_id


def convert_transfer_switch_entity(entity):
    """Convert transfer switch entity to Enhanced SunPower format"""
    entity_id = entity['entity_id']
    unique_id = entity['unique_id']

    if not entity_id.startswith('sensor.transfer_switch_'):
        return None, None

    # Extract serial from unique_id
    parts = unique_id.split('_', 1)
    if len(parts) != 2:
        return None, None
    serial, field_key = parts

    # Build new IDs
    new_entity_id = f"sensor.sunpower_transfer_switch_{serial.lower()}_{field_key}"
    new_unique_id = f"{serial}_transfer_switch_{field_key}"

    return new_entity_id, new_unique_id


def migrate_entity(entity, pvs_serial="UNKNOWN", pvs_model="pvs6"):
    """Determine entity type and migrate"""
    entity_id = entity['entity_id']

    # Determine type and convert
    if entity_id.startswith('sensor.mi_'):
        device_type = "Inverter"
        new_entity_id, new_unique_id = convert_inverter_entity(entity)
    elif entity_id.startswith('sensor.meter_'):
        device_type = "Power Meter"
        new_entity_id, new_unique_id = convert_meter_entity(entity)
    elif entity_id.startswith('sensor.pvs_gateway_'):
        device_type = "Gateway"
        new_entity_id, new_unique_id = convert_gateway_entity(entity, pvs_serial, pvs_model)
    elif entity_id.startswith('sensor.ess_'):
        device_type = "ESS"
        new_entity_id, new_unique_id = convert_ess_entity(entity)
    elif entity_id.startswith('sensor.transfer_switch_'):
        device_type = "Transfer Switch"
        new_entity_id, new_unique_id = convert_transfer_switch_entity(entity)
    else:
        return None  # Unknown type, skip

    if not new_entity_id or not new_unique_id:
        return None

    return {
        'old_entity_id': entity_id,
        'new_entity_id': new_entity_id,
        'old_unique_id': entity.get('unique_id'),
        'new_unique_id': new_unique_id,
        'device_type': device_type,
        'entity': entity
    }


# ===== MAIN MIGRATION =====

def main():
    print("=" * 70)
    print("SunStrong → Enhanced SunPower Migration Tool")
    print("=" * 70)
    print()

    # Check if HA config directory exists
    if not CONFIG_DIR.exists():
        print(f"❌ ERROR: Config directory not found: {CONFIG_DIR}")
        print()
        print("Usage: python3 migrate_from_sunstrong.py [/path/to/config]")
        sys.exit(1)

    print(f"📁 Config directory: {CONFIG_DIR}")
    print(f"📄 Entity registry: {ENTITY_REGISTRY_FILE}")
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

    # Load entity registry
    print("📖 Loading entity registry...")
    registry = load_entity_registry()
    print(f"✅ Loaded {len(registry['data']['entities'])} total entities")
    print()

    # Find SunStrong entities
    print("🔍 Searching for SunStrong entities...")
    sunstrong_entities = find_sunstrong_entities(registry)

    if not sunstrong_entities:
        print("✅ No SunStrong entities found - nothing to migrate!")
        sys.exit(0)

    print(f"📊 Found {len(sunstrong_entities)} SunStrong entities")
    print()

    # Get PVS info (needed for gateway entities)
    print("Please provide PVS information (for gateway entities):")
    pvs_serial = input("  PVS Serial Number (press Enter to skip): ").strip().upper()
    pvs_model = input("  PVS Model (pvs5/pvs6, default=pvs6): ").strip().lower() or "pvs6"
    print()

    # Plan migration
    print("🗺️  Planning migration...")
    migrations = []
    skipped = []

    for entity in sunstrong_entities:
        result = migrate_entity(entity, pvs_serial, pvs_model)
        if result:
            migrations.append(result)
        else:
            skipped.append(entity['entity_id'])

    print(f"✅ {len(migrations)} entities will be migrated")
    if skipped:
        print(f"⚠️  {len(skipped)} entities will be skipped (unknown type)")
    print()

    # Show sample migrations
    print("📋 Sample migrations:")
    for migration in migrations[:5]:
        print(f"   {migration['device_type']:15} {migration['old_entity_id']}")
        print(f"   {'':15} → {migration['new_entity_id']}")
    if len(migrations) > 5:
        print(f"   ... and {len(migrations) - 5} more")
    print()

    # Confirm migration
    response = input(f"Migrate {len(migrations)} entities? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Migration cancelled.")
        sys.exit(0)
    print()

    # Stop Home Assistant to prevent registry file conflicts
    if not stop_home_assistant():
        print()
        print("⚠️  WARNING: Could not stop Home Assistant Core")
        print("   Migration will continue, but there's a risk of file conflicts.")
        print("   Recommend manually stopping HA Core and re-running this script.")
        print()
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Migration cancelled.")
            sys.exit(0)
    print()

    # Perform migration
    print("🔄 Migrating entities...")
    migrated_count = 0
    error_count = 0

    for migration in migrations:
        try:
            entity = migration['entity']
            entity['entity_id'] = migration['new_entity_id']
            entity['unique_id'] = migration['new_unique_id']
            entity['platform'] = 'sunpower'
            # COMPLETELY REMOVE config_entry_id so Enhanced SunPower can adopt these entities
            # Using pop() to delete the key entirely (not just set to None)
            entity.pop('config_entry_id', None)

            migrated_count += 1
            print(f"✅ {migration['device_type']:15} {migration['old_entity_id']}")
            print(f"   {'':15} → {migration['new_entity_id']}")
        except Exception as e:
            error_count += 1
            print(f"❌ {migration['device_type']:15} {migration['old_entity_id']}")
            print(f"   {'':15} ERROR: {e}")

    print()

    # Save updated registry
    print("💾 Saving updated entity registry...")
    save_entity_registry(registry)
    print("✅ Entity registry saved")
    print()

    # Restart Home Assistant
    if not start_home_assistant():
        print()
        print("⚠️  WARNING: Could not start Home Assistant Core")
        print("   Please manually start HA Core: ha core start")
        print()
    print()

    # Summary
    print("=" * 70)
    print("MIGRATION COMPLETE!")
    print("=" * 70)
    print(f"✅ Migrated:  {migrated_count} entities")
    if skipped:
        print(f"⚠️  Skipped:   {len(skipped)} entities")
    if error_count:
        print(f"❌ Errors:    {error_count} entities")
    print()

    # Next steps
    print("📝 NEXT STEPS:")
    print("   1. Configure Enhanced SunPower integration:")
    print("      Settings → Devices & Services → Add Integration → Enhanced SunPower")
    print("   2. Enter your PVS IP address and settings")
    print("   3. Verify entities are working (check Developer Tools → States)")
    print("   4. Check that history is preserved (click entity → History tab)")
    print("   5. Delete SunStrong integration (Settings → Devices → SunStrong → Delete)")
    print()
    print("✨ Your entity history has been preserved - automations should work!")
    print("⏰ Home Assistant is now running - wait ~1 minute before configuring.")


if __name__ == "__main__":
    main()
