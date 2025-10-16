# Troubleshooting Guide

## Common Issues

### Polling Interval vs Data Update Rates

**Issue**: "I changed polling to 30 seconds but meter/inverter power still only updates every few minutes"

**This is normal PVS hardware behavior!** The integration polls at your configured interval, but the PVS controls when it updates different data.

**Why?** The PVS likely caches meter/inverter data to reduce polling stress on those devices (similar to old firmware protection).

**How to Verify Polling Works:**
1. Go to Settings → Devices & Services → Enhanced SunPower → PVS device
2. Watch the **Uptime** sensor - should update at your configured interval
3. Meter power will still only change every ~5 min (PVS hardware limitation)

**Or enable Debug Notifications:**
1. Settings → Devices & Services → Enhanced SunPower → Configure
2. Enable "Debug Notifications"
3. Watch for coordinator poll time notifications

**Bottom Line:** Faster polling gets you fresher PVS system stats, but doesn't make power readings update faster.

### PVS Not Responding
1. **Verify IP Address**: PVS typically uses `172.27.153.1`
2. **Check Authentication**: Ensure PVS serial number (last 5 digits) is correct in integration settings
3. **Monitor Health Checks**: Integration shows health check attempts in notifications
4. **Check Backoff Status**: Integration may be in cooldown period after failures
5. **PVS Reboot**: If persistent, power cycle the PVS (turn off breaker for 60 seconds)

### 🔐 **Authentication Issues (New Firmware)**
1. **Check Serial Number**: Verify last 5 digits of PVS serial in integration configuration
2. **Firmware Detection**: Integration automatically detects if authentication is required
3. **Authentication Alerts**: Watch for critical authentication failure notifications
4. **Reset Integration**: Reconfigure if authentication settings are incorrect
5. **Contact Support**: If serial number is correct but authentication still fails

### ⚡ **Hardware/Power Issues (USB Setups)**
1. **Check Power Draw**: Measure combined USB device power consumption
2. **Single Adapter**: Use only one USB-Ethernet adapter per power source
3. **Dedicated Power**: Power USB adapters separately from Pi/computer
4. **Powered Hub**: Use quality powered USB hub rated for network adapters
5. **Cable Length**: Use shorter, thicker USB cables to minimize voltage drop
6. **Monitor Logs**: Check for USB disconnect messages in system logs

### Unit Change Notifications After Upgrade
![Unit Change Dialog](images/upgrade_error.png)

**Expected Behavior**: Enhanced integration fixes unit inconsistencies from original.

**Recommended Action**: Click **"Update the unit of the historic statistic values"** to:
- ✅ Preserve all historical data
- ✅ Fix unit displays (shows proper % symbols)
- ✅ Improve HA statistics consistency

**Why This Happens**: Enhanced integration properly declares percentage units for sensors like "System Load" that previously had no units.

### All Entities Show "Unavailable" or Config UI Corrupted
1. **🌐 Force Browser Refresh**: **Ctrl+F5** (Windows) or **Cmd+Shift+R** (Mac) to clear cached files
2. **Check Integration Status**: Look for "Fresh data from PVS" notifications
3. **Verify Health Check**: Should see "PVS Health Check" notifications in debug mode
4. **Monitor Notifications**: Check for "PVS OFFLINE" or backoff messages
5. **Check PVS Response**: Try manual test: `curl http://172.27.153.1/cgi-bin/dl_cgi?Command=DeviceList`

### Diagnostic Sensors Not Working
1. **Check Device**: Look for "Enhanced SunPower Diagnostics" device
2. **Verify Sensors**: Should see 7 diagnostic sensors with real values
3. **Wait for Data**: Some sensors need a few polling cycles to show meaningful data
4. **Check Logs**: Look for diagnostic tracking messages in HA logs
5. **Time Display**: Verify "Last Successful Poll" shows readable format (e.g., "5 minutes ago")

### Inverter Health Alerts
1. **Individual Inverter Offline**: Check specific inverter mentioned in alert
2. **Multiple Inverter Issues**: May indicate PVS communication problems
3. **False Positive Alerts**: Verify inverter is actually producing power
4. **Recovery Notifications**: Normal when inverters come back online after maintenance

### Mobile Notifications Not Working
1. **Check Mobile App**: Ensure Home Assistant mobile app is installed and configured
2. **Verify Service Name**: Check that selected mobile service exists
3. **Test Notification**: Use HA Developer Tools to test mobile notification service
4. **Fallback Behavior**: Should automatically use persistent notifications if mobile fails

### Battery Data Missing
1. **Enable Battery System**: Check integration configuration options
2. **Verify SunVault Installation**: Ensure batteries are properly connected to PVS
3. **Check Notifications**: Look for battery detection warnings
4. **ESS Communication**: Battery data requires separate ESS API endpoint

### Energy Dashboard - Missing Grid Import/Export Sensors

**Issue**: "KWh To Grid" and "KWh To Home" sensors not available for Energy Dashboard configuration

**Root Cause**: Grid import/export tracking requires consumption CT clamps with bidirectional metering support.

**Three Common Scenarios:**

**1️⃣ No Consumption CT Clamps Installed**
- **Symptom**: No consumption meter device (only production meter exists)
- **Why**: Some installers don't install consumption CT clamps in electrical panel
- **Detection**: Check devices - you should see both `Power Meter *p` (production) AND `Power Meter *c` (consumption)
- **Practical Solutions**:
  - Use utility smart meter integration (recommended - most accurate)
  - Install third-party CT clamp system (Emporia Vue, Sense, etc.)
  - Note: SunPower installer service may be difficult/expensive to obtain post-bankruptcy

**2️⃣ CT Clamps Installed But Not Provisioned**
- **Symptom**: No consumption meter device, but CT clamps are physically installed in electrical panel
- **Why**: Installer installed hardware but didn't enable/configure it in PVS settings
- **Detection**: Physical inspection - CT clamps present on main panel wires but no consumption meter in HA
- **Practical Solutions**:
  - Use utility smart meter integration (easiest - no PVS changes needed)
  - Contact installer to provision CT clamps in PVS (may be costly/difficult post-SunPower bankruptcy)
  - Install third-party CT clamp system as alternative

**3️⃣ PVS5 Firmware Limitation (CT Clamps Installed & Provisioned)**
- **Symptom**: Consumption meter exists but only shows "Lifetime Power" - missing "KWh To Grid" and "KWh To Home" sensors
- **Why**: Some PVS5 systems only report net consumption (`net_ltea_3phsum_kwh`) instead of separate import/export counters
- **Detection**: Download diagnostics and check consumption meter data:
  - ✅ **PVS6/newer**: Has `neg_ltea_3phsum_kwh` (to grid) AND `pos_ltea_3phsum_kwh` (from grid)
  - ❌ **PVS5/limited**: Only has `net_ltea_3phsum_kwh` (net total)
- **Workaround Options**:
  - Use utility smart meter integration (most accurate for billing)
  - Create template sensors to split net consumption into import/export

**Reference**: [krbaker Issue #13 - KWH to Grid not working](https://github.com/krbaker/hass-sunpower/issues/13)

**Alternative Energy Dashboard Setup (Without Grid Sensors)**:
- **Solar Production**: Use Virtual Production Meter or individual inverter sensors
- **Grid Consumption**: Use utility smart meter integration or third-party CT clamp system (Emporia Vue, Sense, etc.)

## Network Setup Issues

### **Hardware Power Requirements & Known Issues**

**CRITICAL: PVS USB Power Limitation Warning**

Many users power their Raspberry Pi directly from the PVS USB ports. However, the PVS has **limited USB power capacity** that can cause **random connection drops** when exceeded:

**The Problem:**
- **PVS USB ports** have limited power output (exact specs unknown)
- **Dual USB-Ethernet setup** (WAN + LAN adapters) can exceed this capacity
- **Raspberry Pi Zero 2 W** alone can draw up to **1.5A**
- **USB-Ethernet adapters** add ~500-800mA each
- **Combined load** can exceed PVS USB power capacity

**Real-World Example:**
*I experienced random PVS connectivity issues using **two SunPower-approved USB-Ethernet adapters** (one for WAN, one for LAN) powered from PVS USB ports. Problem completely resolved by switching PVS back to WiFi for WAN connection, leaving only one USB-Ethernet adapter for LAN polling.*

**Symptoms of PVS USB Power Overload:**
- **Random "PVS OFFLINE" alerts** despite network functioning normally
- **Integration works fine for hours, then suddenly fails**
- **PVS becomes completely unresponsive** requiring power cycle
- **Both WAN and LAN connections drop randomly**

**Practical Solutions:**

**Recommended: Reduce USB Load**
- **Use WiFi for PVS WAN** connection (phoning home to SunPower)
- **Single USB-Ethernet adapter** for LAN polling only
- **Significantly reduces** PVS USB power draw
- **Fits within limited PVS enclosure space**

**Alternative: External Pi Power**
- **External power supply** for Raspberry Pi (don't use PVS USB for Pi power)
- **Note**: Space constraints in PVS enclosure make this challenging

**Important Notes:**
- **No PVS logs available** - you won't see USB disconnect messages
- **SunPower-approved hardware** can still exceed power limits in dual configuration
- **Random failures** are the primary symptom, not permanent connection loss
- **PVS newer models** often lack RJ45 jacks, requiring USB-Ethernet solutions

### Network Architecture Overview
```
Internet ──┐
           │
     Your Router/Switch
           │
    ┌──────┼──────┐
    │             │
PVS WAN Port   PVS LAN Port (172.27.153.1)
(SunPower      │
 Cloud)        └── Isolated Network → Home Assistant
```

### Network Setup
With authentication support, network setup is simplified:

- **Direct Connection**: PVS can be accessed directly using standard IP addressing
- **Legacy Setups**: Existing VLAN or proxy configurations will continue to work
- **Simplified Troubleshooting**: Authentication eliminates most network isolation issues

**For detailed network setup guidance**, see existing community resources and [@krbaker's documentation](https://github.com/krbaker/hass-sunpower#network-setup).

**Support Scope**: Network configuration is outside the scope of this integration. We provide general guidance but recommend consulting community network guides for detailed setup assistance.

## Debug Information
Enable debug notifications to monitor:
- Health check attempts and results
- Polling status and timing decisions
- Sunrise/sunset transitions with elevation values and active thresholds
- PVS response times and data quality
- Auto-recovery events and cache usage
- Individual inverter health status
- Mobile notification delivery status
- Authentication status and session management
- Time conversion accuracy
