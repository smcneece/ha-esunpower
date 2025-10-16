"""SunStrong → Enhanced SunPower Entity Migration

Converts orphaned SunStrong (pvs-hass) entities to Enhanced SunPower format.
Preserves history and automations by renaming entities while maintaining recorder links.

SAFETY: Requires SunStrong integration removal before migration to prevent entity duplication.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import ConfigEntryError

from .const import (
    SUNPOWER_SENSORS,
    SUNPOWER_BINARY_SENSORS,
    INVERTER_DEVICE_TYPE,
    METER_DEVICE_TYPE,
    PVS_DEVICE_TYPE,
    ESS_DEVICE_TYPE,
    TRANSFER_SWITCH_DEVICE_TYPE,
)

_LOGGER = logging.getLogger(__name__)


def is_field_supported(device_type: str, field_name: str) -> bool:
    """Check if a field is supported by Enhanced SunPower for given device type

    Args:
        device_type: Device type (Inverter, Power Meter, etc)
        field_name: Field name to check (e.g., p_3phsum_kw)

    Returns:
        True if field has a sensor definition, False otherwise
    """
    # Check regular sensors
    if device_type in SUNPOWER_SENSORS:
        for sensor_def in SUNPOWER_SENSORS[device_type].get("sensors", {}).values():
            if sensor_def.get("field") == field_name:
                return True

    # Check binary sensors
    if device_type in SUNPOWER_BINARY_SENSORS:
        for sensor_def in SUNPOWER_BINARY_SENSORS[device_type].get("sensors", {}).values():
            if sensor_def.get("field") == field_name:
                return True

    return False


# Field name mappings: SunStrong key → Enhanced SunPower key
INVERTER_FIELD_MAP = {
    "current_power_production": "p_3phsum_kw",
    "lifetime_production": "ltea_3phsum_kwh",
    "production_current": "i_3phsum_a",
    "production_voltage": "vln_3phavg_v",
    "frequency": "freq_hz",  # Same field name, but include for completeness
    "temperature": "t_htsnk_degc",
}

GATEWAY_FIELD_MAP = {
    "gateway_uptime": "dl_uptime",
    "ram_usage": "ram_usage_percent",  # Same field, but Enhanced adds _percent
    "flash_usage": "flash_usage_percent",  # Same field, but Enhanced adds _percent
    "cpu_usage": "dl_cpu_load",
}

METER_FIELD_MAP = {
    "lte_3ph_kwh": "net_ltea_3phsum_kwh",
    "pos_lte_kwh": "pos_ltea_3phsum_kwh",
    "q3phsum_kvar": "q_3phsum_kvar",
    "s3phsum_kva": "s_3phsum_kva",
    "tot_pf_ratio": "tot_pf_rto",
    # These are exact matches in both integrations:
    # p_3phsum_kw, freq_hz, i1_a, i2_a, neg_lte_kwh, net_lte_kwh,
    # p1_kw, p2_kw, v12_v, v1n_v, v2n_v
}

# ESS/Battery fields are mostly identical
ESS_FIELD_MAP = {
    # Most ESS fields match exactly: power_3ph_kw, op_mode, soc_val, soh_val,
    # t_invtr_degc, v_batt_v, chrg_limit_pmax_kw, dischrg_lim_pmax_kw,
    # max_t_batt_cell_degc, min_t_batt_cell_degc
}


def convert_inverter_entity_id(sunstrong_entity_id: str, serial: str) -> str | None:
    """Convert SunStrong inverter entity_id to Enhanced SunPower format

    SunStrong: sensor.mi_e00122142080335_current_power_production
    Enhanced:  sensor.sunpower_inverter_e00122142080335_p_3phsum_kw
    """
    if not sunstrong_entity_id.startswith("sensor.mi_"):
        return None

    # Extract field key from entity_id
    parts = sunstrong_entity_id.split("_")
    if len(parts) < 3:
        return None

    # Parts: ['sensor.mi', serial, ...field_parts]
    field_key = "_".join(parts[2:])  # Everything after serial

    # Map field name
    enhanced_field = INVERTER_FIELD_MAP.get(field_key, field_key)

    return f"sensor.sunpower_inverter_{serial.lower()}_{enhanced_field}"


def convert_meter_entity_id(sunstrong_entity_id: str, serial: str) -> str | None:
    """Convert SunStrong meter entity_id to Enhanced SunPower format

    SunStrong: sensor.meter_pvs6m22283193p_3_phase_power
    Enhanced:  sensor.sunpower_power_meter_pvs6m22283193p_p_3phsum_kw
    """
    if not sunstrong_entity_id.startswith("sensor.meter_"):
        return None

    # Extract field key from entity_id
    parts = sunstrong_entity_id.split("_")
    if len(parts) < 3:
        return None

    # SunStrong uses descriptive names like "3_phase_power"
    # We need to extract the actual field name from unique_id instead
    # This function will need the translation_key or unique_id to map correctly

    # For now, handle known patterns
    field_key = "_".join(parts[2:])

    # Map common display names to field names
    display_to_field = {
        "3_phase_power": "p_3phsum_kw",
        "lifetime_total_energy": "net_ltea_3phsum_kwh",
        # Add more as discovered from actual SunStrong entities
    }

    enhanced_field = display_to_field.get(field_key, field_key)
    enhanced_field = METER_FIELD_MAP.get(enhanced_field, enhanced_field)

    return f"sensor.sunpower_power_meter_{serial.lower()}_{enhanced_field}"


def convert_gateway_entity_id(sunstrong_entity_id: str, serial: str, model: str = "pvs6") -> str | None:
    """Convert SunStrong gateway entity_id to Enhanced SunPower format

    SunStrong: sensor.pvs_gateway_ram_usage
    Enhanced:  sensor.pv_supervisor_pvs6_zt222885000549w3193_ram_usage_percent
    """
    if not sunstrong_entity_id.startswith("sensor.pvs_gateway_"):
        return None

    # Extract field key
    field_key = sunstrong_entity_id.replace("sensor.pvs_gateway_", "")

    # Map field name
    enhanced_field = GATEWAY_FIELD_MAP.get(field_key, field_key)

    return f"sensor.pv_supervisor_{model.lower()}_{serial.lower()}_{enhanced_field}"


def convert_ess_entity_id(sunstrong_entity_id: str, serial: str) -> str | None:
    """Convert SunStrong ESS entity_id to Enhanced SunPower format

    SunStrong: sensor.ess_{serial}_{key}
    Enhanced:  sensor.sunpower_ess_{serial}_{key}
    """
    if not sunstrong_entity_id.startswith("sensor.ess_"):
        return None

    # Extract field key
    parts = sunstrong_entity_id.split("_")
    if len(parts) < 3:
        return None

    field_key = "_".join(parts[2:])

    # Map field name (most are identical)
    enhanced_field = ESS_FIELD_MAP.get(field_key, field_key)

    return f"sensor.sunpower_ess_{serial.lower()}_{enhanced_field}"


def convert_transfer_switch_entity_id(sunstrong_entity_id: str, serial: str) -> str | None:
    """Convert SunStrong Transfer Switch entity_id to Enhanced SunPower format

    SunStrong: sensor.transfer_switch_{serial}_{key}
    Enhanced:  sensor.sunpower_transfer_switch_{serial}_{key}
    """
    if not sunstrong_entity_id.startswith("sensor.transfer_switch_"):
        return None

    # Extract field key
    parts = sunstrong_entity_id.split("_")
    if len(parts) < 4:  # sensor, transfer, switch, serial, ...field
        return None

    # Parts: ['sensor', 'transfer', 'switch', serial, ...field_parts]
    serial_part = parts[3]
    field_key = "_".join(parts[4:])  # Everything after serial

    # Transfer switch fields are identical between integrations
    return f"sensor.sunpower_transfer_switch_{serial_part.lower()}_{field_key}"


def convert_unique_id(
    sunstrong_unique_id: str,
    device_type: str,
    new_field_key: str | None = None
) -> str:
    """Convert SunStrong unique_id to Enhanced SunPower format

    SunStrong unique_id format: {SERIAL}_{field_key}
    Enhanced unique_id format: {SERIAL}_{device_prefix}_{field_key}

    Examples:
    - Inverter: E00122142080335_current_power_production → E00122142080335_inverter_p_3phsum_kw
    - Meter: PVS6M22283193p_power_3ph_kw → PVS6M22283193p_meter_p_3phsum_kw
    - Gateway: ZT222885000549W3193_ram_usage → ZT222885000549W3193_pvs_ram_usage_percent
    - ESS: {serial}_power_3ph_kw → {serial}_ess_power_3ph_kw
    """
    parts = sunstrong_unique_id.split("_", 1)
    if len(parts) != 2:
        _LOGGER.warning("Unexpected unique_id format: %s", sunstrong_unique_id)
        return sunstrong_unique_id

    serial, old_field = parts
    field_key = new_field_key or old_field

    # Add device type prefix
    device_prefix = {
        "inverter": "inverter",
        "meter": "meter",
        "gateway": "pvs",
        "ess": "ess",
        "transfer_switch": "transfer_switch",
    }.get(device_type, device_type)

    return f"{serial}_{device_prefix}_{field_key}"


async def check_sunstrong_installed(hass: HomeAssistant) -> bool:
    """Check if SunStrong integration is still installed/enabled"""
    for entry in hass.config_entries.async_entries():
        if entry.domain == "sunstrong_pvs":
            return True
    return False


async def find_orphaned_sunstrong_entities(hass: HomeAssistant) -> list[er.RegistryEntry]:
    """Find orphaned SunStrong entities (platform exists but integration removed)"""
    entity_reg = er.async_get(hass)

    return [
        entity for entity in entity_reg.entities.values()
        if entity.platform == "sunstrong_pvs"
    ]


async def migrate_sunstrong_entities(hass: HomeAssistant, pvs_serial: str, pvs_model: str = "pvs6") -> dict[str, Any]:
    """Migrate orphaned SunStrong entities to Enhanced SunPower format

    Args:
        hass: Home Assistant instance
        pvs_serial: PVS serial number (for gateway entity naming)
        pvs_model: PVS model (pvs5 or pvs6, default pvs6)

    Returns:
        Migration results dict with counts and details

    Raises:
        ConfigEntryError: If SunStrong integration is still installed
    """
    # Safety check: Ensure SunStrong is removed
    if await check_sunstrong_installed(hass):
        raise ConfigEntryError(
            "SunStrong Migration Blocked\n\n"
            "Please remove the SunStrong (pvs-hass) integration first.\n"
            "Your entities and history will be preserved!\n\n"
            "Steps:\n"
            "1. Go to Settings → Devices & Services\n"
            "2. Find 'SunStrong PVS Monitoring'\n"
            "3. Click 'Delete'\n"
            "4. Reload Enhanced SunPower integration"
        )

    # Find orphaned entities
    orphaned = await find_orphaned_sunstrong_entities(hass)

    if not orphaned:
        _LOGGER.info("No orphaned SunStrong entities found - migration not needed")
        return {"migrated": 0, "skipped": 0, "errors": 0}

    _LOGGER.info("Found %d orphaned SunStrong entities - starting migration", len(orphaned))
    _LOGGER.info("PVS Info - Serial: %s, Model: %s", pvs_serial, pvs_model)

    entity_reg = er.async_get(hass)
    results = {
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }

    for entity in orphaned:
        _LOGGER.debug("Processing entity: %s (unique_id: %s)", entity.entity_id, entity.unique_id)
        try:
            old_entity_id = entity.entity_id
            old_unique_id = entity.unique_id

            # Determine device type and convert
            new_entity_id = None
            new_unique_id = None
            device_type = None

            # Extract serial from unique_id (format: SERIAL_field_key)
            serial = old_unique_id.split("_")[0] if "_" in old_unique_id else ""

            if old_entity_id.startswith("sensor.mi_"):
                # Inverter
                device_type = "inverter"
                new_entity_id = convert_inverter_entity_id(old_entity_id, serial)
                if new_entity_id:
                    # Extract new field key from converted entity_id
                    new_field = new_entity_id.split("_")[-1]
                    new_unique_id = convert_unique_id(old_unique_id, device_type, new_field)

            elif old_entity_id.startswith("sensor.meter_"):
                # Power Meter
                device_type = "meter"
                new_entity_id = convert_meter_entity_id(old_entity_id, serial)
                if new_entity_id:
                    new_field = "_".join(new_entity_id.split("_")[-2:])  # Last 2 parts for compound fields
                    new_unique_id = convert_unique_id(old_unique_id, device_type, new_field)

            elif old_entity_id.startswith("sensor.pvs_gateway_"):
                # Gateway/PVS
                device_type = "gateway"
                new_entity_id = convert_gateway_entity_id(old_entity_id, pvs_serial, pvs_model)
                if new_entity_id:
                    new_field = new_entity_id.split("_")[-1]
                    if new_field == "percent":  # Handle ram_usage_percent, flash_usage_percent
                        new_field = "_".join(new_entity_id.split("_")[-2:])
                    new_unique_id = convert_unique_id(old_unique_id, device_type, new_field)

            elif old_entity_id.startswith("sensor.ess_"):
                # ESS/Battery
                device_type = "ess"
                new_entity_id = convert_ess_entity_id(old_entity_id, serial)
                if new_entity_id:
                    new_field = "_".join(new_entity_id.split("_")[3:])  # After sunpower_ess_{serial}_
                    new_unique_id = convert_unique_id(old_unique_id, device_type, new_field)

            elif old_entity_id.startswith("sensor.transfer_switch_"):
                # Transfer Switch
                device_type = "transfer_switch"
                new_entity_id = convert_transfer_switch_entity_id(old_entity_id, serial)
                if new_entity_id:
                    new_field = "_".join(new_entity_id.split("_")[4:])  # After sunpower_transfer_switch_{serial}_
                    new_unique_id = convert_unique_id(old_unique_id, device_type, new_field)

            if new_entity_id and new_unique_id:
                # Check if field is supported by Enhanced SunPower
                device_type_const_map = {
                    "inverter": INVERTER_DEVICE_TYPE,
                    "meter": METER_DEVICE_TYPE,
                    "gateway": PVS_DEVICE_TYPE,
                    "ess": ESS_DEVICE_TYPE,
                    "transfer_switch": TRANSFER_SWITCH_DEVICE_TYPE,
                }

                enhanced_device_type = device_type_const_map.get(device_type)

                # Extract field name from unique_id (more reliable than entity_id)
                field_from_unique_id = old_unique_id.split("_", 1)[1] if "_" in old_unique_id else ""

                # Map SunStrong field to Enhanced field if needed
                if device_type == "inverter":
                    field_to_check = INVERTER_FIELD_MAP.get(field_from_unique_id, field_from_unique_id)
                elif device_type == "gateway":
                    field_to_check = GATEWAY_FIELD_MAP.get(field_from_unique_id, field_from_unique_id)
                elif device_type == "meter":
                    field_to_check = METER_FIELD_MAP.get(field_from_unique_id, field_from_unique_id)
                elif device_type == "ess":
                    field_to_check = ESS_FIELD_MAP.get(field_from_unique_id, field_from_unique_id)
                else:
                    field_to_check = field_from_unique_id

                # Check if Enhanced SunPower supports this field
                if not is_field_supported(enhanced_device_type, field_to_check):
                    _LOGGER.info(
                        "Skipping unsupported sensor: %s (field '%s' not in Enhanced SunPower)",
                        old_entity_id,
                        field_to_check
                    )
                    results["skipped"] += 1
                    results["details"].append({
                        "old": old_entity_id,
                        "status": "skipped",
                        "reason": f"Field '{field_to_check}' not supported by Enhanced SunPower"
                    })
                    continue

                # Field is supported - perform migration
                _LOGGER.info(
                    "Migrating %s: %s → %s (unique_id: %s → %s)",
                    device_type,
                    old_entity_id,
                    new_entity_id,
                    old_unique_id,
                    new_unique_id
                )

                entity_reg.async_update_entity(
                    old_entity_id,
                    new_entity_id=new_entity_id,
                    new_unique_id=new_unique_id,
                    platform="sunpower"
                )

                _LOGGER.info("✅ Migration successful")

                results["migrated"] += 1
                results["details"].append({
                    "old": old_entity_id,
                    "new": new_entity_id,
                    "type": device_type,
                    "status": "migrated"
                })
            else:
                _LOGGER.warning(
                    "Could not convert entity: %s (unique_id: %s)",
                    old_entity_id,
                    old_unique_id
                )
                results["skipped"] += 1
                results["details"].append({
                    "old": old_entity_id,
                    "status": "skipped",
                    "reason": "Could not determine conversion pattern"
                })

        except Exception as err:
            _LOGGER.error(
                "Error migrating entity %s: %s",
                entity.entity_id,
                err,
                exc_info=True
            )
            results["errors"] += 1
            results["details"].append({
                "old": entity.entity_id,
                "status": "error",
                "reason": str(err)
            })

    _LOGGER.info(
        "SunStrong migration complete: %d migrated, %d skipped, %d errors",
        results["migrated"],
        results["skipped"],
        results["errors"]
    )

    return results
