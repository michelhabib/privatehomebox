"""Minimal JSON-RPC 2.0 helpers for phbcli's plugin server side.

Kept as a standalone module so phbcli does not need to import phb-channel-sdk.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4


def build_notification(method: str, params: dict[str, Any] | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params or {}},
        separators=(",", ":"),
    )


def build_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id or uuid4().hex,
        },
        separators=(",", ":"),
    )


def build_success(result: Any, request_id: str | int | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "result": result, "id": request_id},
        separators=(",", ":"),
    )


def build_error(
    code: int,
    message: str,
    request_id: str | int | None = None,
    data: Any = None,
) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message, "data": data},
            "id": request_id,
        },
        separators=(",", ":"),
    )
