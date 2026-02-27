"""PluginManager — phbcli-side orchestrator for channel plugins.

Responsibilities:
  - Runs a local WebSocket server on plugin_port (default 18081).
  - Spawns a subprocess for each enabled channel on startup.
  - Accepts JSON-RPC connections from channel plugins.
  - Dispatches incoming channel.receive / channel.event notifications.
  - Routes channel.send / channel.configure / channel.status to plugins.
  - Terminates subprocesses on shutdown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from .channel_config import ChannelConfig, list_enabled_channels
from .config import Config
from . import rpc_helpers as rpc

logger = logging.getLogger(__name__)


@dataclass
class _ConnectedChannel:
    name: str
    version: str
    description: str
    ws: ServerConnection
    # Pending RPC requests keyed by request id
    pending: dict[str, asyncio.Future[Any]] = field(default_factory=dict)


class PluginManager:
    """Manages the lifecycle of channel plugins as subprocesses."""

    def __init__(
        self,
        config: Config,
        stop_event: asyncio.Event,
        on_message: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._stop_event = stop_event
        self._on_message = on_message
        self._channels: dict[str, _ConnectedChannel] = {}
        self._subprocesses: list[subprocess.Popen[bytes]] = []
        self._host = "127.0.0.1"
        self._port = config.plugin_port

    # ------------------------------------------------------------------
    # Main coroutine
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the plugin WS server and spawn enabled channel subprocesses."""
        async with websockets.serve(
            self._handle_connection, self._host, self._port
        ):
            logger.info(
                "Plugin server listening on ws://%s:%d", self._host, self._port
            )
            await self._spawn_channels()
            await self._stop_event.wait()
            await self._shutdown_channels()

        logger.info("Plugin server stopped.")

    # ------------------------------------------------------------------
    # Subprocess management
    # ------------------------------------------------------------------

    async def _spawn_channels(self) -> None:
        channels = list_enabled_channels()
        if not channels:
            logger.info("No enabled channel plugins configured.")
            return

        phb_ws = f"ws://{self._host}:{self._port}"
        for ch in channels:
            await self._spawn_one(ch, phb_ws)

    async def _spawn_one(self, ch: ChannelConfig, phb_ws: str) -> None:
        cmd = ch.effective_command() + ["--phb-ws", phb_ws]
        logger.info("Spawning channel plugin: %s → %s", ch.name, cmd)
        try:
            if sys.platform == "win32":
                proc = subprocess.Popen(
                    cmd,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP
                        | subprocess.CREATE_NO_WINDOW
                    ),
                    close_fds=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    close_fds=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            self._subprocesses.append(proc)
        except FileNotFoundError:
            logger.error(
                "Channel command not found: %s. "
                "Install it with: phbcli channel install %s",
                cmd[0],
                ch.name,
            )
        except Exception as exc:
            logger.error("Failed to spawn channel '%s': %s", ch.name, exc)

    async def _shutdown_channels(self) -> None:
        # Ask each connected plugin to stop gracefully
        for ch in list(self._channels.values()):
            try:
                await ch.ws.send(rpc.build_notification("channel.stop", {}))
            except Exception:
                pass

        # Give plugins a moment to shut down, then terminate
        await asyncio.sleep(1)
        for proc in self._subprocesses:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # WebSocket connection handler
    # ------------------------------------------------------------------

    async def _handle_connection(self, ws: ServerConnection) -> None:
        channel_name: str | None = None
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from plugin: %.200s", raw)
                    continue

                if "method" not in data:
                    # This is a response to one of our requests
                    await self._handle_response(channel_name, data)
                    continue

                method: str = data["method"]
                params: dict[str, Any] = data.get("params", {})
                req_id: Any = data.get("id")

                match method:
                    case "channel.register":
                        channel_name = params["name"]
                        self._channels[channel_name] = _ConnectedChannel(
                            name=channel_name,
                            version=params.get("version", "?"),
                            description=params.get("description", ""),
                            ws=ws,
                        )
                        logger.info(
                            "Channel registered: %s v%s",
                            channel_name,
                            params.get("version", "?"),
                        )
                        # Push stored config immediately after registration
                        await self._push_config(channel_name)

                    case "channel.receive":
                        if self._on_message:
                            try:
                                await self._on_message(params)
                            except Exception as exc:
                                logger.exception(
                                    "on_message handler error for '%s': %s",
                                    channel_name,
                                    exc,
                                )

                    case "channel.event":
                        logger.info(
                            "[%s] event=%s data=%s",
                            channel_name or "?",
                            params.get("event"),
                            params.get("data"),
                        )

                    case _:
                        logger.warning(
                            "Unknown method from channel '%s': %s",
                            channel_name or "?",
                            method,
                        )
                        if req_id is not None:
                            await ws.send(
                                rpc.build_error(
                                    -32601,
                                    f"Method not found: {method}",
                                    req_id,
                                )
                            )

        except ConnectionClosed:
            pass
        except Exception as exc:
            logger.error(
                "Error in plugin connection (%s): %s", channel_name or "?", exc
            )
        finally:
            if channel_name and channel_name in self._channels:
                del self._channels[channel_name]
                logger.info("Channel disconnected: %s", channel_name)

    async def _handle_response(
        self, channel_name: str | None, data: dict[str, Any]
    ) -> None:
        if channel_name is None:
            return
        ch = self._channels.get(channel_name)
        if ch is None:
            return
        resp_id = str(data.get("id", ""))
        fut = ch.pending.pop(resp_id, None)
        if fut and not fut.done():
            if data.get("error"):
                fut.set_exception(RuntimeError(data["error"]["message"]))
            else:
                fut.set_result(data.get("result"))

    async def _push_config(self, channel_name: str) -> None:
        from .channel_config import load_channel_config

        cfg = load_channel_config(channel_name)
        if cfg and cfg.config:
            await self.configure_channel(channel_name, cfg.config)

    # ------------------------------------------------------------------
    # Outbound API (phbcli → plugin)
    # ------------------------------------------------------------------

    async def send_to_channel(
        self, channel_name: str, message: dict[str, Any]
    ) -> None:
        """Send a channel.send notification to a specific plugin."""
        ch = self._channels.get(channel_name)
        if ch is None:
            logger.warning(
                "Cannot send to channel '%s': not connected.", channel_name
            )
            return
        await ch.ws.send(rpc.build_notification("channel.send", message))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a channel.send notification to all connected plugins."""
        for ch in list(self._channels.values()):
            try:
                await ch.ws.send(rpc.build_notification("channel.send", message))
            except Exception as exc:
                logger.warning(
                    "Failed to send to channel '%s': %s", ch.name, exc
                )

    async def configure_channel(
        self, channel_name: str, config: dict[str, Any]
    ) -> None:
        """Push credentials/config to a specific plugin."""
        ch = self._channels.get(channel_name)
        if ch is None:
            return
        await ch.ws.send(
            rpc.build_notification("channel.configure", {"config": config})
        )

    async def probe_channel(self, channel_name: str) -> dict[str, Any] | None:
        """Send channel.status and await the response."""
        ch = self._channels.get(channel_name)
        if ch is None:
            return None
        from uuid import uuid4

        req_id = uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        ch.pending[req_id] = fut
        await ch.ws.send(rpc.build_request("channel.status", request_id=req_id))
        try:
            return await asyncio.wait_for(fut, timeout=5.0)
        except asyncio.TimeoutError:
            ch.pending.pop(req_id, None)
            return None

    def get_connected_channels(self) -> list[str]:
        return list(self._channels.keys())

    def get_channel_info(self) -> list[dict[str, str]]:
        return [
            {
                "name": ch.name,
                "version": ch.version,
                "description": ch.description,
            }
            for ch in self._channels.values()
        ]
