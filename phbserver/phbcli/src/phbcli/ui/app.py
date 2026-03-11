"""NiceGUI app shell — shared layout, sidebar navigation, and page registration.

Call `register_pages()` once before starting the Uvicorn server.  Each page
calls `create_page_layout(active_path)` at the top of its page function.

Dark mode strategy:
  NiceGUI's ui.dark_mode() sets Quasar's body--dark class, which is NOT the
  same as Tailwind's 'dark' selector.  All layout elements therefore use Quasar
  components (QHeader, QDrawer, QItem, etc.) which auto-adapt — no hardcoded
  Tailwind colors on structural elements.
"""

from __future__ import annotations

from nicegui import app as nicegui_app, ui

_NAV: list[tuple[str | None, str, str | None, str | None]] = [
    # (group, label, icon, path)  — group=None marks a section header row
    (None, "Server", None, None),
    ("Server", "Dashboard", "dashboard", "/"),
    ("Server", "Workspaces", "storage", "/workspaces"),
    ("Server", "Channels", "cable", "/channels"),
    ("Server", "Agents", "smart_toy", "/agents"),
    (None, "Nodes / Devices", None, None),
    ("Nodes / Devices", "Devices", "devices", "/devices"),
    ("Nodes / Devices", "Chats", "chat", "/chats"),
    (None, "Configuration", None, None),
    ("Configuration", "Logs", "article", "/logs"),
]


def create_page_layout(active_path: str = "/") -> None:
    """Render the full shell (header + collapsible sidebar) for a page.

    Must be called at the top of every @ui.page function.  The drawer is
    instantiated first so the header toggle button can reference it.
    """
    # behavior="desktop" makes the drawer push page content instead of overlaying it
    drawer = ui.left_drawer(value=True).props('behavior="desktop" bordered')
    with drawer:
        _sidebar(active_path)

    # Bind dark mode to per-user browser storage so the preference persists
    # across page navigations.  Both this element and the header switch write
    # to the same storage key — no extra .on() handler needed.
    ui.dark_mode().bind_value(nicegui_app.storage.user, "dark_mode")

    with ui.header(elevated=True).classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            # color="white" is a Quasar color role — keeps the icon visible on the primary header background
            ui.button(icon="menu", on_click=drawer.toggle).props('flat dense round color="white"')
            ui.icon("home").classes("text-primary text-xl")
            ui.label("PHB Admin").classes("text-lg font-semibold")

        ui.switch("Dark mode").props("dense").bind_value(
            nicegui_app.storage.user, "dark_mode"
        )


def _sidebar(active_path: str) -> None:
    """Render sidebar navigation using Quasar QItem components (auto-adapt to dark mode)."""
    with ui.column().classes("w-full py-2"):
        for group, label, icon, path in _NAV:
            if group is None:
                ui.label(label).classes(
                    "text-xs font-semibold uppercase tracking-wider opacity-50 px-4 pt-3 pb-1"
                )
            else:
                is_active = path == active_path
                # ui.item() → Quasar QItem: auto-adapts background/text to dark mode.
                # Lambda default arg (p=path) captures loop variable correctly.
                with ui.item(on_click=lambda p=path: ui.navigate.to(p)).props(
                    "clickable v-ripple"
                ).classes("rounded-md mx-2 " + ("text-primary" if is_active else "")):
                    with ui.item_section().props("avatar"):
                        if icon:
                            ui.icon(icon).classes(
                                "text-lg " + ("text-primary" if is_active else "opacity-60")
                            )
                    with ui.item_section():
                        ui.label(label).classes("text-sm")


def register_pages() -> None:
    """Register all UI pages.  Import page modules so their @ui.page decorators fire."""
    from phbcli.ui.pages import dashboard as _dashboard  # noqa: F401 — side-effect import
    from phbcli.ui.pages import workspaces as _workspaces  # noqa: F401 — side-effect import
    from phbcli.ui.pages import channels as _channels  # noqa: F401 — side-effect import
    from phbcli.ui.pages import devices as _devices  # noqa: F401 — side-effect import
    from phbcli.ui.pages import agents as _agents  # noqa: F401 — side-effect import

    _register_stub_pages()


# ---------------------------------------------------------------------------
# Stub pages for routes not yet implemented
# ---------------------------------------------------------------------------

_STUBS: list[tuple[str, str, str]] = [
    ("/chats", "Chats", "chat"),
    ("/logs", "Logs", "article"),
]


def _register_stub_pages() -> None:
    for path, label, icon in _STUBS:
        _make_stub_page(path, label, icon)


def _make_stub_page(path: str, label: str, icon: str) -> None:
    @ui.page(path)
    def _stub_page() -> None:
        create_page_layout(active_path=path)
        with ui.column().classes("w-full gap-4 p-6"):
            ui.label(label).classes("text-2xl font-semibold")
            with ui.card().classes("w-full max-w-sm items-center text-center"):
                ui.icon(icon).classes("text-4xl opacity-30 mt-2")
                ui.label("Coming soon").classes("text-lg font-medium opacity-50 mb-1")
                ui.label("This page is planned but not yet implemented.").classes(
                    "text-sm opacity-40 mb-2"
                )
