"""Device connection registry and message relay logic.

A device connects with ?device_id=<id>.
Messages are JSON objects with an optional `target_device_id` field:
  - Present  → unicast to that specific device
  - Absent   → broadcast to all OTHER connected devices

Message envelope:
{
    "target_device_id": "<uuid>",   # optional
    "sender_device_id": "<uuid>",   # injected by gateway
    "payload": { ... }              # arbitrary application data
}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.asyncio.server import ServerConnection

logger = logging.getLogger(__name__)

# device_id -> websocket
_registry: Dict[str, ServerConnection] = {}
_registry_lock = asyncio.Lock()


def _extract_device_id(path: str) -> str | None:
    qs = parse_qs(urlparse(path).query)
    ids = qs.get("device_id", [])
    return ids[0] if ids else None


async def register(device_id: str, ws: ServerConnection) -> None:
    async with _registry_lock:
        if device_id in _registry:
            logger.warning("Device %s reconnected — replacing old connection.", device_id)
            old_ws = _registry[device_id]
            try:
                await old_ws.close(code=4000, reason="replaced by new connection")
            except Exception:
                pass
        _registry[device_id] = ws
        logger.info("Device registered: %s (total=%d)", device_id, len(_registry))


async def unregister(device_id: str) -> None:
    async with _registry_lock:
        _registry.pop(device_id, None)
        logger.info("Device unregistered: %s (total=%d)", device_id, len(_registry))


async def relay_message(sender_id: str, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Non-JSON message from %s — ignored.", sender_id)
        return

    msg["sender_device_id"] = sender_id
    target_id: str | None = msg.get("target_device_id")
    out = json.dumps(msg)

    async with _registry_lock:
        if target_id:
            target_ws = _registry.get(target_id)
            if target_ws is None:
                logger.warning(
                    "Target device %s not connected. Message from %s dropped.",
                    target_id,
                    sender_id,
                )
                return
            recipients = [(target_id, target_ws)]
        else:
            recipients = [
                (did, ws) for did, ws in _registry.items() if did != sender_id
            ]

    for did, ws in recipients:
        try:
            await ws.send(out)
            logger.debug("Relayed message from %s → %s", sender_id, did)
        except Exception as exc:
            logger.warning("Failed to send to %s: %s", did, exc)


def _request_path(ws: ServerConnection) -> str:
    # websockets < 15 exposed `ws.path`; newer versions expose `ws.request.path`.
    path = getattr(ws, "path", None)
    if isinstance(path, str):
        return path
    request = getattr(ws, "request", None)
    req_path = getattr(request, "path", None)
    return req_path if isinstance(req_path, str) else ""


async def handle_connection(ws: ServerConnection) -> None:
    """Handle a single WebSocket connection lifetime."""
    device_id = _extract_device_id(_request_path(ws))
    if not device_id:
        logger.warning("Connection rejected: missing device_id query param.")
        await ws.close(code=4001, reason="missing device_id")
        return

    await register(device_id, ws)
    try:
        async for message in ws:
            await relay_message(device_id, message)
    except websockets.ConnectionClosed:
        pass
    finally:
        await unregister(device_id)


def get_connected_devices() -> list[str]:
    return list(_registry.keys())
