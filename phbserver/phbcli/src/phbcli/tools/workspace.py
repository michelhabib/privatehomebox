"""Workspace management tools.

Five operations: list, create, remove, set-default, show.
The CLI (commands/workspace.py) and the AI agent call these directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..domain.workspace import (
    WorkspaceError,
    create_workspace,
    gateway_port_for,
    http_port_for,
    load_registry,
    next_free_slot,
    plugin_port_for,
    remove_workspace,
    resolve_workspace,
    set_default_workspace,
)
from .base import Tool, ToolParam


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceListResult:
    workspaces: list[dict[str, Any]] = field(default_factory=list)
    default_workspace: str = ""


@dataclass
class WorkspaceCreateResult:
    name: str
    path: str
    http_port: int
    plugin_port: int
    gateway_port: int
    is_default: bool


@dataclass
class WorkspaceRemoveResult:
    name: str
    purged: bool


@dataclass
class WorkspaceSetDefaultResult:
    name: str


@dataclass
class WorkspaceShowResult:
    name: str
    path: str
    is_default: bool
    http_port: int
    plugin_port: int
    gateway_port: int
    port_slot: int


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class WorkspaceListTool(Tool):
    name = "workspace_list"
    description = "List all configured workspaces with their ports and status"
    params: dict = {}

    def execute(self) -> WorkspaceListResult:
        registry = load_registry()
        workspaces = []
        for ws_name, entry in registry.workspaces.items():
            workspaces.append({
                "name": ws_name,
                "path": entry.path,
                "is_default": ws_name == registry.default_workspace,
                "http_port": http_port_for(registry, entry.port_slot),
                "plugin_port": plugin_port_for(registry, entry.port_slot),
                "gateway_port": gateway_port_for(registry, entry.port_slot),
                "port_slot": entry.port_slot,
            })
        return WorkspaceListResult(
            workspaces=workspaces,
            default_workspace=registry.default_workspace,
        )


class WorkspaceCreateTool(Tool):
    name = "workspace_create"
    description = "Create a new workspace and register it with auto-assigned ports"
    params = {
        "name": ToolParam(str, "Workspace name, e.g. 'default' or 'work'"),
        "path": ToolParam(str, "Custom folder path (default: platform data dir)", required=False),
        "set_default": ToolParam(bool, "Set this workspace as the default after creation", required=False),
    }

    def execute(
        self,
        name: str,
        path: str | None = None,
        set_default: bool = False,
    ) -> WorkspaceCreateResult:
        custom_path = Path(path) if path else None
        entry, registry = create_workspace(name, path=custom_path)

        if set_default:
            set_default_workspace(name)
            registry = load_registry()

        return WorkspaceCreateResult(
            name=entry.name,
            path=entry.path,
            http_port=http_port_for(registry, entry.port_slot),
            plugin_port=plugin_port_for(registry, entry.port_slot),
            gateway_port=gateway_port_for(registry, entry.port_slot),
            is_default=entry.name == registry.default_workspace,
        )


class WorkspaceRemoveTool(Tool):
    name = "workspace_remove"
    description = "Remove a workspace from the registry, optionally deleting its folder from disk"
    params = {
        "name": ToolParam(str, "Workspace name to remove"),
        "purge": ToolParam(bool, "Also delete the workspace folder from disk", required=False),
    }

    def execute(self, name: str, purge: bool = False) -> WorkspaceRemoveResult:
        remove_workspace(name, purge=purge)
        return WorkspaceRemoveResult(name=name, purged=purge)


class WorkspaceSetDefaultTool(Tool):
    name = "workspace_set_default"
    description = "Set the default workspace used when --workspace is not specified"
    params = {
        "name": ToolParam(str, "Workspace name to set as default"),
    }

    def execute(self, name: str) -> WorkspaceSetDefaultResult:
        set_default_workspace(name)
        return WorkspaceSetDefaultResult(name=name)


class WorkspaceShowTool(Tool):
    name = "workspace_show"
    description = "Show details of a workspace: path, ports, and whether it is the default"
    params = {
        "name": ToolParam(str, "Workspace name (omit to show the default workspace)", required=False),
    }

    def execute(self, name: str | None = None) -> WorkspaceShowResult:
        entry, registry = resolve_workspace(name)
        return WorkspaceShowResult(
            name=entry.name,
            path=entry.path,
            is_default=entry.name == registry.default_workspace,
            http_port=http_port_for(registry, entry.port_slot),
            plugin_port=plugin_port_for(registry, entry.port_slot),
            gateway_port=gateway_port_for(registry, entry.port_slot),
            port_slot=entry.port_slot,
        )
