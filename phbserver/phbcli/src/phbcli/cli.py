"""Typer CLI entrypoint for phbcli.

Commands:
  setup   — one-time interactive configuration, register auto-start, then start
  start   — start the background server
  stop    — stop the running server
  status  — show server + WS connection status
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import typer
from rich.console import Console
from rich.table import Table

from .autostart import (
    register_autostart,
    register_autostart_elevated,
    unregister_autostart,
    unregister_autostart_elevated,
)
from .config import (
    APP_DIR,
    Config,
    load_config,
    load_state,
    save_config,
)
from .process import is_running, read_pid, remove_pid, stop_server, write_pid
from .server import run_http_server
from .ws_client import run_ws_client

app = typer.Typer(
    name="phbcli",
    help="Private Home Box — desktop server CLI.",
    add_completion=False,
)
console = Console()


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

@app.command()
def setup(
    gateway_url: str = typer.Option(
        None, "--gateway-url", "-g", help="WebSocket gateway URL (e.g. ws://myhost:8765)"
    ),
    http_port: int = typer.Option(18080, "--port", "-p", help="Local HTTP server port"),
    skip_autostart: bool = typer.Option(False, "--skip-autostart", help="Do not register auto-start"),
    elevated_task: bool = typer.Option(
        False,
        "--elevated-task",
        help="(Windows) Request UAC elevation to create a high-privilege Task Scheduler entry.",
    ),
) -> None:
    """One-time setup: configure gateway, generate device ID, register auto-start."""
    console.print("[bold cyan]phbcli setup[/bold cyan]")

    existing = load_config()

    if gateway_url is None:
        gateway_url = typer.prompt(
            "Gateway WebSocket URL",
            default=existing.gateway_url,
        )

    config = Config(
        device_id=existing.device_id,  # preserve existing device_id
        gateway_url=gateway_url,
        http_host=existing.http_host,
        http_port=http_port,
    )
    save_config(config)
    console.print(f"[green]Config saved to[/green] {APP_DIR / 'config.json'}")
    console.print(f"  device_id  : [bold]{config.device_id}[/bold]")
    console.print(f"  gateway_url: [bold]{config.gateway_url}[/bold]")
    console.print(f"  http_port  : [bold]{config.http_port}[/bold]")

    if not skip_autostart:
        _register_autostart_with_feedback(elevated=elevated_task)

    console.print("\nStarting server…")
    _do_start(config)


def _register_autostart_with_feedback(*, elevated: bool = False) -> None:
    """Register auto-start and print a user-friendly summary of the outcome."""
    import sys

    if elevated and sys.platform == "win32":
        console.print(
            "[dim]Requesting UAC elevation to create a high-privilege task…[/dim]"
        )
        try:
            accepted = register_autostart_elevated()
        except RuntimeError as exc:
            console.print(f"[yellow]Elevated task creation failed: {exc}[/yellow]")
            accepted = False

        if accepted:
            console.print(
                "[green]Auto-start registered[/green] via Task Scheduler "
                "(elevated, run-level: HIGHEST)."
            )
        else:
            console.print(
                "[yellow]UAC prompt was cancelled or failed. "
                "Falling back to standard auto-start…[/yellow]"
            )
            _register_autostart_standard()
    else:
        _register_autostart_standard()


def _register_autostart_standard() -> None:
    """Try schtasks (LIMITED), fall back to registry, report the method used."""
    try:
        method = register_autostart()
    except NotImplementedError as exc:
        console.print(f"[yellow]Auto-start skipped: {exc}[/yellow]")
        return
    except Exception as exc:
        console.print(f"[yellow]Auto-start registration failed: {exc}[/yellow]")
        return

    if method == "schtasks":
        console.print(
            "[green]Auto-start registered[/green] via Task Scheduler "
            "(run-level: LIMITED, no elevation needed)."
        )
    elif method == "registry":
        console.print(
            "[green]Auto-start registered[/green] via Registry Run key "
            "[dim](Task Scheduler was unavailable — registry fallback used)[/dim]."
        )
    else:
        console.print("[yellow]Auto-start method unknown.[/yellow]")


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

@app.command()
def start() -> None:
    """Start the phbcli server in the background."""
    config = load_config()
    if not (APP_DIR / "config.json").exists():
        console.print(
            "[red]Not configured. Run [bold]phbcli setup[/bold] first.[/red]"
        )
        raise typer.Exit(1)
    _do_start(config)


def _do_start(config: Config) -> None:
    pid = read_pid()
    if pid and is_running(pid):
        console.print(f"[yellow]Server already running (PID {pid}).[/yellow]")
        return

    # Spawn a detached child process that runs the server loop
    python = sys.executable
    script = str(Path(__file__).parent / "_server_process.py")
    if sys.platform == "win32":
        proc = subprocess.Popen(
            [python, script],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            [python, script],
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    write_pid(proc.pid)
    console.print(
        f"[green]Server started[/green] (PID {proc.pid}). "
        f"HTTP: http://{config.http_host}:{config.http_port}/status"
    )


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

@app.command()
def stop() -> None:
    """Stop the running phbcli server."""
    pid = read_pid()
    if pid is None or not is_running(pid):
        console.print("[yellow]Server is not running.[/yellow]")
        remove_pid()
        return
    stopped = stop_server()
    if stopped:
        console.print(f"[green]Server stopped[/green] (was PID {pid}).")
    else:
        console.print("[red]Failed to stop server.[/red]")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show server and WebSocket connection status."""
    pid = read_pid()
    running = is_running(pid)
    state = load_state()
    config = load_config()

    table = Table(title="phbcli status", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Server running", "[green]yes[/green]" if running else "[red]no[/red]")
    table.add_row("PID", str(pid) if pid else "—")
    table.add_row(
        "WS connected",
        "[green]yes[/green]" if state.ws_connected else "[red]no[/red]",
    )
    table.add_row("Last connected", state.last_connected or "—")
    table.add_row("Gateway URL", state.gateway_url or config.gateway_url or "—")
    table.add_row("Device ID", config.device_id)
    table.add_row(
        "HTTP API",
        f"http://{config.http_host}:{config.http_port}/status" if running else "—",
    )

    console.print(table)


# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------

@app.command()
def teardown(
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Also delete the ~/.phbcli/ app directory (config, state, PID file).",
    ),
    elevated_task: bool = typer.Option(
        False,
        "--elevated-task",
        help="(Windows) Request UAC elevation to delete a high-privilege Task Scheduler entry.",
    ),
) -> None:
    """Stop the server and remove all auto-start registrations.

    Use --purge to also delete the ~/.phbcli/ app directory.
    Use --elevated-task if the task was originally created with --elevated-task.
    """
    console.print("[bold cyan]phbcli teardown[/bold cyan]")

    # 1. Stop the server if running
    pid = read_pid()
    if pid and is_running(pid):
        stopped = stop_server()
        if stopped:
            console.print(f"[green]Server stopped[/green] (was PID {pid}).")
        else:
            console.print("[yellow]Could not stop server — continuing teardown.[/yellow]")
    else:
        console.print("[dim]Server was not running.[/dim]")
        remove_pid()

    # 2. Unregister auto-start
    _unregister_autostart_with_feedback(elevated=elevated_task)

    # 3. Optionally purge app directory
    if purge:
        import shutil as _shutil
        if APP_DIR.exists():
            _shutil.rmtree(APP_DIR, ignore_errors=True)
            console.print(f"[green]App directory removed:[/green] {APP_DIR}")
        else:
            console.print(f"[dim]App directory not found (already clean): {APP_DIR}[/dim]")

    console.print("\n[green]Teardown complete.[/green]")


def _unregister_autostart_with_feedback(*, elevated: bool = False) -> None:
    if elevated and sys.platform == "win32":
        console.print(
            "[dim]Requesting UAC elevation to delete high-privilege task…[/dim]"
        )
        try:
            accepted = unregister_autostart_elevated()
        except RuntimeError as exc:
            console.print(f"[yellow]Elevated teardown failed: {exc}[/yellow]")
            accepted = False

        if accepted:
            console.print(
                "[green]Auto-start removed[/green] via elevated Task Scheduler delete."
            )
        else:
            console.print(
                "[yellow]UAC prompt was cancelled. "
                "Falling back to standard unregister…[/yellow]"
            )
            _unregister_autostart_standard()
    else:
        _unregister_autostart_standard()


def _unregister_autostart_standard() -> None:
    try:
        unregister_autostart()
        console.print("[green]Auto-start removed[/green] (Task Scheduler + Registry).")
    except NotImplementedError as exc:
        console.print(f"[yellow]Auto-start removal skipped: {exc}[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]Auto-start removal failed: {exc}[/yellow]")


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

@app.command()
def uninstall(
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Also delete the ~/.phbcli/ app directory.",
    ),
    elevated_task: bool = typer.Option(
        False,
        "--elevated-task",
        help="(Windows) Request UAC elevation to delete a high-privilege Task Scheduler entry.",
    ),
) -> None:
    """Stop server, remove auto-start, then print the command to uninstall the package.

    Runs teardown first, then tells you how to remove the phbcli package itself.
    The package cannot uninstall itself from within, so the final step is manual.
    """
    # Delegate to teardown logic
    ctx = click.get_current_context()
    ctx.invoke(teardown, purge=purge, elevated_task=elevated_task)

    console.print(
        "\n[bold]To fully remove phbcli, run one of:[/bold]\n"
        "  [cyan]uv tool uninstall phbcli[/cyan]       (if installed via uv tool)\n"
        "  [cyan]pip uninstall phbcli[/cyan]            (if installed via pip)\n"
    )


if __name__ == "__main__":
    app()
