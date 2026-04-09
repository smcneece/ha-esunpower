# SunVault Battery System - What We Think We Know

**IMPORTANT DISCLAIMER**: This is an internal reference document combining user reports, varserver API docs, and general knowledge. The integration author does not have a SunVault system. Treat everything here as "best current understanding." It may be incomplete or wrong. Corrections from users with actual SunVault hardware are very welcome.

Sources used:
- User reports from GitHub discussions/issues (#28, #54, #60, #63, #65)
- PVS6 varserver public variable list (pypvs-0.2.7 docs)
- General knowledge from training data (cutoff Aug 2025)
- Reddit/community observations

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
- PVS does a nightly scheduled reboot (approximately every 23-24 hours, firmware controlled)

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
Confirmed by multiple users (jeffvrba, calvinshih90, issue #65):
- When SOC drops to the reserve threshold, firmware automatically sets `control_mode` to TARIFF_OPTIMIZER
- When SOC hits 100%, firmware automatically sets `control_mode` to TARIFF_OPTIMIZER
- It is a "battery is at a limit, nothing to do right now" holding state
- The battery restores the previous mode once conditions change
- **Seeing TARIFF_OPTIMIZER in HA does not mean you set it.** It is normal firmware behavior.
- TARIFF_OPTIMIZER does not appear as a user option in the SunStrong app for most users

### Two-Layer Mode Display
- SunStrong shows the user-configured mode (what you chose in the app)
- Our integration reads `control_mode` from the varserver, which is what the battery firmware is currently doing
- When firmware overrides the mode at SOC limits, HA shows the override while SunStrong still shows your configured mode
- Both are correct. They are showing different things. This is not a bug.

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
| ENERGY_ARBITRAGE | Cost Savings | Cost Savings (?) | Medium - may have changed |
| BACKUP_ONLY | Emergency Reserve | Reserve (?) | Low - not confirmed |
| TARIFF_OPTIMIZER | Tariff Optimizer | Not user-selectable | High that it is firmware-internal |
| STANDBY | (unmapped) | Unknown | Unknown |

dlp688 raised a valid point: ENERGY_ARBITRAGE might now map to what SunStrong calls "Self Supply" and TARIFF_OPTIMIZER might have replaced ENERGY_ARBITRAGE in recent firmware. The renaming may have happened between firmware versions. Our current labels may be wrong.

### Grid Charging
- Cost Savings (ENERGY_ARBITRAGE) is the mode intended for off-peak grid charging
- Whether it actually charges from the grid overnight (no solar) is not confirmed in our testing
- Emergency Reserve mode may also trigger grid charging if SOC is below the reserve threshold and no solar is available
- Some users (jeffvrba) plan to test this - we need the results

### SunStrong TOU Support
- SunStrong TOU optimization likely requires a partnership/configuration between SunPower and the specific utility
- Probably only supports a handful of major utilities
- TOU schedules change regularly and SunStrong almost certainly does not keep up
- TOU features may be behind a paywall in the SunStrong app
- **Home Assistant is a better TOU solution** because you control your own schedule and can update it yourself

### HA Mode Changes vs SunStrong Cloud
- We write mode changes to the varserver immediately when you change the selector in HA
- Whether the SunStrong cloud overrides our changes is unclear
- dlp688 reported no visible effect in SunStrong when setting mode via HA
- Could be the two-layer display issue (SunStrong shows configured mode, we show operational mode)
- Could mean our writes are being ignored or overridden
- Needs more testing from users

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

## What We Need From Users With Battery Systems

1. Set "Emergency Reserve" in HA, wait a few minutes, check SunStrong. Does it show "Reserve"? This would confirm or deny our BACKUP_ONLY mapping.
2. In Cost Savings mode overnight with no solar: does the battery actually charge from the grid?
3. What does `opMode` report during normal operation vs at SOC limits?
4. After changing mode in HA, does battery behavior actually change (not just the display)?
5. Does mode behavior differ between firmware builds?
6. Do users with third-party batteries (Schneider etc.) see the same modes?

---

## Our Integration and Battery Control

- Battery control (mode + reserve percentage) requires new firmware (BUILD >= 61840 or PVS5)
- Uses varserver write via `set_var()` in varserver_client.py
- Changes are sent immediately when you change the selector in HA
- PVS varserver updates its status data every few minutes, so there is a lag before HA reflects the new state
- Battery control entities only created if ESS/Battery device type detected during setup
- If battery entities go unavailable after a PVS restart: reload the integration once the battery is fully back online
- Changing the PVS IP in integration config does NOT create duplicate entities (unique IDs are hardware serial based)
