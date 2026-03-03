# First Run

If the gateway has **no `gateway_state.json` yet** (first run), passing `--desktop-pubkey` is still correct and is actually the recommended way to start it. From the auth code:

```93:106:d:\projects\privatehomebox\phbserver\gateway\src\phbgateway\auth.py
        if self._desktop_public_key is not None:
            # Idempotent claim from the same desktop key is accepted.
            current = self._desktop_public_key.public_bytes(
                encoding=Encoding.Raw,
                format=PublicFormat.Raw,
            )
            incoming = key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
            if current != incoming:
                return AuthResult(ok=False, reason="gateway already claimed by another desktop")
            return AuthResult(ok=True)

        self._desktop_public_key = key
        self._save_state()
        return AuthResult(ok=True)
```

And from the constructor:

```67:69:d:\projects\privatehomebox\phbserver\gateway\src\phbgateway\auth.py
        if desktop_public_key_b64:
            self._desktop_public_key = _load_public_key_b64(desktop_public_key_b64)
            self._save_state()
```

So on first run, there are two valid paths:

**Path A — pass `--desktop-pubkey` (recommended for dev)**
The gateway pre-loads the key at startup, writes `gateway_state.json` immediately, and accepts the first phbcli connection without any claim handshake needed. This is what the updated `launch.json` does.

**Path B — start without `--desktop-pubkey`**
The gateway starts unclaimed. The first phbcli that connects will go through `verify_desktop_claim`, which sees `_desktop_public_key is None`, accepts it unconditionally, saves the key, and the gateway is now claimed. This is the "zero-config first boot" flow — it works fine as long as no attacker connects before your phbcli does.

For local dev (gateway and phbcli on the same machine) either path is fine. The `launch.json` now uses Path A, which is slightly safer and avoids any "who claims first" race on startup.