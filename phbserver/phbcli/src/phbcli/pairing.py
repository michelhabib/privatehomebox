"""Pairing session and approved-device persistence helpers."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from .config import APP_DIR, ensure_app_dir

PAIRING_SESSION_FILE = APP_DIR / "pairing_session.json"
APPROVED_DEVICES_FILE = APP_DIR / "devices.json"


class PairingSession(BaseModel):
    code: str
    created_at: datetime
    ttl_seconds: int

    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(seconds=self.ttl_seconds)

    def is_valid(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        return current < self.expires_at

    def remaining_seconds(self, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        delta = self.expires_at - current
        return max(0, int(delta.total_seconds()))


class ApprovedDevice(BaseModel):
    device_id: str
    device_public_key: str
    paired_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


def generate_pairing_code(length: int = 6) -> str:
    if length <= 0:
        raise ValueError("pairing code length must be > 0")
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def create_pairing_session(code_length: int = 6, ttl_seconds: int = 300) -> PairingSession:
    if ttl_seconds <= 0:
        raise ValueError("pairing code ttl_seconds must be > 0")
    return PairingSession(
        code=generate_pairing_code(code_length),
        created_at=datetime.now(UTC),
        ttl_seconds=ttl_seconds,
    )


def load_pairing_session() -> PairingSession | None:
    ensure_app_dir()
    if not PAIRING_SESSION_FILE.exists():
        return None
    try:
        session = PairingSession.model_validate_json(
            PAIRING_SESSION_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return None
    if not session.is_valid():
        clear_pairing_session()
        return None
    return session


def save_pairing_session(session: PairingSession) -> None:
    ensure_app_dir()
    PAIRING_SESSION_FILE.write_text(
        session.model_dump_json(indent=2),
        encoding="utf-8",
    )


def clear_pairing_session() -> None:
    try:
        PAIRING_SESSION_FILE.unlink()
    except FileNotFoundError:
        pass


def load_approved_devices() -> list[ApprovedDevice]:
    ensure_app_dir()
    if not APPROVED_DEVICES_FILE.exists():
        return []
    try:
        raw = json.loads(APPROVED_DEVICES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []

    devices: list[ApprovedDevice] = []
    for item in raw:
        try:
            devices.append(ApprovedDevice.model_validate(item))
        except Exception:
            continue
    return devices


def save_approved_devices(devices: list[ApprovedDevice]) -> None:
    ensure_app_dir()
    APPROVED_DEVICES_FILE.write_text(
        json.dumps(
            [device.model_dump(mode="json") for device in devices],
            indent=2,
        ),
        encoding="utf-8",
    )


def upsert_approved_device(device: ApprovedDevice) -> None:
    devices = load_approved_devices()
    by_id = {d.device_id: d for d in devices}
    by_id[device.device_id] = device
    save_approved_devices(sorted(by_id.values(), key=lambda d: d.device_id))


def revoke_approved_device(device_id: str) -> bool:
    devices = load_approved_devices()
    remaining = [d for d in devices if d.device_id != device_id]
    if len(remaining) == len(devices):
        return False
    save_approved_devices(remaining)
    return True
