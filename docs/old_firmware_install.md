# Old Firmware Install Guide

Old firmware support (dl_cgi, BUILD below 61840 on PVS6 or below 5408 on PVS5) was removed in the v2026.06.x release series. **v2026.05.1 is the last version of Enhanced SunPower that supports old firmware.**

If your PVS is on old firmware, you can continue using the integration indefinitely by pinning to v2026.05.1. Your sensors, history, and automations are preserved. You simply will not receive future updates.

---

## What Is Old Firmware?

- **PVS6**: BUILD number below 61840
- **PVS5**: BUILD number below 5408

You can check your firmware from Home Assistant: Settings, Devices and Services, Enhanced SunPower, open the PV Supervisor device. The firmware version shown contains your BUILD number. Alternatively check the Enhanced SunPower Diagnostics device.

---

## Pinning to v2026.05.1

### If you installed via HACS

HACS always installs the latest version. If you leave it installed via HACS, a future HACS update will silently upgrade you to a version that no longer supports old firmware and the integration will stop working.

**To pin:**
1. Go to HACS and remove Enhanced SunPower
2. Go to the [GitHub Releases page](https://github.com/smcneece/ha-esunpower/releases) and find v2026.05.1
3. Download the release zip and extract the `custom_components/sunpower` folder into your HA `custom_components` directory
4. Restart Home Assistant

After this, HACS no longer manages the integration and will not update it. You are pinned to v2026.05.1 indefinitely.

### If you installed manually

You are already protected. Do not update past v2026.05.1 and the integration will continue working.

---

## Network Setup for Old Firmware

Old firmware requires the PVS LAN port at `172.27.153.1`. The LAN port runs its own DHCP and DNS server, so it must be isolated from your main network on a dedicated VLAN or switch connection.

**Option 1: Dedicated VLAN (Managed Switch)**
- Create an isolated VLAN for the PVS LAN port connection
- Add a static route on your router for `172.27.153.0/24` pointing toward your HA host
- HA must have a network interface reachable in that VLAN
- See community guides for specific router/switch configuration

**Option 2: Raspberry Pi Proxy**
- Popular community solution using a Pi as a bridge between PVS LAN and your main network
- Pi connects to PVS LAN port via USB-to-Ethernet adapter
- See [@krbaker's documentation](https://github.com/krbaker/hass-sunpower#network-setup) for detailed setup instructions

### Network Architecture

```
Internet -> Your Router/Switch
                  |
      +-----------+-----------+
      |                       |
  PVS WAN Port            PVS LAN Port (172.27.153.1)
  (SunPower Cloud)            |
                         Isolated Network -> Home Assistant
```

---

## USB Power Warning for Raspberry Pi Setups

Many users power their Raspberry Pi from the PVS USB ports. This can cause random connection drops if the combined power draw exceeds the PVS USB capacity.

**Symptoms:**
- Random "PVS OFFLINE" alerts despite network functioning normally
- Integration works fine for hours then suddenly fails
- PVS becomes unresponsive requiring a power cycle

**Solutions:**
- Use WiFi for PVS WAN (SunPower cloud) and a single USB-Ethernet adapter for LAN polling only
- Power the Raspberry Pi externally rather than from the PVS USB ports

---

## Troubleshooting Old Firmware

### PVS Not Responding

1. Verify IP is `172.27.153.1` (LAN port required, old firmware does not support WAN polling)
2. Check network isolation: the PVS LAN port must be on an isolated VLAN or dedicated switch connection
3. Verify a static route exists for `172.27.153.0/24` on your router or HA host
4. Check the Raspberry Pi or VLAN configuration if using a bridge
5. Power cycle the PVS (turn off breaker for 60 seconds) if the issue persists

**Quick test** (run from HA host):
```
curl http://172.27.153.1/cgi-bin/dl_cgi?Command=DeviceList
```
If this returns JSON device data, the network path to the PVS is working.

### Health Check Behavior (Old Firmware)

Old firmware performed TCP health checks before each HTTP poll to detect PVS availability. If the integration reported health check failures, the usual causes were:

- Network isolation not configured correctly (PVS LAN not reachable from HA)
- Raspberry Pi bridge offline or not routing traffic
- PVS itself powered down or unresponsive

### Flash Memory (Old Firmware)

Old firmware uses a MB-based flash memory threshold for alerts. If you see flash memory alerts on v2026.05.1, the threshold is configured in MB (not percentage as in newer versions). The alert fires when free flash drops below the configured MB value.

---

## Migrating From the Original krbaker Integration

If you are migrating from [@krbaker's original SunPower integration](https://github.com/krbaker/hass-sunpower) to Enhanced SunPower on old firmware, see [MIGRATION.md](MIGRATION.md) for step-by-step instructions. Back up your configuration before migrating.

---

## Getting Help

If you are stuck on old firmware and need assistance, the community is still the best resource:

- [GitHub Discussions](https://github.com/smcneece/ha-esunpower/discussions)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
- [@krbaker's original integration](https://github.com/krbaker/hass-sunpower) for old-firmware-specific network guidance
