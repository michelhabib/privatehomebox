"""Server lifecycle tools: setup, start, stop, status, teardown.

These tools own the logic for managing the phbcli server process and
auto-start registrations.  CLI commands in commands/root.py are thin
wrappers that parse flags, call execute(), and render the result.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from phb_commons.keys import public_key_to_b64
from phb_commons.process import is_running, read_pid

from ..autostart import (
    register_autostart,
    register_autostart_elevated,
    unregister_autostart,
    unregister_autostart_elevated,
)
from ..config import Config, load_config, load_state, master_key_path, save_config
from ..crypto import load_or_create_master_key
from ..services.bootstrap import ensure_mandatory_devices_channel
from ..services.server_control import do_start, do_stop
from ..workspace import (
    WorkspaceError,
    WorkspaceRegistry,
    create_workspace,
    http_port_for,
    load_registry,
    plugin_port_for,
    remove_workspace,
    resolve_workspace,
)
from .base import Tool, ToolParam


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SetupResult:
    workspace: str
    workspace_path: str
    device_id: str
    gateway_url: str
    http_port: int
    master_key: str
    desktop_pub: str
    autostart_registered: bool
    autostart_method: str  # "schtasks" | "registry" | "elevated" | "skipped" | "failed"
    server_started: bool


@dataclass
class StartResult:
    workspace: str
    workspace_path: str
    already_running: bool
    pid: int | None
    http_host: str
    http_port: int


@dataclass
class StopResult:
    workspace: str
    was_running: bool
    pid: int | None


@dataclass
class WorkspaceStatusEntry:
    name: str
    is_default: bool
    server_running: bool
    pid: int | None
    ws_connected: bool
    last_connected: str | None
    gateway_url: str | None
    device_id: str
    http_host: str
    http_port: int


@dataclass
class StatusResult:
    workspaces: list[WorkspaceStatusEntry] = field(default_factory=list)


@dataclass
class TeardownResult:
    workspace: str
    workspace_path: str
    server_stopped: bool
    autostart_removed: bool
    purged: bool


@dataclass
class UninstallResult:
    teardown: TeardownResult


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_or_create(workspace: str | None) -> tuple[Any, WorkspaceRegistry, Path]:
    """Resolve a workspace entry, auto-creating 'default' if none exist."""
    try:
        entry, registry = resolve_workspace(workspace)
        return entry, registry, Path(entry.path)
    except WorkspaceError:
        if workspace is not None:
            raise
        entry, registry = create_workspace("default")
        return entry, registry, Path(entry.path)


def _register_autostart(workspace_name: str, elevated: bool) -> tuple[bool, str]:
    """Register auto-start and return (success, method_label)."""
    import sys

    if elevated and sys.platform == "win32":
        try:
            accepted = register_autostart_elevated(workspace_name)
        except RuntimeError:
            accepted = False
        if accepted:
            return True, "elevated"
        # fall through to standard
    try:
        method = register_autostart(workspace_name)
        return True, str(method)
    except (NotImplementedError, Exception):
        return False, "failed"


def _unregister_autostart(workspace_name: str, elevated: bool) -> bool:
    import sys

    if elevated and sys.platform == "win32":
        try:
            accepted = unregister_autostart_elevated(workspace_name)
        except RuntimeError:
            accepted = False
        if accepted:
            return True
    try:
        unregister_autostart(workspace_name)
        return True
    except (NotImplementedError, Exception):
        return False


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class SetupTool(Tool):
    name = "setup"
    description = (
        "One-time setup: save gateway config, generate device key, "
        "register auto-start, and start the server"
    )
    params = {
        "gateway_url": ToolParam(str, "WebSocket gateway URL, e.g. ws://myhost:8765"),
        "workspace": ToolParam(str, "Workspace name to configure", required=False),
        "http_port": ToolParam(int, "Local HTTP server port override", required=False),
        "skip_autostart": ToolParam(bool, "Do not register auto-start", required=False),
        "elevated_task": ToolParam(
            bool,
            "(Windows) Request UAC elevation for Task Scheduler entry",
            required=False,
        ),
    }

    def execute(
        self,
        gateway_url: str,
        workspace: str | None = None,
        http_port: int | None = None,
        skip_autostart: bool = False,
        elevated_task: bool = False,
    ) -> SetupResult:
        entry, registry, workspace_path = _resolve_or_create(workspace)
        existing = load_config(workspace_path)

        effective_http_port = http_port or http_port_for(registry, entry.port_slot)
        effective_plugin_port = plugin_port_for(registry, entry.port_slot)

        config = Config(
            device_id=existing.device_id,
            gateway_url=gateway_url,
            http_host=existing.http_host,
            http_port=effective_http_port,
            plugin_port=effective_plugin_port,
            master_key_file=existing.master_key_file,
            pairing_code_length=existing.pairing_code_length,
            pairing_code_ttl_seconds=existing.pairing_code_ttl_seconds,
            attestation_expires_days=existing.attestation_expires_days,
        )
        save_config(workspace_path, config)
        private_key = load_or_create_master_key(workspace_path, filename=config.master_key_file)
        public_key_b64 = public_key_to_b64(private_key.public_key())
        ensure_mandatory_devices_channel(workspace_path, config)

        autostart_registered = False
        autostart_method = "skipped"
        if not skip_autostart:
            autostart_registered, autostart_method = _register_autostart(
                entry.name, elevated_task
            )

        do_start(workspace_path, entry, registry, config, _NullConsole(), foreground=False)

        return SetupResult(
            workspace=entry.name,
            workspace_path=str(workspace_path),
            device_id=config.device_id,
            gateway_url=config.gateway_url,
            http_port=config.http_port,
            master_key=str(master_key_path(workspace_path, config)),
            desktop_pub=public_key_b64,
            autostart_registered=autostart_registered,
            autostart_method=autostart_method,
            server_started=True,
        )


class StartTool(Tool):
    name = "start"
    description = "Start the phbcli server for a workspace (background by default)"
    params = {
        "workspace": ToolParam(str, "Workspace name to start", required=False),
        "foreground": ToolParam(
            bool,
            "Run the server in the foreground with live log output",
            required=False,
        ),
    }

    def execute(
        self,
        workspace: str | None = None,
        foreground: bool = False,
    ) -> StartResult:
        entry, registry, workspace_path = _resolve_or_create(workspace)

        if not (workspace_path / "config.json").exists():
            raise ValueError(
                f"Workspace '{entry.name}' is not configured. "
                f"Run 'phbcli setup --workspace {entry.name}' first."
            )

        config = load_config(workspace_path)

        from ..constants import PID_FILENAME

        pid = read_pid(workspace_path, PID_FILENAME)
        if pid and is_running(pid):
            return StartResult(
                workspace=entry.name,
                workspace_path=str(workspace_path),
                already_running=True,
                pid=pid,
                http_host=config.http_host,
                http_port=config.http_port,
            )

        do_start(workspace_path, entry, registry, config, _NullConsole(), foreground=foreground)

        new_pid = read_pid(workspace_path, PID_FILENAME)
        return StartResult(
            workspace=entry.name,
            workspace_path=str(workspace_path),
            already_running=False,
            pid=new_pid,
            http_host=config.http_host,
            http_port=config.http_port,
        )


class StopTool(Tool):
    name = "stop"
    description = "Stop the running phbcli server for a workspace"
    params = {
        "workspace": ToolParam(str, "Workspace name to stop", required=False),
    }

    def execute(self, workspace: str | None = None) -> StopResult:
        entry, _, workspace_path = _resolve_or_create(workspace)

        from ..constants import PID_FILENAME

        pid = read_pid(workspace_path, PID_FILENAME)
        was_running = pid is not None and is_running(pid)

        do_stop(workspace_path, entry, _NullConsole())
        return StopResult(workspace=entry.name, was_running=was_running, pid=pid)


class StatusTool(Tool):
    name = "status"
    description = "Show server and WebSocket connection status for one or all workspaces"
    params = {
        "workspace": ToolParam(
            str,
            "Workspace name to query (omit to show all workspaces)",
            required=False,
        ),
    }

    def execute(self, workspace: str | None = None) -> StatusResult:
        registry = load_registry()

        if not registry.workspaces:
            return StatusResult(workspaces=[])

        names: list[str]
        if workspace is not None:
            if workspace not in registry.workspaces:
                raise WorkspaceError(f"Workspace '{workspace}' not found.")
            names = [workspace]
        else:
            names = list(registry.workspaces.keys())

        entries = []
        for name in names:
            ws_entry = registry.workspaces[name]
            ws_path = Path(ws_entry.path)
            pid = read_pid(ws_path, "phbcli.pid")
            running = is_running(pid)
            state = load_state(ws_path)
            config = load_config(ws_path)
            entries.append(
                WorkspaceStatusEntry(
                    name=name,
                    is_default=name == registry.default_workspace,
                    server_running=running,
                    pid=pid,
                    ws_connected=state.ws_connected,
                    last_connected=state.last_connected,
                    gateway_url=state.gateway_url or config.gateway_url or None,
                    device_id=config.device_id,
                    http_host=config.http_host,
                    http_port=config.http_port,
                )
            )
        return StatusResult(workspaces=entries)


class TeardownTool(Tool):
    name = "teardown"
    description = "Stop server and remove all auto-start registrations for a workspace"
    params = {
        "workspace": ToolParam(str, "Workspace name to tear down", required=False),
        "purge": ToolParam(
            bool,
            "Also delete the workspace folder (config, state, keys, logs…)",
            required=False,
        ),
        "elevated_task": ToolParam(
            bool,
            "(Windows) Request UAC elevation to delete a high-privilege Task Scheduler entry",
            required=False,
        ),
    }

    def execute(
        self,
        workspace: str | None = None,
        purge: bool = False,
        elevated_task: bool = False,
    ) -> TeardownResult:
        entry, registry, workspace_path = _resolve_or_create(workspace)

        do_stop(workspace_path, entry, _NullConsole())
        autostart_removed = _unregister_autostart(entry.name, elevated_task)

        if purge:
            if workspace_path.exists():
                shutil.rmtree(workspace_path, ignore_errors=True)
            try:
                remove_workspace(entry.name, purge=False)
            except WorkspaceError:
                pass

        return TeardownResult(
            workspace=entry.name,
            workspace_path=str(workspace_path),
            server_stopped=True,
            autostart_removed=autostart_removed,
            purged=purge,
        )


class UninstallTool(Tool):
    name = "uninstall"
    description = "Stop server, remove auto-start, and return package uninstall instructions"
    params = {
        "workspace": ToolParam(str, "Workspace name to uninstall", required=False),
        "purge": ToolParam(bool, "Also delete the workspace folder", required=False),
        "elevated_task": ToolParam(
            bool,
            "(Windows) Request UAC elevation to delete a high-privilege Task Scheduler entry",
            required=False,
        ),
    }

    def execute(
        self,
        workspace: str | None = None,
        purge: bool = False,
        elevated_task: bool = False,
    ) -> UninstallResult:
        teardown_result = TeardownTool().execute(
            workspace=workspace,
            purge=purge,
            elevated_task=elevated_task,
        )
        return UninstallResult(teardown=teardown_result)


# ---------------------------------------------------------------------------
# Internal: null console for do_start / do_stop (output handled by CLI layer)
# ---------------------------------------------------------------------------


class _NullConsole:
    """Drop-in for rich.Console that discards all output."""

    def print(self, *args: object, **kwargs: object) -> None:  # noqa: A003
        pass
