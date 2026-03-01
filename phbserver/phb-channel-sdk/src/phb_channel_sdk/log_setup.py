"""Shared logging initialiser for all PHB components.

Call ``init()`` once at process start, before any other logging calls.
Each component writes its own rotating log file under ``log_dir``.
In foreground mode a :class:`logging.StreamHandler` is also added so log
output appears in the terminal alongside the file.

Log format (human-readable, UTC timestamps)::

    2026-03-02T10:00:00.123Z [INFO    ] phbcli.agent_manager: Agent started
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT = 5              # keep 5 rotated backups


class _UtcFormatter(logging.Formatter):
    """Emit ISO-8601 UTC timestamps on every log record."""

    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%dT%H:%M:%S", ct)
        return f"{t}.{int(record.msecs):03d}Z"


_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"


def init(
    component: str,
    log_dir: Path,
    *,
    level: str = "INFO",
    foreground: bool = False,
    log_levels: dict[str, str] | None = None,
) -> None:
    """Initialise logging for one PHB process.

    Parameters
    ----------
    component:
        Short label used as the log-file stem, e.g. ``"server"``,
        ``"plugin-devices"``, ``"gateway"``.
    log_dir:
        Directory where rotating log files are written.  Created if absent.
    level:
        Root logger level string (``"INFO"``, ``"DEBUG"``, …).
        Defaults to ``"INFO"``.
    foreground:
        If *True*, also attach a :class:`logging.StreamHandler` so log output
        appears on stdout.  Use for ``phbcli start --foreground`` and direct
        gateway runs.
    log_levels:
        Optional per-logger level overrides applied after the root level, e.g.
        ``{"phbcli.agent_manager": "DEBUG"}``.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = _UtcFormatter(_FMT)
    handlers: list[logging.Handler] = []

    file_handler = RotatingFileHandler(
        log_dir / f"{component}.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    if foreground:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    for logger_name, level_str in (log_levels or {}).items():
        override = getattr(logging, level_str.upper(), None)
        if isinstance(override, int):
            logging.getLogger(logger_name).setLevel(override)
