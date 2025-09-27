#!/usr/bin/env python3
"""
Enhanced SunPower ESS Endpoint Test Tool
Run this script to test ESS endpoint connectivity and data structure
Usage: python test_ess.py
"""

import asyncio
import json
import sys
import aiohttp
from datetime import datetime

async def test_ess_endpoint(host="172.27.153.1", pvs_serial_last5=""):
    """Test ESS endpoint directly"""

    print(f"🔄 Testing ESS endpoint at {host}")
    print(f"⏰ Test time: {datetime.now()}")
    print("=" * 60)

    # Test ESS endpoint
    ess_url = f"http://{host}/cgi-bin/dl_cgi/energy-storage-system/status"
    print(f"📡 Testing URL: {ess_url}")

    auth = None
    if pvs_serial_last5:
        auth = aiohttp.BasicAuth("installer", pvs_serial_last5)
        print(f"🔐 Using authentication with PVS serial last 5: {pvs_serial_last5}")
    else:
        print("🔓 No authentication configured")

    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            print("🔄 Sending request...")

            async with session.get(ess_url, auth=auth) as response:
                print(f"📊 Response status: {response.status}")
                print(f"📊 Response headers: {dict(response.headers)}")

                if response.status == 200:
                    try:
                        ess_data = await response.json()
                        print("✅ ESS endpoint successful!")
                        print(f"📊 Data type: {type(ess_data)}")

                        if isinstance(ess_data, dict):
                            print(f"📊 Top-level keys: {list(ess_data.keys())}")

                            if "ess_report" in ess_data:
                                ess_report = ess_data["ess_report"]
                                print(f"📊 ESS report keys: {list(ess_report.keys())}")

                                battery_status = ess_report.get("battery_status", [])
                                print(f"📊 Battery status entries: {len(battery_status)}")

                                for i, battery in enumerate(battery_status):
                                    serial = battery.get("serial_number", "unknown")
                                    soc = battery.get("customer_state_of_charge", {})
                                    voltage = battery.get("battery_voltage", {})
                                    temp = battery.get("temperature", {})

                                    print(f"   Battery {i}: Serial={serial}")
                                    print(f"      SOC: {soc}")
                                    print(f"      Voltage: {voltage}")
                                    print(f"      Temperature: {temp}")

                                # Check for Max's specific serial
                                max_serial = "BC212200611033751040"
                                found_max = any(b.get("serial_number") == max_serial for b in battery_status)
                                if found_max:
                                    print(f"✅ Found Max's BMS serial: {max_serial}")
                                else:
                                    print(f"❌ Max's BMS serial not found: {max_serial}")
                                    print(f"   Available serials: {[b.get('serial_number') for b in battery_status]}")

                            else:
                                print("❌ No ess_report in response data")
                        else:
                            print("❌ Response is not a dictionary")

                        print("\n📄 Full response data:")
                        print(json.dumps(ess_data, indent=2))

                    except json.JSONDecodeError as e:
                        print(f"❌ Failed to parse JSON response: {e}")
                        text = await response.text()
                        print(f"📄 Raw response: {text[:500]}...")

                elif response.status == 401:
                    print("❌ Authentication required (401)")
                    print("   Try providing PVS serial last 5 characters")

                elif response.status == 404:
                    print("❌ ESS endpoint not found (404)")
                    print("   This PVS may not support battery systems")

                else:
                    print(f"❌ Unexpected response status: {response.status}")
                    text = await response.text()
                    print(f"📄 Response: {text[:500]}...")

    except aiohttp.ClientError as e:
        print(f"❌ Network error: {e}")
    except asyncio.TimeoutError:
        print("❌ Request timeout (30 seconds)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Main test function"""
    host = input("Enter PVS IP (default 172.27.153.1): ").strip() or "172.27.153.1"
    pvs_serial = input("Enter PVS serial last 5 chars (or blank for no auth): ").strip()

    print(f"\n🚀 Starting ESS endpoint test...")
    asyncio.run(test_ess_endpoint(host, pvs_serial))
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main()