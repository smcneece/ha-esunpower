"""Tests for data_processor.py pure functions."""
import json
from pathlib import Path

import pytest

SAMPLE_DATA_PATH = Path(__file__).parent.parent / "json-data" / "dl_cgi.json"


def load_sample_data():
    with open(SAMPLE_DATA_PATH) as f:
        return json.load(f)


def test_convert_sunpower_data_basic_structure():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    result = convert_sunpower_data(load_sample_data())
    assert isinstance(result, dict)
    assert "PVS" in result
    assert "Inverter" in result
    assert "Power Meter" in result


def test_convert_sunpower_data_creates_virtual_meter():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    result = convert_sunpower_data(load_sample_data())
    meters = result.get("Power Meter", {})
    virtual = [s for s, d in meters.items() if d.get("interface") == "virtual"]
    assert len(virtual) >= 1


def test_convert_sunpower_data_inverters_indexed_by_serial():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    result = convert_sunpower_data(load_sample_data())
    for serial, inverter in result.get("Inverter", {}).items():
        assert inverter.get("SERIAL") == serial


def test_convert_sunpower_data_returns_empty_on_none():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    assert convert_sunpower_data(None) == {}


def test_convert_sunpower_data_returns_empty_on_missing_devices_key():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    assert convert_sunpower_data({}) == {}
    assert convert_sunpower_data({"other_key": []}) == {}


def test_convert_sunpower_data_returns_empty_on_empty_devices():
    from custom_components.sunpower.data_processor import convert_sunpower_data
    assert convert_sunpower_data({"devices": []}) == {}


def test_no_device_field_leaks_pvs_password_except_serial():
    """The PVS serial's last 5 characters are the varserver auth password
    (see mask_pvs_serial()). They must never appear in any device field
    that Home Assistant can render as user-visible text - DESCR (device
    name fallback, entity title substitution), or anything else - for ANY
    device, including ones derived from the PVS serial like the virtual
    production meter and virtual SunVault.

    The one accepted exception is the SERIAL field itself: it's used only
    as an internal identifier (dict key, HA unique_id/device identifier),
    never rendered directly as text, and entity.py/sensor.py apply masking
    separately whenever a device's own SERIAL would otherwise be shown.

    This test exists because a virtual meter's DESCR embedding the full
    unmasked PVS serial (`f"Virtual Production Meter {pvs_serial}pv"`)
    shipped and passed manual review twice before a HACS reviewer caught
    it - this makes that specific class of regression fail automatically.
    """
    from custom_components.sunpower.const import PVS_DEVICE_TYPE
    from custom_components.sunpower.data_processor import convert_sunpower_data

    raw_data = load_sample_data()
    pvs_serial = next(
        d["SERIAL"] for d in raw_data["devices"] if d.get("DEVICE_TYPE") == PVS_DEVICE_TYPE
    )
    password = pvs_serial[-5:]

    result = convert_sunpower_data(raw_data)
    assert result, "fixture produced no data - test would pass vacuously"

    for device_type, devices in result.items():
        for serial, device in devices.items():
            if not isinstance(device, dict):
                continue
            for field, value in device.items():
                if field == "SERIAL":
                    continue
                assert password not in str(value), (
                    f"PVS password leaked into {device_type}/{serial}/{field}: {value!r}"
                )
