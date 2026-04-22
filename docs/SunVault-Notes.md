# SunVault Battery System - What We Think We Know

**IMPORTANT DISCLAIMER**: This is an internal reference document combining user reports, varserver API docs, and general knowledge. The integration author does not have a SunVault system. Treat everything here as "best current understanding." It may be incomplete or wrong. Corrections from users with actual SunVault hardware are very welcome.

Sources used:
- User reports from GitHub discussions/issues (#28, #54, #60, #63, #65)
- PVS6 varserver public variable list (pypvs-0.2.7 docs)
- General knowledge from training data (cutoff Aug 2025)
- Reddit/community observations
- Direct SunStrong support response (jeffvrba, April 2026)
- ItsaMeKielO PVS6/SunVault reverse engineering gist (April 2026): https://gist.github.com/koleson/5c719620039e0282976a8263c068e85c
- Reddit r/SunPower thread on grid charging (April 2026): https://www.reddit.com/r/SunPower/comments/1sqsvqy/

---

## Category 1: Stuff We Are Pretty Confident About

### SunPower / SunStrong Background
- SunPower filed Chapter 11 bankruptcy in August 2024
- SunStrong acquired the residential solar monitoring business afterward
- SunStrong replaced the old mySunPower app
- Many customers feel abandoned, which is a big driver of community integrations like ours
- SunStrong's cloud service communicates with the PVS via the internet (and historically cellular, but 3G shutdown makes this likely dead for US users - see PVS Hardware section)
- SunStrong has a history of poor reliability and slow feature development

### PVS Hardware
- PVS5 and PVS6 are the two supervisor unit generations
- PVS6 has WiFi WAN, LAN port, and some units have a built-in cellular modem (3G)
- The cellular modem was intended as a cloud fallback when home internet is unavailable. Personally witnessed the PVS fall back to cellular mode during a WiFi network change - so it did work.
- **3G sunset**: Major US carriers shut down traditional 3G in 2022. However, the PVS may use LTE-M or NB-IoT (narrowband IoT protocols on 4G/LTE networks, specifically designed for low-bandwidth IoT devices). These remain active on most carriers. Cellular connectivity in the SunStrong app was still observed as recently as 2025, so some form of cellular is still functional.
- SunStrong was reportedly planning to decommission the cellular service regardless.
- **Practical result**: The cellular fallback may still be active. Blocking SunStrong at the router alone may not fully isolate the PVS from the cloud if a cellular modem is present. Exact carrier and protocol unknown.
- PVS6 runs a local HTTP varserver API on port 443 (new firmware) that our integration uses
- PVS firmware is updated by SunPower/SunStrong OTA, users have no control over it
- New firmware (BUILD >= 61840 on PVS6, any build on PVS5) uses authenticated varserver API
- Old firmware uses unauthenticated dl_cgi endpoint (we still support this but plan to drop it)
- PVS has eMMC flash storage and runs an embedded Linux system
- PVS units typically reboot roughly every 24 hours. Whether this is a scheduled firmware timer or a load-related watchdog/OOM crash that happens to occur on a roughly daily cycle is not confirmed. Community observation (April 2026) suggests heavy polling can cause reboots every few hours, while light polling can extend uptime well beyond 24 hours - which may mean the "nightly reboot" is not scheduled at all, just a resource limit under typical load. Treat this as speculation.

### varserver API - Battery Variables We Know About
From the PVS6 public variable docs:

| Path | Type | Description |
|------|------|-------------|
| `/ess/config/dcm/mode_param/control_mode` | str | ESS configured control mode (read/write) |
| `/ess/config/dcm/control_param/min_customer_soc` | float | Reserve threshold 0.0-1.0 (read/write) |
| `/sys/devices/ess/{index}/opMode` | str | Real-time operational mode (read only) |
| `/sys/devices/ess/{index}/socVal` | float | State of charge (read only) |
| `/sys/devices/ess/{index}/customerSocVal` | float | Customer-facing SOC (read only) |
| `/sys/livedata/soc` | float | Battery SOC via WebSocket |
| `/sys/livedata/ess_p` | float | Battery power kW via WebSocket |
| `/sys/livedata/ess_en` | float | Battery energy kWh via WebSocket |
| `/sys/livedata/backupTimeRemaining` | uint32 | Estimated backup time (minutes) |

**Key distinction**: `control_mode` is the configured mode. `opMode` is what the battery firmware is actually doing right now. They can differ.

### TARIFF_OPTIMIZER is Automatic Firmware Behavior
Confirmed by dlp688 screenshots (issue #65, April 9 2026) - now definitively understood:
- TARIFF_OPTIMIZER appears in `opMode` (ESS Operating Mode), NOT in `control_mode` (ESS Configured Mode)
- When SOC drops to the reserve threshold or hits 100%, firmware sets `opMode` to TARIFF_OPTIMIZER
- `control_mode` stays as whatever the user configured (e.g. SELF_CONSUMPTION) - it does not change
- It is a "battery is at a limit, nothing to do right now" holding state in the operational layer
- The firmware restores normal opMode once conditions change
- **Seeing TARIFF_OPTIMIZER in ESS Operating Mode is normal.** It just means the battery is at an SOC limit.
- TARIFF_OPTIMIZER does not appear as a user option in the SunStrong app

### Two-Layer Mode Display (Confirmed)
Confirmed with side-by-side sensor screenshots from dlp688:
- `control_mode` (ESS Configured Mode sensor) = what the user has set. Follows HA selector changes. Updates every few minutes via varserver poll.
- `opMode` (ESS Operating Mode sensor) = what the battery firmware is actually doing right now. Often TARIFF_OPTIMIZER when battery is at SOC limits.
- The old integration used `opMode` for the Battery Control Mode selector display - this made it look broken because it always showed TARIFF_OPTIMIZER. Fixed in v2026.04.1.
- SunStrong app shows `control_mode` (configured), same as our ESS Configured Mode sensor. This is why SunStrong looked correct while our old selector looked wrong.

### Reserve Percentage
- Stored as a float 0.0-1.0 at `/ess/config/dcm/control_param/min_customer_soc`
- Our integration exposes 5%-100% in 5% increments
- Sets the SOC floor before reserve protection (TARIFF_OPTIMIZER) kicks in
- 25% is a valid value even though our dropdown only shows 5% increments (25% works fine)

---

## Category 2: Stuff We Think Is Probably Right But Are Not Sure

### SunVault Hardware Specs
From general knowledge (verify against current SunPower/SunStrong docs):
- SunVault uses lithium iron phosphate (LFP) chemistry (safer, longer cycle life than NMC)
- Available in stackable modules, typically 13 kWh per module
- Designed to work with SunPower microinverters and the PVS6 supervisor
- Third-party batteries (Schneider Electric, etc.) can also connect to PVS as ESS devices

### Mode Mapping (Uncertain, Needs Confirmation)
| varserver value | Our HA label | SunStrong label | Confidence |
|----------------|--------------|-----------------|------------|
| SELF_CONSUMPTION | Self Supply | Self Supply | High |
| ENERGY_ARBITRAGE | Cost Savings | Cost Savings | Medium |
| BACKUP_ONLY | Reserve | Reserve | High - confirmed calvinshih90 April 2026 |
| TARIFF_OPTIMIZER | (not user-selectable) | Not shown | High - firmware-internal holding state only |
| STANDBY | (unmapped) | Unknown | Unknown |

dlp688 raised a valid point: ENERGY_ARBITRAGE might now map to what SunStrong calls "Self Supply" and TARIFF_OPTIMIZER might have replaced ENERGY_ARBITRAGE in recent firmware. The renaming may have happened between firmware versions. Our current labels may be wrong.

### Grid Charging
- Cost Savings (ENERGY_ARBITRAGE) is the mode intended for off-peak grid charging, but only where the utility allows it.
- **The specific setting that controls this**: An internal PVS6 variable called "DCM ESS Charge Constraint." Values are `None` (grid charging allowed) or `PV Only` (solar charging only). This is not exposed in the SunStrong app. The exact varserver path is unknown; it can potentially be set via the SunStrong MQTT cloud API or the SunPower Pro Connect installer app. Source: ItsaMeKielO gist (April 2026).
- **Grid charging is locked at commissioning**: When a SunVault is commissioned, the installer sets DCM ESS Charge Constraint to `PV Only` if the utility or installer policy requires it. This is why grid charging is effectively locked post-PTO for most users. Confirmed by dlp688 (PG&E, California, April 2026).
- **Important: grid charging does NOT require grid export.** The system can be configured to charge from the grid but not discharge to the grid. This is a meaningful capability for users in states with poor net metering who want to use cheap off-peak electricity to fill their battery without selling anything back to the utility. Confirmation: SunVaultTechs (Reddit, April 2026) and ItsaMeKielO gist.
- **Outside California**: Grid charging almost certainly locked out at commissioning for most users. SunStrong also confirmed Cost Savings mode is California-only (April 2026).
- **Why Cost Savings is broken outside California**: After SunPower's bankruptcy, utility TOU rate data stopped populating correctly in the SunStrong cloud. Cost Savings mode needs real rate schedules to know when to charge/discharge. Without that data the mode idles. SunStrong confirmed they only maintain rate data for California currently. Source: ItsaMeKielO gist, Reddit thread April 2026.
- **Practical workaround for no grid charging**: Use HA weather integrations to watch for storm alerts and automatically switch to Reserve mode 1-2 days before a storm to maximize solar charging before it hits. National Weather Service or Weather.com integrations expose alert data that can trigger automations.

### SunStrong TOU Support
- **Confirmed by SunStrong support (April 2026)**: Cost Savings mode is limited to California. Expansion to other states depends on utility rules, rate designs, and regulatory approval.
- Cost Savings mode requires SunStrong to push TOU rate data to the PVS. Without that data, the firmware has no schedule to act on and the mode idles. Rate data stopped populating correctly after SunPower's bankruptcy.
- Users outside California cannot use Cost Savings mode for grid charging via SunStrong.
- TOU schedules change regularly and SunStrong almost certainly does not keep up even in California.
- TOU features may be behind a paywall in the SunStrong app.
- **Home Assistant is a better TOU solution** because you control your own schedule and can update it yourself. Use an automation to switch modes at the right times rather than relying on Cost Savings mode to know your utility's schedule.

### HA Mode Changes vs SunStrong Cloud
- Mode writes via HA selector confirmed working (dlp688, April 9 2026) - ESS Configured Mode sensor tracked changes between SELF_CONSUMPTION and ENERGY_ARBITRAGE from HA toggle
- dlp688's earlier report of "no effect" was the ~5 minute varserver update lag, not a failed write
- Whether the SunStrong cloud overrides HA-initiated mode changes is still unclear
- Both HA and SunStrong write to the same `control_mode` varserver path, so whichever writes last wins

### Periodic Mode Cycling (~12 hour pattern)
- Some users observed mode switching between values roughly every 12 hours for ~25 minutes
- Theory: battery self-test or maintenance cycle, similar to UPS behavior
- Not confirmed, could also be SunStrong cloud doing scheduled changes

---

## Category 3: Stuff We Are Mostly Guessing At

### Why TARIFF_OPTIMIZER Specifically
We do not know why the firmware uses TARIFF_OPTIMIZER as the limit-holding mode rather than STANDBY or another value. It may relate to how the SunVault was originally designed to interact with SunPower's grid services programs (selling stored energy back to the grid during peak demand), where Tariff Optimizer would have been the controlling mode. When SunPower went bankrupt, those programs may have been discontinued but the firmware behavior remained.

### SunStrong Cloud Commands
We do not know what commands the SunStrong cloud sends to the PVS, how frequently, or whether they override local varserver settings. Cellular connectivity was still observed in 2025, so the cloud channel may remain active even if home internet is blocked.

### Mode Behavior Differences by Firmware Version
User dlp688 specifically observed that mode names/mappings may have changed between firmware versions. We have no way to test this without a battery system and access to multiple firmware versions.

### Third-Party Battery Behavior
Users with Schneider Electric or other non-SunVault batteries connected to PVS may see different mode names, different varserver paths, or different behavior entirely. Our integration treats all ESS device types the same way, which may not be correct.

---

## Open Questions - WebSocket Live Data (Battery Systems)

Battery users testing live data (v2026.04.5+) have reported that "Backup Time Remaining" and "MID State" live data sensors show as Unknown even when other live data sensors update normally. The WebSocket only broadcasts fields when their values change, so if the PVS never emits `backupTimeRemaining` or `midstate` in the stream, those sensors stay Unknown indefinitely. Observed in beta testing April 2026. Unknown whether this is PVS firmware-specific or universal battery behavior.

**What we need**: Battery users on live data reporting whether these sensors ever show a value, and if so, what PVS firmware version they are on.

---

## What We Need From Users With Battery Systems

1. ~~In Cost Savings mode overnight with no solar (outside California): does the battery charge from the grid?~~ Resolved: grid charging is locked at commissioning by the utility. Cannot be overridden in software.
2. After changing mode in HA to Cost Savings, does battery behavior actually change (not just the display)?
3. Does mode behavior differ between firmware builds?
4. Do users with third-party batteries (Schneider etc.) see the same modes?
5. What does `opMode` show during normal daytime operation when SOC is not at a limit? (Confirmed TARIFF_OPTIMIZER at SOC limits - need confirmation of what it shows mid-range)

**Resolved questions:**
- opMode at SOC limits = TARIFF_OPTIMIZER (confirmed dlp688, April 9 2026)
- HA mode writes work and control_mode updates correctly (confirmed dlp688, April 9 2026)
- BACKUP_ONLY = "Reserve" in SunStrong (confirmed calvinshih90, April 12 2026). It IS a real user-facing mode. Our v2026.04.1 incorrectly mapped "Reserve" to TARIFF_OPTIMIZER instead of BACKUP_ONLY. Fixed in v2026.04.3.

---

## Our Integration and Battery Control

- Battery control (mode + reserve percentage) requires new firmware (BUILD >= 61840 or PVS5)
- Uses varserver write via `set_var()` in varserver_client.py
- Changes are sent immediately when you change the selector in HA
- PVS varserver updates its status data every few minutes, so there is a lag before HA reflects the new state
- Battery control entities only created if ESS/Battery device type detected during setup
- If battery entities go unavailable after a PVS restart: reload the integration once the battery is fully back online
- **Rebooting PVS6 with SunVault attached**: Do NOT use the breaker alone. The battery continues supplying DC power to the PVS6 even with breakers off. Procedure: (1) turn off the PVS6 breaker in the Hub+, (2) remove top plastic cover (2x Torx T25 screws), (3) disconnect the barrel connector at top right of the front circuit board that feeds DC from battery to PVS6, (4) wait a few seconds, reconnect. Source: https://gist.github.com/koleson/5c719620039e0282976a8263c068e85c#rebooting-a-pvs6-in-a-system-with-a-sunvault
- **Rebooting PVS5 (no SunVault)**: Flip the breaker or unplug. Straightforward.
- **Full SunVault system shutdown**: Press the rubber button on any battery module for 3 seconds. This powers off the batteries, Schneider inverters, and communications gateway. Use only when a full system restart is needed, not just a PVS reboot.
- Changing the PVS IP in integration config does NOT create duplicate entities (unique IDs are hardware serial based)
