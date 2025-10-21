#!/usr/bin/env python3
"""
SunStrong → Enhanced SunPower History Transfer Script (Post-Installation)

This script transfers history from SunStrong entities to Enhanced SunPower entities
AFTER Enhanced has been installed. It intelligently maps entities by device serial
and sensor type, then updates the recorder database to reconnect history.

USAGE:
1. Disable SunStrong integration (Settings → Devices → SunStrong → Disable)
2. Install and configure Enhanced SunPower integration
3. Wait for Enhanced to create all entities (check entity count)
4. Run this script: python3 SunStrong_HistoryTransfer.py
5. Script will:
   - Map SunStrong entities to Enhanced entities by serial + sensor type
   - Update recorder database (preserve history)
   - Clean up orphaned SunStrong entities
   - Restart HA Core
6. Verify history shows in Enhanced entities

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
import re

# ===== CONFIGURATION =====
CONFIG_DIR = Path("/config")
ENTITY_REGISTRY_FILE = CONFIG_DIR / ".storage" / "core.entity_registry"
RECORDER_DB_FILE = CONFIG_DIR / "home-assistant_v2.db"

# Create timestamped log file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = CONFIG_DIR / f"sunstrong_history_transfer_{TIMESTAMP}.log"
REGISTRY_BACKUP_BEFORE = CONFIG_DIR / f"entity_registry_before_history_transfer_{TIMESTAMP}.json"
REGISTRY_BACKUP_AFTER = CONFIG_DIR / f"entity_registry_after_history_transfer_{TIMESTAMP}.json"

# ===== LOGGING FUNCTIONS =====

def log(message, also_print=True):
    """Write to log file and optionally print to stdout"""
    with open(LOG_FILE, 'a') as f:
        f.write(f"{message}\n")
    if also_print:
        print(message)

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

    # Count SunStrong entities
    sunstrong = [e for e in entities if e.get('platform') == 'sunstrong_pvs']
    if sunstrong:
        log(f"\nSunStrong entities: {len(sunstrong)}")
        disabled = [e for e in sunstrong if e.get('disabled_by') is not None]
        log(f"SunStrong disabled entities: {len(disabled)}")

    # Count Enhanced entities
    enhanced = [e for e in entities if e.get('platform') == 'sunpower']
    if enhanced:
        log(f"\nEnhanced SunPower entities: {len(enhanced)}")
        orphaned = [e for e in enhanced if e.get('config_entry_id') is None]
        log(f"Enhanced orphaned entities: {len(orphaned)}")

    log(f"{'='*70}\n")

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


def extract_serial(entity_id):
    """Extract device serial from entity_id"""
    # SunStrong patterns:
    # sensor.mi_E00122137044207_field
    # sensor.meter_PVS6M22283193p_field
    # sensor.ess_00001D5A134A_field
    # sensor.pvs_gateway_field (no serial in entity_id)

    # Enhanced patterns:
    # sensor.inverter_e00122137044207_field
    # sensor.power_meter_pvs6m22283193p_field
    # sensor.sunpower_ess_00001d5a134a_field
    # sensor.pv_supervisor_pvs6_zt222885000549w3193_field

    entity_id_lower = entity_id.lower()

    # Try to extract serial number patterns
    # Pattern 1: E followed by numbers (inverter)
    match = re.search(r'[_/](e\d+)[_/]', entity_id_lower)
    if match:
        return match.group(1).upper()

    # Pattern 2: PVS6M + numbers + p/c (meter)
    match = re.search(r'[_/](pvs6m\d+[pc])[_/]', entity_id_lower)
    if match:
        return match.group(1).upper()

    # Pattern 3: Hex pattern (ESS/battery)
    match = re.search(r'[_/]([0-9a-f]{12})[_/]', entity_id_lower)
    if match:
        return match.group(1).upper()

    # Pattern 4: ZT + numbers + W + numbers (PVS serial)
    match = re.search(r'[_/](zt\d+w\d+)[_/]', entity_id_lower)
    if match:
        return match.group(1).upper()

    return None


def categorize_sensor(entity_id):
    """Categorize sensor by what it measures"""
    entity_lower = entity_id.lower()

    # Power/Energy categories
    if 'lifetime' in entity_lower or 'ltea' in entity_lower or 'total_energy' in entity_lower:
        return 'lifetime_energy'
    if 'current_power' in entity_lower or 'p_3phsum' in entity_lower or '_power' in entity_lower:
        return 'current_power'
    if 'production_current' in entity_lower or 'i_3phsum' in entity_lower or '_amps' in entity_lower:
        return 'current'
    if 'production_voltage' in entity_lower or 'vln' in entity_lower or '_volts' in entity_lower:
        return 'voltage'
    if 'frequency' in entity_lower or 'freq' in entity_lower:
        return 'frequency'
    if 'temperature' in entity_lower or 't_htsnk' in entity_lower:
        return 'temperature'

    # PVS/Gateway categories
    if 'uptime' in entity_lower or 'dl_uptime' in entity_lower:
        return 'uptime'
    if 'ram' in entity_lower:
        return 'ram_usage'
    if 'flash' in entity_lower and 'wear' not in entity_lower:
        return 'flash_usage'
    if 'cpu' in entity_lower or 'dl_cpu' in entity_lower or 'system_load' in entity_lower:
        return 'cpu_load'
    if 'error' in entity_lower or 'err' in entity_lower:
        return 'error_count'
    if 'comm' in entity_lower:
        return 'comm_errors'
    if 'flash_wear' in entity_lower or 'flashwear' in entity_lower:
        return 'flash_wear'

    # Meter specific
    if 'net_lte' in entity_lower or 'net_ltea' in entity_lower:
        return 'net_lifetime_energy'
    if 'pos_lte' in entity_lower or 'pos_ltea' in entity_lower:
        return 'positive_lifetime_energy'
    if 'reactive_power' in entity_lower or 'q_3phsum' in entity_lower:
        return 'reactive_power'
    if 'apparent_power' in entity_lower or 's_3phsum' in entity_lower:
        return 'apparent_power'
    if 'power_factor' in entity_lower or 'pf_rto' in entity_lower:
        return 'power_factor'

    # ESS/Battery
    if 'soc' in entity_lower or 'state_of_charge' in entity_lower:
        return 'soc'
    if 'battery_power' in entity_lower:
        return 'battery_power'

    return 'unknown'


def map_entities(sunstrong_entities, enhanced_entities):
    """Map SunStrong entities to Enhanced entities by serial + category"""
    log("\n🔍 Mapping SunStrong entities to Enhanced entities...")

    mappings = []
    unmapped_sunstrong = []

    for ss_entity in sunstrong_entities:
        ss_entity_id = ss_entity.get('entity_id')
        ss_serial = extract_serial(ss_entity_id)
        ss_category = categorize_sensor(ss_entity_id)

        if not ss_serial:
            log(f"⚠️  Could not extract serial from: {ss_entity_id}")
            unmapped_sunstrong.append(ss_entity_id)
            continue

        # Find matching Enhanced entity
        found_match = False
        for enh_entity in enhanced_entities:
            enh_entity_id = enh_entity.get('entity_id')
            enh_serial = extract_serial(enh_entity_id)
            enh_category = categorize_sensor(enh_entity_id)

            if enh_serial == ss_serial and enh_category == ss_category:
                mappings.append({
                    'sunstrong_entity_id': ss_entity_id,
                    'enhanced_entity_id': enh_entity_id,
                    'serial': ss_serial,
                    'category': ss_category
                })
                log(f"✅ Mapped: {ss_entity_id}")
                log(f"        → {enh_entity_id}")
                log(f"          Serial: {ss_serial}, Category: {ss_category}")
                found_match = True
                break

        if not found_match:
            log(f"⚠️  No match found for: {ss_entity_id} (Serial: {ss_serial}, Category: {ss_category})")
            unmapped_sunstrong.append(ss_entity_id)

    log(f"\n📊 Mapping Summary:")
    log(f"   Mapped: {len(mappings)} entities")
    log(f"   Unmapped: {len(unmapped_sunstrong)} entities")

    if unmapped_sunstrong:
        log(f"\n⚠️  Unmapped SunStrong entities:")
        for entity_id in unmapped_sunstrong:
            log(f"   - {entity_id}")

    return mappings


def update_recorder_database(mappings):
    """Update entity_id in recorder database for history preservation"""
    if not RECORDER_DB_FILE.exists():
        log(f"⚠️  Warning: Recorder database not found: {RECORDER_DB_FILE}")
        log("   Skipping database update (history will not be preserved)")
        return 0

    log(f"\n💾 Updating recorder database...")
    log(f"   Database: {RECORDER_DB_FILE}")

    try:
        conn = sqlite3.connect(str(RECORDER_DB_FILE))
        cursor = conn.cursor()

        total_rows = 0
        successful_updates = 0
        failed_updates = []

        for mapping in mappings:
            old_entity_id = mapping['sunstrong_entity_id']
            new_entity_id = mapping['enhanced_entity_id']

            try:
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
                    successful_updates += 1
                else:
                    log(f"   ℹ️  {old_entity_id} (no history found)")

            except sqlite3.IntegrityError as e:
                log(f"   ❌ {old_entity_id}")
                log(f"      → ERROR: {e}")
                failed_updates.append((old_entity_id, str(e)))

        conn.commit()
        conn.close()

        log(f"\n✅ Database update complete:")
        log(f"   Total rows updated: {total_rows}")
        log(f"   Successful: {successful_updates}")
        log(f"   Failed: {len(failed_updates)}")

        if failed_updates:
            log(f"\n❌ Failed updates:")
            for entity_id, error in failed_updates:
                log(f"   - {entity_id}: {error}")

        return total_rows

    except Exception as e:
        log(f"❌ ERROR updating database: {e}")
        return 0


def cleanup_sunstrong_entities(registry):
    """Remove SunStrong entities from registry"""
    log(f"\n🗑️  Cleaning up SunStrong entities...")

    original_count = len(registry['data']['entities'])

    # Remove all sunstrong_pvs entities
    registry['data']['entities'] = [
        e for e in registry['data']['entities']
        if e.get('platform') != 'sunstrong_pvs'
    ]

    removed_count = original_count - len(registry['data']['entities'])
    log(f"✅ Removed {removed_count} SunStrong entities from registry")

    return removed_count


# ===== MAIN SCRIPT =====

def main():
    log("=" * 70)
    log("SunStrong → Enhanced SunPower History Transfer (Post-Installation)")
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
        log("❌ History transfer cancelled. Please create a backup first.")
        sys.exit(0)
    log("")

    # Stop Home Assistant
    if not stop_home_assistant():
        log("")
        log("⚠️  WARNING: Could not stop Home Assistant Core")
        log("   History transfer will continue, but there's a risk of file conflicts.")
        log("")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            log("❌ History transfer cancelled.")
            sys.exit(0)
    log("")

    # Load entity registry
    log("📖 Loading entity registry...")
    registry = load_entity_registry()
    log(f"✅ Loaded {len(registry['data']['entities'])} total entities")
    log("")

    # Save "BEFORE" backup and snapshot
    save_entity_registry(registry, backup_path=REGISTRY_BACKUP_BEFORE)
    log_registry_snapshot(registry, "BEFORE HISTORY TRANSFER")

    # Find SunStrong entities
    log("🔍 Finding SunStrong entities...")
    sunstrong_entities = [e for e in registry['data']['entities'] if e.get('platform') == 'sunstrong_pvs']

    if not sunstrong_entities:
        log("❌ ERROR: No SunStrong entities found!")
        log("   Please ensure SunStrong integration is disabled (not deleted).")
        start_home_assistant()
        sys.exit(1)

    log(f"📊 Found {len(sunstrong_entities)} SunStrong entities")
    log("")

    # Find Enhanced entities
    log("🔍 Finding Enhanced SunPower entities...")
    enhanced_entities = [e for e in registry['data']['entities']
                        if e.get('platform') == 'sunpower' and e.get('config_entry_id') is not None]

    if not enhanced_entities:
        log("❌ ERROR: No Enhanced SunPower entities found!")
        log("   Please install and configure Enhanced SunPower first.")
        start_home_assistant()
        sys.exit(1)

    log(f"📊 Found {len(enhanced_entities)} Enhanced SunPower entities")
    log("")

    # Map entities
    mappings = map_entities(sunstrong_entities, enhanced_entities)

    if not mappings:
        log("❌ ERROR: Could not map any entities!")
        log("   Please check the log for details.")
        start_home_assistant()
        sys.exit(1)

    log("")

    # Update recorder database
    rows_updated = update_recorder_database(mappings)
    log("")

    # Cleanup SunStrong entities
    removed_count = cleanup_sunstrong_entities(registry)
    log("")

    # Log snapshot after cleanup
    log_registry_snapshot(registry, "AFTER HISTORY TRANSFER")

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
    log("HISTORY TRANSFER COMPLETE!")
    log("=" * 70)
    log(f"✅ Mapped entities: {len(mappings)}")
    log(f"✅ Database rows updated: {rows_updated}")
    log(f"✅ Removed SunStrong entities: {removed_count}")
    log("")
    log(f"📝 Log file: {LOG_FILE}")
    log(f"📝 Before backup: {REGISTRY_BACKUP_BEFORE}")
    log(f"📝 After backup: {REGISTRY_BACKUP_AFTER}")
    log("")

    # Next steps
    log("📝 NEXT STEPS:")
    log("   1. Wait ~1 minute for Home Assistant to fully initialize")
    log("   2. Check Enhanced SunPower entities for history graphs")
    log("   3. Verify Energy Dashboard shows continuous data")
    log("   4. Delete SunStrong integration (Settings → Devices → SunStrong → Delete)")
    log("")
    log("✨ Your entity history should now be connected to Enhanced SunPower entities!")
    log("")


if __name__ == "__main__":
    main()
