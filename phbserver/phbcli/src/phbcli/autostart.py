"""Auto-start registration for phbcli.

Windows strategy (in order):
  1. schtasks /Create /SC ONLOGON /RL LIMITED  — preferred; user-scoped task.
     If this fails (Access Denied on some Win10/11 configs) →
  2. Registry HKCU\\...\\Run key — always works, no elevation required.

A separate `register_autostart_elevated()` is provided for callers that can
trigger a UAC prompt and want a /RL HIGHEST task instead.

Stubs for macOS (launchd) and Linux (systemd) are provided for future use.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from typing import Literal

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore[assignment]

TASK_NAME = "phbcli-server"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_RUN_KEY = "phbcli-server"

AutostartMethod = Literal["schtasks", "registry", "none"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _phbcli_executable() -> str:
    """Resolve the full path to the phbcli executable."""
    exe = shutil.which("phbcli")
    if exe is None:
        raise RuntimeError(
            "phbcli executable not found on PATH. "
            "Make sure it is installed (e.g. via 'uv tool install phbcli')."
        )
    return exe


def _is_admin() -> bool:
    """Return True if the current process is running with admin privileges."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Windows — Task Scheduler
# ---------------------------------------------------------------------------

def _schtasks_create(exe: str, run_level: str = "LIMITED") -> bool:
    """Create a Task Scheduler ONLOGON task. Returns True on success."""
    cmd = [
        "schtasks",
        "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{exe}" start',
        "/SC", "ONLOGON",
        "/RL", run_level,
        "/F",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def _schtasks_delete() -> bool:
    """Delete the Task Scheduler task. Returns True on success or if not found."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 or "does not exist" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Windows — Registry Run key (no elevation required)
# ---------------------------------------------------------------------------

def _registry_create(exe: str) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        REG_RUN_PATH,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, REG_RUN_KEY, 0, winreg.REG_SZ, f'"{exe}" start')


def _registry_delete() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_RUN_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, REG_RUN_KEY)
    except FileNotFoundError:
        pass


def _registry_exists() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, REG_RUN_KEY)
        return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Windows — UAC-elevated schtasks (for HIGHEST run level)
# ---------------------------------------------------------------------------

def _elevate_schtasks_create(exe: str) -> bool:
    """
    Launch schtasks elevated via UAC (ShellExecuteW runas).
    Blocks until the elevated process exits.
    Returns True if UAC was accepted and task created successfully.
    """
    args = (
        f'/Create /TN "{TASK_NAME}" /TR "\\"{exe}\\" start" '
        f"/SC ONLOGON /RL HIGHEST /F"
    )
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,       # hwnd
        "runas",    # verb — triggers UAC
        "schtasks", # file
        args,       # parameters
        None,       # directory
        1,          # SW_SHOWNORMAL
    )
    # ShellExecuteW returns > 32 on success
    return int(ret) > 32


def _elevate_schtasks_delete() -> bool:
    """
    Delete the Task Scheduler task elevated via UAC.
    Needed when the task was originally created with /RL HIGHEST.
    Returns True if UAC was accepted.
    """
    args = f'/Delete /TN "{TASK_NAME}" /F'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "schtasks", args, None, 1
    )
    return int(ret) > 32


# ---------------------------------------------------------------------------
# Windows — main register/unregister with fallback chain
# ---------------------------------------------------------------------------

def _register_windows(exe: str) -> AutostartMethod:
    """
    Try schtasks first; fall back to registry on failure.
    Returns the method that succeeded.
    """
    if _schtasks_create(exe, run_level="LIMITED"):
        return "schtasks"

    # schtasks failed (likely Access Denied) — use registry fallback
    _registry_create(exe)
    return "registry"


def _unregister_windows() -> None:
    _schtasks_delete()
    _registry_delete()


# ---------------------------------------------------------------------------
# macOS (stub)
# ---------------------------------------------------------------------------

def _register_macos(_exe: str) -> AutostartMethod:
    raise NotImplementedError("macOS launchd auto-start is not yet implemented.")


def _unregister_macos() -> None:
    raise NotImplementedError("macOS launchd auto-start is not yet implemented.")


# ---------------------------------------------------------------------------
# Linux (stub)
# ---------------------------------------------------------------------------

def _register_linux(_exe: str) -> AutostartMethod:
    raise NotImplementedError("Linux systemd auto-start is not yet implemented.")


def _unregister_linux() -> None:
    raise NotImplementedError("Linux systemd auto-start is not yet implemented.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_autostart() -> AutostartMethod:
    """
    Register phbcli to start automatically on user login.

    Returns the method used: 'schtasks' | 'registry'.
    On Windows the function never raises — it always succeeds via the
    registry fallback.
    """
    exe = _phbcli_executable()
    if sys.platform == "win32":
        return _register_windows(exe)
    elif sys.platform == "darwin":
        return _register_macos(exe)
    else:
        return _register_linux(exe)


def register_autostart_elevated() -> bool:
    """
    Windows only: register a /RL HIGHEST (elevated) task via UAC prompt.

    Shows a UAC dialog. Returns True if the user accepted and the task
    was created, False if they cancelled.
    Raises RuntimeError on non-Windows platforms.
    """
    if sys.platform != "win32":
        raise RuntimeError("Elevated auto-start is only supported on Windows.")
    exe = _phbcli_executable()
    return _elevate_schtasks_create(exe)


def unregister_autostart() -> None:
    """Remove all auto-start registrations (both schtasks and registry)."""
    if sys.platform == "win32":
        _unregister_windows()
    elif sys.platform == "darwin":
        _unregister_macos()
    else:
        _unregister_linux()


def unregister_autostart_elevated() -> bool:
    """
    Windows only: delete the Task Scheduler task via UAC prompt.

    Use this when the task was originally created with --elevated-task
    (/RL HIGHEST) and a standard delete fails with Access Denied.
    Returns True if UAC was accepted, False if cancelled.
    Raises RuntimeError on non-Windows platforms.
    """
    if sys.platform != "win32":
        raise RuntimeError("Elevated teardown is only supported on Windows.")
    accepted = _elevate_schtasks_delete()
    if accepted:
        _registry_delete()  # always clean up registry too
    return accepted
