"""WebSocket client that connects phbcli to the gateway.

Features:
- Connects with ?device_id=<id> query parameter
- Sends a ping every PING_INTERVAL seconds (keepalive)
- On disconnect: exponential backoff reconnect (1s → 2s → 4s … capped at 60s)
- Updates state.json on connect / disconnect
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode, urlparse, urlunparse

import websockets
from websockets.exceptions import ConnectionClosed

from .config import Config, mark_connected, mark_disconnected

logger = logging.getLogger(__name__)

PING_INTERVAL = 30  # seconds
BACKOFF_BASE = 1.0
BACKOFF_MAX = 60.0


def _build_url(gateway_url: str, device_id: str) -> str:
    parsed = urlparse(gateway_url)
    qs = urlencode({"device_id": device_id})
    # Append to any existing query string
    full_qs = f"{parsed.query}&{qs}" if parsed.query else qs
    return urlunparse(parsed._replace(query=full_qs))


async def _handle_messages(ws: websockets.WebSocketClientProtocol) -> None:
    """Consume incoming messages (extend here to handle commands from gateway)."""
    async for message in ws:
        logger.debug("Gateway message: %s", message)


async def _run_connection(url: str, config: Config, stop_event: asyncio.Event) -> None:
    logger.info("Connecting to gateway: %s", url)
    async with websockets.connect(url, ping_interval=None) as ws:
        mark_connected(config.gateway_url)
        logger.info("Connected to gateway (device_id=%s)", config.device_id)

        ping_task = asyncio.create_task(_ping_loop(ws, stop_event))
        recv_task = asyncio.create_task(_handle_messages(ws))
        stop_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            [ping_task, recv_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, ConnectionClosed):
                pass


async def _ping_loop(ws: websockets.WebSocketClientProtocol, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(ws.ping(), timeout=10)
            logger.debug("Ping sent")
        except (ConnectionClosed, asyncio.TimeoutError):
            break
        await asyncio.sleep(PING_INTERVAL)


async def run_ws_client(config: Config, stop_event: asyncio.Event) -> None:
    """Main WS client loop with exponential backoff reconnect."""
    url = _build_url(config.gateway_url, config.device_id)
    backoff = BACKOFF_BASE

    while not stop_event.is_set():
        try:
            await _run_connection(url, config, stop_event)
            # Clean disconnect (stop requested)
            if stop_event.is_set():
                break
            # Unexpected disconnect — reconnect
            logger.warning("Disconnected from gateway. Reconnecting in %.0fs…", backoff)
        except (OSError, ConnectionClosed, websockets.InvalidURI, websockets.WebSocketException) as exc:
            logger.warning("WS error: %s. Reconnecting in %.0fs…", exc, backoff)
        finally:
            mark_disconnected()

        if stop_event.is_set():
            break

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=backoff)
        except asyncio.TimeoutError:
            pass

        backoff = min(backoff * 2, BACKOFF_MAX)

    mark_disconnected()
    logger.info("WS client stopped.")
