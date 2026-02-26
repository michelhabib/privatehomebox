"""PID file-based process management for the phbcli server.

Supports Windows (taskkill) and Unix (SIGTERM).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from .config import PID_FILE


def write_pid(pid: int | None = None) -> None:
    pid = pid or os.getpid()
    PID_FILE.write_text(str(pid), encoding="utf-8")


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def remove_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def is_running(pid: int | None = None) -> bool:
    if pid is None:
        pid = read_pid()
    if pid is None:
        return False
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def kill_process(pid: int) -> bool:
    """Send termination signal to process. Returns True if signal was sent."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                check=True,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def stop_server() -> bool:
    """Stop the running server. Returns True if it was stopped, False if not running."""
    pid = read_pid()
    if pid is None:
        return False
    if not is_running(pid):
        remove_pid()
        return False
    killed = kill_process(pid)
    if killed:
        remove_pid()
    return killed
