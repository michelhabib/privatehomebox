"""Admin UI coroutine — started alongside the HTTP server when --admin is set.

Uses `ui.run_with()` to mount NiceGUI onto a dedicated FastAPI app, then
serves that app with Uvicorn in the same event loop — identical to how
`run_http_server` works.  No extra thread or event loop required.
"""

from __future__ import annotations

import asyncio

import uvicorn
from fastapi import FastAPI
from phb_commons.log import Logger

from phbcli.domain.config import Config

log = Logger.get("ADMIN")


async def run_admin_ui(config: Config, stop_event: asyncio.Event) -> None:
    """Start the NiceGUI admin UI and shut it down when stop_event fires."""
    from nicegui import ui

    from phbcli.ui.app import register_pages

    register_pages()

    # Dedicated FastAPI app so NiceGUI gets its own port, separate from the
    # HTTP API.  ui.run_with() sets has_run_config and mounts NiceGUI's
    # routes/static assets onto this app.
    # Note: run_with() hardcodes reload=False internally — do not pass it.
    admin_app = FastAPI(title="PHB Admin")
    # storage_secret enables app.storage.user (per-browser persistent storage)
    # used for the dark mode preference. Derived from the device ID so it is
    # stable across server restarts without needing an extra config field.
    ui.run_with(
        admin_app,
        title="PHB Admin",
        show_welcome_message=False,
        storage_secret=f"phb-admin-{config.device_id}",
    )

    log.info("Admin UI starting", url=f"http://127.0.0.1:{config.admin_port}")

    uv_config = uvicorn.Config(
        app=admin_app,
        host="127.0.0.1",
        port=config.admin_port,
        log_level="warning",
        loop="none",
    )
    server = uvicorn.Server(uv_config)

    serve_task = asyncio.create_task(server.serve())
    stop_task = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait(
        [serve_task, stop_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_task in done:
        server.should_exit = True
        await serve_task

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    log.info("Admin UI stopped")
