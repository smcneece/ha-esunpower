"""Tests for pvs_websocket.py telemetry enable handling."""
import logging
from unittest.mock import AsyncMock

import pytest

from custom_components.sunpower.pvs_websocket import PVSWebSocket


def make_ws(enable_callback=None):
    return PVSWebSocket(host="192.168.1.50", enable_callback=enable_callback)


async def test_refused_enable_is_reported(caplog):
    """A PVS that refuses to broadcast must produce a warning.

    Regression test: enable_telemetry_websocket returns a bool, and the caller
    used to discard it. A refusal raises nothing, and the PVS still accepts the
    WebSocket handshake on port 9002 whether or not telemetry is on, so the
    connection succeeds and simply never delivers a frame. Confirmed on a live
    PVS6: /sys/telemetryws/enable read 0, the socket connected in 0.4s, and no
    message arrived in 20s. Every live data sensor stayed unavailable with
    nothing above debug in the log.
    """
    ws = make_ws(AsyncMock(return_value=False))

    with caplog.at_level(logging.WARNING):
        assert await ws._ensure_telemetry_enabled() is False

    assert "/sys/telemetryws/enable" in caplog.text, (
        "the warning must name the variable, otherwise it isn't actionable"
    )


async def test_successful_enable_is_quiet():
    """The normal path must not warn, or the warning stops meaning anything."""
    ws = make_ws(AsyncMock(return_value=True))
    assert await ws._ensure_telemetry_enabled() is True


async def test_enable_exception_still_reported(caplog):
    """An exception from the callback keeps its existing warning."""
    ws = make_ws(AsyncMock(side_effect=OSError("connection refused")))

    with caplog.at_level(logging.WARNING):
        assert await ws._ensure_telemetry_enabled() is False

    assert "connection refused" in caplog.text


async def test_no_callback_is_treated_as_enabled():
    """enable_callback is optional; without one there is nothing to verify."""
    ws = make_ws(None)
    assert await ws._ensure_telemetry_enabled() is True


@pytest.mark.parametrize("result", [None, 1, "ok"])
async def test_only_false_counts_as_refusal(result, caplog):
    """Only an explicit False is a refusal.

    The callback is typed to return bool, but guarding on falsiness would turn
    a None from some future code path into a spurious warning. Check identity
    against False so the test pins the intent rather than the truthiness.
    """
    ws = make_ws(AsyncMock(return_value=result))

    with caplog.at_level(logging.WARNING):
        assert await ws._ensure_telemetry_enabled() is True

    assert caplog.text == ""


def test_stale_after_receiving_frames_does_not_warn(caplog):
    """A socket that goes quiet after delivering data is ordinary, not broken.

    The PVS has stretches with nothing to say, and its auth session ages out,
    so healthy systems see stale reconnects routinely. Warning on those would
    tell those users the PVS isn't broadcasting telemetry, which is false for
    them, and would train everyone to ignore the message that matters.
    """
    ws = make_ws()

    with caplog.at_level(logging.WARNING):
        assert ws._note_stale(120.0, received_any=True, url="ws://pvs:9002") is False

    assert caplog.text == ""
    assert ws._warned_never_received is False, (
        "a healthy stale reconnect must not consume the warning latch"
    )


def test_stale_without_any_frame_warns_once(caplog):
    """Connected but never received is the broken case, and it warns once.

    This is the #99 scenario: telemetry off, the PVS accepts the handshake and
    sends nothing, and the client reconnects every 90s forever. The heartbeat
    re-checks on every cycle, so warning each time would flood the log.
    """
    ws = make_ws()

    with caplog.at_level(logging.WARNING):
        assert ws._note_stale(95.0, received_any=False, url="ws://pvs:9002") is True
    assert "/sys/telemetryws/enable" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert ws._note_stale(95.0, received_any=False, url="ws://pvs:9002") is False
    assert caplog.text == ""


def test_latch_clears_once_data_arrives(caplog):
    """After a silent run recovers, a later silent run must warn again."""
    ws = make_ws()
    ws._note_stale(95.0, received_any=False, url="ws://pvs:9002")

    ws._warned_never_received = False   # what the message loop does on a frame

    with caplog.at_level(logging.WARNING):
        assert ws._note_stale(95.0, received_any=False, url="ws://pvs:9002") is True
    assert "/sys/telemetryws/enable" in caplog.text


def test_stale_warning_latch_starts_clear():
    """Nothing has been warned about on a fresh client."""
    assert make_ws()._warned_never_received is False
