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
