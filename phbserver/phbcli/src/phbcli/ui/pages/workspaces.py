"""Workspaces page — list, create, remove, and set default workspace.

Actions:
  - Create:      name + optional path → WorkspaceCreateTool
  - Remove:      confirmation dialog + optional purge → WorkspaceRemoveTool
  - Set default: per-row button → WorkspaceSetDefaultTool
"""

from __future__ import annotations

from nicegui import ui


@ui.page("/workspaces")
async def workspaces_page() -> None:
    from phbcli.tools.server import StatusTool
    from phbcli.tools.workspace import (
        WorkspaceCreateTool,
        WorkspaceListTool,
        WorkspaceRemoveTool,
        WorkspaceSetDefaultTool,
    )
    from phbcli.ui.app import create_page_layout

    create_page_layout(active_path="/workspaces")

    # Mutable container so inner async callbacks can update it
    pending_remove: list[dict] = [{}]

    # ------------------------------------------------------------------ create dialog
    with ui.dialog() as create_dialog, ui.card().classes("w-96"):
        ui.label("Create workspace").classes("text-lg font-semibold mb-2")
        name_input = ui.input("Name", placeholder="e.g. work").classes("w-full")
        path_input = ui.input(
            "Path (optional)",
            placeholder="Leave blank for default location",
        ).classes("w-full")

        async def do_create() -> None:
            name = name_input.value.strip()
            if not name:
                ui.notify("Name is required.", color="negative")
                return
            path = path_input.value.strip() or None
            try:
                WorkspaceCreateTool().execute(name=name, path=path)
                ui.notify(f"Workspace '{name}' created.", color="positive")
                create_dialog.close()
                name_input.set_value("")
                path_input.set_value("")
                workspace_list.refresh()
            except Exception as exc:
                ui.notify(str(exc), color="negative")

        with ui.row().classes("justify-end gap-2 w-full mt-4"):
            ui.button("Cancel", on_click=create_dialog.close).props("flat")
            ui.button("Create", on_click=do_create)

    # ------------------------------------------------------------------ remove dialog
    with ui.dialog() as remove_dialog, ui.card().classes("w-96"):
        remove_title = ui.label("").classes("text-lg font-semibold mb-2")
        purge_checkbox = ui.checkbox("Also delete workspace folder from disk")

        async def do_remove() -> None:
            row = pending_remove[0]
            name = row.get("name", "")
            try:
                WorkspaceRemoveTool().execute(name=name, purge=purge_checkbox.value)
                ui.notify(f"Workspace '{name}' removed.", color="positive")
                remove_dialog.close()
                workspace_list.refresh()
            except Exception as exc:
                ui.notify(str(exc), color="negative")

        with ui.row().classes("justify-end gap-2 w-full mt-4"):
            ui.button("Cancel", on_click=remove_dialog.close).props("flat")
            ui.button("Remove", on_click=do_remove).props('color="negative"')

    # ------------------------------------------------------------------ refreshable table
    @ui.refreshable
    def workspace_list() -> None:
        rows: list[dict] = []
        error: str | None = None

        try:
            ws_result = WorkspaceListTool().execute()
            running_by_name: dict[str, bool] = {}
            try:
                status_result = StatusTool().execute()
                running_by_name = {w.name: w.server_running for w in status_result.workspaces}
            except Exception:
                pass
            for ws in ws_result.workspaces:
                rows.append({**ws, "running": running_by_name.get(ws["name"], False)})
        except Exception as exc:
            error = str(exc)

        if error:
            ui.label(f"Error loading workspaces: {error}").classes("text-negative")
            return

        if not rows:
            with ui.card().classes("w-full"):
                ui.label("No workspaces configured yet. Create one to get started.").classes(
                    "opacity-60 text-sm p-2"
                )
            return

        columns = [
            {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
            {"name": "status", "label": "Status", "field": "running", "align": "left"},
            {"name": "http_port", "label": "HTTP port", "field": "http_port", "align": "left"},
            {"name": "gateway_port", "label": "Gateway port", "field": "gateway_port", "align": "left"},
            {"name": "is_default", "label": "Default", "field": "is_default", "align": "center"},
            {"name": "actions", "label": "", "field": "name", "align": "right"},
        ]

        table = ui.table(columns=columns, rows=rows, row_key="name").classes("w-full")
        table.add_slot(
            "body-cell-status",
            """
            <q-td :props="props">
                <q-badge :color="props.row.running ? 'positive' : 'grey-6'"
                         :label="props.row.running ? 'Running' : 'Stopped'" />
            </q-td>
            """,
        )
        table.add_slot(
            "body-cell-is_default",
            """
            <q-td :props="props" class="text-center">
                <q-icon v-if="props.row.is_default" name="star" color="warning" size="sm" />
            </q-td>
            """,
        )
        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props" class="text-right">
                <q-btn v-if="!props.row.is_default" flat dense size="sm" icon="star_border"
                       color="warning" title="Set as default"
                       @click="() => $parent.$emit('set-default', props.row)" />
                <q-btn flat dense size="sm" icon="delete" color="negative" title="Remove"
                       @click="() => $parent.$emit('remove', props.row)" />
            </q-td>
            """,
        )

        async def handle_set_default(e) -> None:
            row = e.args if isinstance(e.args, dict) else {}
            name = row.get("name", "")
            try:
                WorkspaceSetDefaultTool().execute(name=name)
                ui.notify(f"'{name}' is now the default workspace.", color="positive")
            except Exception as exc:
                ui.notify(str(exc), color="negative")
            workspace_list.refresh()

        def handle_remove(e) -> None:
            row = e.args if isinstance(e.args, dict) else {}
            pending_remove[0] = row
            remove_title.set_text(f"Remove workspace '{row.get('name', '')}'?")
            purge_checkbox.set_value(False)
            remove_dialog.open()

        table.on("set-default", handle_set_default)
        table.on("remove", handle_remove)

    # ------------------------------------------------------------------ page layout
    with ui.column().classes("w-full gap-6 p-6"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Workspaces").classes("text-2xl font-semibold")
            ui.button("Create workspace", icon="add", on_click=create_dialog.open)

        workspace_list()
