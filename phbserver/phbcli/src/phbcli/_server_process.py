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
    from phbcli.process import write_pid
    from phbcli.server import run_http_server
    from phbcli.ws_client import run_ws_client

    config = load_config()
    stop_event = asyncio.Event()
    write_pid()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    if sys.platform == "win32":
        # CTRL_BREAK_EVENT is the closest Windows equivalent to SIGTERM
        signal.signal(signal.SIGBREAK, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "Starting phbcli server. HTTP: http://%s:%d/status  device_id: %s",
        config.http_host,
        config.http_port,
        config.device_id,
    )

    await asyncio.gather(
        run_http_server(config, stop_event),
        run_ws_client(config, stop_event),
    )

    mark_disconnected()
    logger.info("phbcli server exited.")


if __name__ == "__main__":
    asyncio.run(_main())
