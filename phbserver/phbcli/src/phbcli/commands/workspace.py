"""Workspace management subcommands — thin CLI layer over workspace tools.

phbcli workspace list
phbcli workspace create <name> [--path P] [--set-default]
phbcli workspace remove <name> [--purge] [--yes]
phbcli workspace set-default <name>
phbcli workspace show [<name>]
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from phb_commons.process import is_running, read_pid
from rich.console import Console
from rich.table import Table

from ..tools.workspace import (
    WorkspaceCreateTool,
    WorkspaceListTool,
    WorkspaceRemoveTool,
    WorkspaceSetDefaultTool,
    WorkspaceShowTool,
)
from ..workspace import WorkspaceError


def register(workspace_app: typer.Typer, console: Console) -> None:
    """Register workspace management commands."""

    @workspace_app.command("list")
    def workspace_list() -> None:
        """List all configured workspaces."""
        result = WorkspaceListTool().execute()

        if not result.workspaces:
            console.print(
                "[dim]No workspaces configured. "
                "Run [bold]phbcli workspace create <name>[/bold] to get started.[/dim]"
            )
            return

        table = Table(title="Workspaces", show_header=True)
        table.add_column("", width=2, no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("HTTP")
        table.add_column("Path")

        for ws in result.workspaces:
            workspace_path = Path(ws["path"])
            pid = read_pid(workspace_path, "phbcli.pid")
            running = is_running(pid)

            default_marker = "[cyan]*[/cyan]" if ws["is_default"] else ""
            status = "[green]running[/green]" if running else "[dim]stopped[/dim]"
            http_str = f":{ws['http_port']}"
            table.add_row(default_marker, ws["name"], status, http_str, ws["path"])

        console.print(table)
        console.print("\n[cyan]*[/cyan] = default workspace")

    @workspace_app.command("create")
    def workspace_create(
        name: str = typer.Argument(..., help="Workspace name (e.g. 'default', 'work')"),
        path: Optional[str] = typer.Option(
            None, "--path", "-p",
            help="Custom folder path. Defaults to the platform data dir.",
        ),
        make_default: bool = typer.Option(
            False, "--set-default",
            help="Set this workspace as the default after creation.",
        ),
    ) -> None:
        """Create a new workspace."""
        try:
            result = WorkspaceCreateTool().execute(
                name=name,
                path=path,
                set_default=make_default,
            )
        except WorkspaceError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Workspace '[bold]{result.name}[/bold]' created.[/green]")
        console.print(f"  path         : [bold]{result.path}[/bold]")
        console.print(f"  http_port    : [bold]{result.http_port}[/bold]")
        console.print(f"  plugin_port  : [bold]{result.plugin_port}[/bold]")
        console.print(f"  gateway_port : [bold]{result.gateway_port}[/bold]  (external)")

        if result.is_default:
            console.print("  [cyan]Set as default workspace.[/cyan]")

        console.print(f"\nNext: [bold]phbcli setup --workspace {result.name}[/bold]")

    @workspace_app.command("remove")
    def workspace_remove(
        name: str = typer.Argument(..., help="Workspace name to remove"),
        purge: bool = typer.Option(
            False, "--purge",
            help="Also delete the workspace folder from disk.",
        ),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    ) -> None:
        """Remove a workspace from the registry."""
        if not yes:
            action = "remove and DELETE the folder of" if purge else "remove"
            typer.confirm(
                f"Are you sure you want to {action} workspace '{name}'?", abort=True
            )
        try:
            result = WorkspaceRemoveTool().execute(name=name, purge=purge)
        except WorkspaceError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Workspace '[bold]{result.name}[/bold]' removed.[/green]")
        if result.purged:
            console.print("  Workspace folder deleted from disk.")

    @workspace_app.command("set-default")
    def workspace_set_default(
        name: str = typer.Argument(..., help="Workspace name to set as default"),
    ) -> None:
        """Set the default workspace used when --workspace is not specified."""
        try:
            result = WorkspaceSetDefaultTool().execute(name=name)
        except WorkspaceError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        console.print(
            f"[green]Default workspace set to '[bold]{result.name}[/bold]'.[/green]"
        )

    @workspace_app.command("show")
    def workspace_show(
        name: Optional[str] = typer.Argument(
            None, help="Workspace name (omit to show the default)"
        ),
    ) -> None:
        """Show details of a workspace."""
        try:
            result = WorkspaceShowTool().execute(name=name)
        except WorkspaceError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

        workspace_path = Path(result.path)
        pid = read_pid(workspace_path, "phbcli.pid")
        running = is_running(pid)

        table = Table(
            title=f"Workspace: {result.name}",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("Name", result.name)
        table.add_row("Path", result.path)
        table.add_row("Default", "[cyan]yes[/cyan]" if result.is_default else "no")
        table.add_row(
            "Server",
            f"[green]running[/green] (PID {pid})" if running else "[dim]stopped[/dim]",
        )
        table.add_row("HTTP port", str(result.http_port))
        table.add_row("Plugin port", str(result.plugin_port))
        table.add_row("Gateway port", str(result.gateway_port))
        table.add_row("Gateway", "[dim]external (not managed by phbcli)[/dim]")
        table.add_row("Port slot", str(result.port_slot))

        console.print(table)
