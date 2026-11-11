# Migrating from the SunStrong PVS Integration

This guide covers moving from SunStrong's [pvs-hass](https://github.com/SunStrong-Management/pvs-hass) integration (domain `sunstrong_pvs`) to Enhanced SunPower while keeping your sensor history and Energy Dashboard.

Coming from krbaker's original SunPower integration instead? See [MIGRATION.md](MIGRATION.md).

**⚠️ Make a full Home Assistant backup first:** Settings, System, Backups, Create Backup.

## How It Works

There is no automatic migration, but both integrations read the same values from the PVS. Home Assistant keeps history and long-term statistics by **entity ID**, so if you give each Enhanced SunPower entity the entity ID your old SunStrong entity had, the history and Energy Dashboard carry on from where they left off.

SunStrong's own guide for moving from krbaker to their integration uses this same rename method. Enhanced SunPower kept krbaker's sensor names, so their mapping table read in reverse is exactly the table below.

## Steps

1. **Install Enhanced SunPower** from HACS and set it up, following the [Installation](../README.md#installation) section of the README. It can run alongside the SunStrong integration for the few minutes this takes. Leave WebSocket Live Data off for now.
2. **Write down the entity IDs you want to keep** from the SunStrong integration. At minimum, the ones used in your Energy Dashboard (Settings, Dashboards, Energy) and in any automations or dashboards. The easiest way is Settings, Devices & Services, Entities, then search for the device.
3. **Remove the SunStrong integration:** Settings, Devices & Services, find the PVS integration, three-dot menu, Delete. Its history stays in the database. This frees up its entity IDs so Enhanced SunPower can use them.
4. **Rename the Enhanced SunPower entities.** For each sensor you wrote down, find the matching Enhanced SunPower entity using the table below, open it, click the gear icon, and change the **Entity ID** to the old one.
5. **Check one sensor before doing them all.** Rename one inverter's `Lifetime Power`, wait for the next poll, and open its history. The old SunStrong history should be there with the new readings continuing from it. Then do the rest.
6. **Remove the SunStrong repository from HACS** (HACS, find the SunStrong PVS integration, three-dot menu, Remove), then restart Home Assistant.
7. **Turn on WebSocket Live Data** in Configure if you want it, then reload the integration.

Do the renames soon after setup. Readings Enhanced SunPower recorded under its own entity IDs before the rename are not moved over.

## Sensor Mapping

Each sensor is on the device with the same serial number in both integrations.

### Power Meters

| SunStrong | Enhanced SunPower |
| --- | --- |
| `Positive Lifetime Energy` | `KWh To Home` |
| `Negative Lifetime Energy` | `KWh To Grid` |
| `Net Lifetime Energy` | `Lifetime Power` |
| `3-Phase Power` | `Power` |
| `Reactive Power 3-Phase` | `Reactive Power` |
| `Apparent Power 3-Phase` | `Apparent Power` |
| `Total Power Factor` | `Power Factor` |
| `Frequency` | `Frequency` |
| `Line-to-Line Voltage` | `Supply Volts` |
| `Phase 1-N Voltage` | `Leg 1 Volts` |
| `Phase 2-N Voltage` | `Leg 2 Volts` |
| `Current Phase 1` | `Leg 1 Amps` |
| `Current Phase 2` | `Leg 2 Amps` |
| `Power Phase 1` | `Leg 1 KW` |
| `Power Phase 2` | `Leg 2 KW` |

### Inverters

| SunStrong | Enhanced SunPower |
| --- | --- |
| `Lifetime Production` | `Lifetime Power` |
| `Current Power Production` | `Power` |
| `Production Voltage` | `Voltage` |
| `Production Current` | `Amps` |
| `Grid Frequency` | `Frequency` |
| `Heatsink Temperature` | `Temperature` |

### PVS Gateway

| SunStrong | Enhanced SunPower |
| --- | --- |
| `Gateway uptime` | `Uptime` |
| `RAM usage` | `RAM Usage` |
| `Flash usage` | `Flash Usage` |
| `Flash wear (Type B)` | `Flash Wear` |
| `Firmware version` | `Firmware Version` |

SunStrong's `CPU usage` is on a different scale from Enhanced SunPower's `System Load`, so don't merge those two.

### SunVault / ESS

| SunStrong | Enhanced SunPower |
| --- | --- |
| `State of Charge` | `State of Charge` |
| `Customer State of Charge` | `Customer State of Charge` |
| `State of Health` | `State of Health` |
| `3-Phase Power` | `Power` |
| `Positive Lifetime Energy` | `Lifetime Energy Discharged` |
| `Negative Lifetime Energy` | `Lifetime Energy Charged` |
| `Battery Voltage` | `Battery Voltage` |
| `Inverter Temperature` | `Inverter Temperature` |
| `Operating Mode` | `Operating Mode` |
| `Charge Limit Power Max` | `Charge Limit` |
| `Discharge Limit Power Max` | `Discharge Limit` |
| `Max Battery Cell Temperature` | `Max Cell Temperature` |
| `Min Battery Cell Temperature` | `Min Cell Temperature` |
| `Max Battery Cell Voltage` | `Max Cell Voltage` |
| `Min Battery Cell Voltage` | `Min Cell Voltage` |
| `Phase 1-N Voltage` | `V1N Voltage` |
| `Phase 2-N Voltage` | `V2N Voltage` |

### Transfer Switch

| SunStrong | Enhanced SunPower |
| --- | --- |
| `MIDC State` | `Main Breaker State` |
| `PVD1 State` | `PV Disconnect State` |
| `MIDC Temperature` | `Temperature` |
| `Grid Phase 1-N Voltage` | `Grid Voltage L1` |
| `Grid Phase 2-N Voltage` | `Grid Voltage L2` |
| `Phase 1-N Voltage` | `Load Voltage L1` |
| `Phase 2-N Voltage` | `Load Voltage L2` |
| `MIDC Supply Voltage` | `Supply Voltage` |

### WebSocket Live Data

These are on the **PVS Live Data** device in Enhanced SunPower, and only exist once Live Data is turned on.

| SunStrong | Enhanced SunPower |
| --- | --- |
| `Live Production Power` | `Production Power` |
| `Live Net Consumption Power` | `Net Power` |
| `Live Site Load Power` | `Site Load Power` |
| `Live Battery Power` | `Battery Power` |
| `Live Battery State of Charge` | `Battery State of Charge` |

**Don't migrate the Live Data energy sensors** (`Live Production Energy`, `Live Net Consumption Energy`, `Live Site Load Energy`, `Live Battery Energy`). Enhanced SunPower deliberately doesn't give these a state class, so they can't be used in the Energy Dashboard. Use the polled lifetime sensors above (`Lifetime Power`, `KWh To Home`, `KWh To Grid`) for Energy Dashboard sources instead. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for why.

## Things That Don't Carry Over

- **Battery controls work differently.** SunStrong has `Charge from grid` and `Grid enabled` switches. Enhanced SunPower has a battery mode select (Self Supply, Cost Savings, Emergency Reserve, Tariff Optimizer) and a reserve percentage select. Automations that used the SunStrong switches need to be rewritten.
- **Sensors only Enhanced SunPower has** (inverter MPPT sensors, the virtual production meter, the diagnostic sensors, flash memory and inverter health alerts) start fresh, there's nothing to migrate them from.
- **Leftover devices.** If a SunStrong device is still listed after removing the integration, try deleting it from the three-dot menu on the device page.

## Need Help?

- **Troubleshooting Guide:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Report Issues:** [GitHub Issues](https://github.com/smcneece/ha-esunpower/issues)
- **Ask Questions:** [GitHub Discussions](https://github.com/smcneece/ha-esunpower/discussions)
