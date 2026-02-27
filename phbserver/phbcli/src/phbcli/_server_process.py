"""Entry point for the detached server process spawned by `phbcli start`.

Runs both the FastAPI HTTP server and the WebSocket client concurrently
inside a single asyncio event loop.  Handles SIGTERM / SIGBREAK for
clean shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("phbcli.server_process")


async def _main() -> None:
    from phbcli.config import load_config, mark_disconnected
    from phbcli.plugin_manager import PluginManager
    from phbcli.process import write_pid
    from phbcli.server import run_http_server, set_channel_info_provider
    from phbcli.ws_client import run_ws_client

    config = load_config()
    stop_event = asyncio.Event()
    write_pid()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _shutdown)

    plugin_manager = PluginManager(config, stop_event)
    set_channel_info_provider(plugin_manager.get_channel_info)

    logger.info(
        "Starting phbcli server. HTTP: http://%s:%d/status  "
        "plugin WS: ws://127.0.0.1:%d  device_id: %s",
        config.http_host,
        config.http_port,
        config.plugin_port,
        config.device_id,
    )

    await asyncio.gather(
        run_http_server(config, stop_event),
        run_ws_client(config, stop_event),
        plugin_manager.run(),
    )

    mark_disconnected()
    logger.info("phbcli server exited.")


if __name__ == "__main__":
    asyncio.run(_main())
