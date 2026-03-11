"""Dashboard page — the landing page for the admin UI.

Assembles aggregate statistics by calling tools in-process on page load.
No real-time push: the user navigates back or refreshes to see updated counts.

Statistics shown:
  - Total workspaces        (WorkspaceListTool)
  - Running workspaces      (StatusTool)
  - Gateway connected       (StatusTool — ws_connected)
  - Total paired devices    (DeviceListTool per workspace)
  - Installed channels      (ChannelListTool per workspace)
  - Enabled channels        (ChannelListTool — filtered)
"""

from __future__ import annotations

from nicegui import ui


@ui.page("/")
async def dashboard_page() -> None:
    from phbcli.tools.channel import ChannelListTool
    from phbcli.tools.device import DeviceListTool
    from phbcli.tools.server import StatusTool
    from phbcli.tools.workspace import WorkspaceListTool
    from phbcli.ui.app import create_page_layout

    # ------------------------------------------------------------------ data
    workspaces: list[dict] = []
    total_workspaces = 0
    running_workspaces = 0
    gateway_connected = False
    total_devices = 0
    total_channels = 0
    enabled_channels = 0

    try:
        ws_result = WorkspaceListTool().execute()
        workspaces = ws_result.workspaces
        total_workspaces = len(workspaces)
    except Exception:
        pass

    try:
        status_result = StatusTool().execute()
        running_workspaces = sum(1 for w in status_result.workspaces if w.server_running)
        gateway_connected = any(w.ws_connected for w in status_result.workspaces)
    except Exception:
        pass

    for ws in workspaces:
        ws_name: str | None = ws.get("name")
        try:
            devices = DeviceListTool().execute(workspace=ws_name)
            total_devices += len(devices.devices)
        except Exception:
            pass
        try:
            channels = ChannelListTool().execute(workspace=ws_name)
            total_channels += len(channels.channels)
            enabled_channels += sum(1 for c in channels.channels if c.get("enabled"))
        except Exception:
            pass

    # ------------------------------------------------------------------ layout
    create_page_layout(active_path="/")

    with ui.column().classes("w-full gap-6 p-6"):
        ui.label("Dashboard").classes("text-2xl font-semibold")

        with ui.grid(columns=3).classes("w-full gap-4"):
            _stat_card("Total workspaces", str(total_workspaces), "workspaces")
            _stat_card("Running workspaces", str(running_workspaces), "activity")
            _stat_card(
                "Gateway",
                "Connected" if gateway_connected else "Disconnected",
                "wifi" if gateway_connected else "wifi_off",
                ok=gateway_connected,
            )
            _stat_card("Paired devices", str(total_devices), "smartphone")
            _stat_card("Installed channels", str(total_channels), "extension")
            _stat_card("Enabled channels", str(enabled_channels), "check_circle")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stat_card(title: str, value: str, icon: str, *, ok: bool | None = None) -> None:
    # Use Quasar semantic color roles so values adapt to dark/light theme automatically.
    value_classes = "text-2xl font-bold"
    if ok is True:
        value_classes += " text-positive"
    elif ok is False:
        value_classes += " text-negative"

    with ui.card().classes("w-full"):
        with ui.row().classes("items-start gap-3 p-1"):
            # opacity-50 on inherited color adapts to both themes instead of a fixed gray
            ui.icon(icon).classes("text-3xl opacity-50 mt-1")
            with ui.column().classes("gap-0"):
                ui.label(value).classes(value_classes)
                ui.label(title).classes("text-sm opacity-60")
