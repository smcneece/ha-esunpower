"""WebSocket client for PVS live data."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import random
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

import aiohttp

from .livedata import LIVEDATA_FIELD_DEFINITIONS, PVSLiveData

_LOGGER = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


# Pre-built lookup table for websocket message processing
# Maps ws_field_name -> (var_path, attr_name, value_type)
_WS_FIELD_MAP: dict[str, tuple[str, str, str]] = {
    ws_field: (var_path, attr_name, value_type)
    for ws_field, var_path, attr_name, value_type in LIVEDATA_FIELD_DEFINITIONS
}


# Type aliases for callbacks
LiveDataCallback = Callable[[set[str]], None]
ConnectionStateCallback = Callable[[ConnectionState], None]


class PVSWebSocket:
    """WebSocket client for PVS live data with auto-reconnect."""

    def __init__(
        self,
        host: str,
        port: int = 9002,
        enable_callback: Callable[[], Any] | None = None,
    ) -> None:
        """Initialize the WebSocket client.

        Args:
            host: PVS hostname or IP address (without port)
            port: WebSocket port (default 9002)
            enable_callback: Optional async callable invoked before each
                connection attempt to ensure the telemetry websocket is
                enabled on the PVS.
        """
        self._host = host
        self._port = port
        self._enable_callback = enable_callback
        self._callbacks: list[LiveDataCallback] = []
        self._state_callbacks: list[ConnectionStateCallback] = []
        self._task: asyncio.Task | None = None
        self._live_data: PVSLiveData | None = None
        self._timestamp_format: str | None = None
        self._stopping = False
        self._state = ConnectionState.DISCONNECTED

    @property
    def live_data(self) -> PVSLiveData | None:
        """Return current live data."""
        return self._live_data

    @property
    def is_connected(self) -> bool:
        """Return True if websocket is connected and receiving data."""
        return self._state == ConnectionState.CONNECTED

    @property
    def state(self) -> ConnectionState:
        """Return current connection state."""
        return self._state

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify listeners."""
        if self._state != state:
            self._state = state
            for callback in list(self._state_callbacks):
                try:
                    callback(state)
                except Exception as e:
                    _LOGGER.error("Error in state callback: %s", e)

    def add_listener(self, callback: LiveDataCallback) -> Callable[[], None]:
        """Add a listener for live data updates.

        Returns a function to remove the listener.
        """
        self._callbacks.append(callback)

        def remove() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return remove

    def add_state_listener(
        self, callback: ConnectionStateCallback
    ) -> Callable[[], None]:
        """Add a listener for connection state changes.

        Returns a function to remove the listener.
        """
        self._state_callbacks.append(callback)

        def remove() -> None:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)

        return remove

    async def connect(self) -> None:
        """Start the WebSocket connection with auto-reconnect."""
        if self._task and not self._task.done():
            _LOGGER.debug("WebSocket already running")
            return

        self._stopping = False
        self._task = asyncio.create_task(self._run_websocket())

    async def disconnect(self) -> None:
        """Stop the WebSocket connection."""
        self._stopping = True

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        self._task = None
        self._live_data = None
        self._set_state(ConnectionState.DISCONNECTED)

    async def _run_websocket(self) -> None:
        """Run WebSocket connection loop with auto-reconnect."""
        # Strip port suffix from host if present (host should be bare IP/hostname)
        host = self._host.split(":")[0]
        websocket_url = f"ws://{host}:{self._port}"
        _LOGGER.info("Starting WebSocket connection to %s", websocket_url)

        reconnect_count = 0
        fast_retry_limit = 3
        fast_retry_delay = 2
        backoff_delay = 5.0
        max_backoff = 300
        stale_timeout = 180

        # Reuse session across reconnects
        session: aiohttp.ClientSession | None = None

        try:
            while not self._stopping:
                heartbeat_task = None
                last_message_time: float = 0

                try:
                    # Create session if needed
                    if session is None or session.closed:
                        session = aiohttp.ClientSession(
                            timeout=aiohttp.ClientTimeout(total=30, connect=10),
                            connector=aiohttp.TCPConnector(
                                limit=1,
                                limit_per_host=1,
                                ttl_dns_cache=300,
                                use_dns_cache=True,
                                enable_cleanup_closed=True,
                            ),
                        )

                    self._set_state(ConnectionState.CONNECTING)

                    # Ensure telemetry websocket is enabled on the PVS
                    if self._enable_callback is not None:
                        try:
                            await self._enable_callback()
                        except Exception as e:
                            _LOGGER.warning(
                                "Failed to enable telemetry websocket: %s", e
                            )

                    _LOGGER.info(
                        "Attempting WebSocket connection to %s (attempt %d)",
                        websocket_url,
                        reconnect_count + 1,
                    )

                    async with session.ws_connect(
                        websocket_url,
                        heartbeat=30,
                        compress=0,
                    ) as ws:
                        reconnect_count = 0
                        backoff_delay = 5.0
                        _LOGGER.info("WebSocket connected to %s", websocket_url)

                        # Initialize live data
                        self._live_data = PVSLiveData()
                        self._timestamp_format = None
                        last_message_time = time.monotonic()
                        self._set_state(ConnectionState.CONNECTED)

                        # Start heartbeat monitor
                        async def monitor_heartbeat() -> None:
                            nonlocal last_message_time
                            while True:
                                await asyncio.sleep(30)
                                elapsed = time.monotonic() - last_message_time
                                if elapsed > stale_timeout:
                                    _LOGGER.info(
                                        "WebSocket stale (no messages for %.0fs), closing and reconnecting",
                                        elapsed,
                                    )
                                    await ws.close()
                                    break

                        heartbeat_task = asyncio.create_task(monitor_heartbeat())

                        async for msg in ws:
                            last_message_time = time.monotonic()

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                    self._process_message(data)
                                except json.JSONDecodeError:
                                    _LOGGER.debug("Invalid JSON in WebSocket message")
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                _LOGGER.debug("WebSocket error (will reconnect): %s", ws.exception())
                                break
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.CLOSED,
                            ):
                                _LOGGER.info("WebSocket closed by server")
                                break

                except asyncio.CancelledError:
                    _LOGGER.debug("WebSocket cancelled")
                    raise
                except Exception as e:
                    reconnect_count += 1
                    _LOGGER.warning(
                        "WebSocket connection failed (attempt %d): %s",
                        reconnect_count,
                        e,
                    )
                finally:
                    if heartbeat_task and not heartbeat_task.done():
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass

                    self._live_data = None
                    self._set_state(ConnectionState.DISCONNECTED)

                if self._stopping:
                    break

                # Calculate retry delay
                if reconnect_count <= fast_retry_limit:
                    actual_delay = float(fast_retry_delay)
                    _LOGGER.info(
                        "Fast retry in %ds (attempt %d/%d)",
                        actual_delay,
                        reconnect_count,
                        fast_retry_limit,
                    )
                else:
                    delay = min(
                        backoff_delay
                        * (2 ** min(reconnect_count - fast_retry_limit - 1, 5)),
                        max_backoff,
                    )
                    jitter = random.uniform(0.8, 1.2)
                    actual_delay = delay * jitter
                    _LOGGER.info(
                        "Reconnecting in %.1fs (exponential backoff)", actual_delay
                    )
                    backoff_delay = min(backoff_delay * 1.5, max_backoff)

                try:
                    await asyncio.sleep(actual_delay)
                except asyncio.CancelledError:
                    _LOGGER.debug("WebSocket reconnection cancelled")
                    raise

        finally:
            # Clean up session on exit
            if session and not session.closed:
                await session.close()

    def _process_message(self, data: dict) -> None:
        """Process incoming WebSocket message."""
        if data.get("notification") != "power" or "params" not in data:
            return

        if self._live_data is None:
            return

        params = data["params"]
        changed_vars: set[str] = set()

        for ws_field, (var_path, attr_name, value_type) in _WS_FIELD_MAP.items():
            if ws_field not in params:
                continue

            new_value = self._convert_value(params[ws_field], value_type)
            old_value = getattr(self._live_data, attr_name, None)

            if old_value != new_value:
                setattr(self._live_data, attr_name, new_value)
                changed_vars.add(var_path)

        if changed_vars:
            # Iterate over a copy in case callbacks modify the list
            for callback in list(self._callbacks):
                try:
                    callback(changed_vars)
                except Exception as e:
                    _LOGGER.error("Error in live data callback: %s", e)

    def _convert_value(self, raw_value: Any, value_type: str) -> Any:
        """Convert raw WebSocket value to appropriate type."""
        if value_type == "string":
            return str(raw_value) if raw_value is not None else None

        if value_type == "numeric":
            return PVSLiveData._parse_numeric(raw_value)

        if value_type == "timestamp":
            return self._convert_timestamp(raw_value)

        return None

    def _convert_timestamp(self, raw_value: Any) -> Any:
        """Convert timestamp with format caching for websocket stream."""
        if raw_value is None:
            return None
        try:
            timestamp = int(raw_value)
            current_time = datetime.datetime.now(datetime.timezone.utc).timestamp()

            # Detect and cache timestamp format
            if self._timestamp_format == "milliseconds":
                timestamp = timestamp / 1000
            elif self._timestamp_format == "seconds":
                pass
            else:
                if timestamp > current_time + (365 * 24 * 3600):
                    self._timestamp_format = "milliseconds"
                    timestamp = timestamp / 1000
                else:
                    self._timestamp_format = "seconds"

            # Validate
            if timestamp < 0 or timestamp > current_time + (365 * 24 * 3600):
                return None

            return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        except (ValueError, TypeError, OSError):
            return None
