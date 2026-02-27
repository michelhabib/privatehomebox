
**After pairing, the desktop gives the phone a “membership card.”
Later, the phone proves it’s really the owner of that card.
The gateway checks the card + the proof before letting traffic through.**

### The 3 pieces

1. **Desktop has a master key** (private key) it never shares.
   Think: the desktop is the “bouncer who can sign VIP passes.”

2. **Each device has its own keypair** (private key stays on device, public key is shareable).
   Think: the device has a unique “fingerprint.”

3. **Gateway knows the desktop’s public key** (safe to share) so it can verify signatures from the desktop.

---

## Phase 1: Pairing (one-time)

### Step A — Device creates identity

* Phone generates a keypair:

  * `device_private_key` (secret, stored on phone)
  * `device_public_key` (sent out)

### Step B — Desktop issues a “membership card”

Phone sends to desktop (via gateway):

* pairing code (proves you’re physically near the desktop UI)
* `device_public_key`

Desktop responds by creating and signing an “approval card” that says:

> “I (this desktop) approve device X, and here is its public key.”

Concretely, it’s just a JSON blob like:

```json
{
  "device_id": "phone-1",
  "device_public_key": "....",
  "expires_at": "2026-03-01T00:00:00Z"
}
```

Desktop then signs this blob with its **desktop private key** and sends back to the phone:

* `approval_blob`
* `desktop_signature_over_blob`

That pair = **Device Attestation** (fancy name, simple meaning: “desktop-approved card”).

Phone stores it.

---

## Phase 2: Every connection after that (authentication)

Now the phone wants to connect again tomorrow.

### Step 1 — Phone connects to gateway

Phone opens the WebSocket to the gateway.

### Step 2 — Gateway asks: “prove you’re an approved device”

Gateway sends a random number (nonce), like:

* `nonce = "938475..."`

This nonce prevents replay attacks (copy/paste an old login).

### Step 3 — Phone sends two things

Phone sends:

1. **The membership card** (the attestation)

   * `approval_blob`
   * `desktop_signature_over_blob`

2. **A proof that it owns the device private key**

   * phone signs the gateway’s nonce using **device_private_key**
   * call this signature: `device_signature_over_nonce`

So the phone’s auth message is basically:

* “Here is my card”
* “And here is my signature of your challenge to prove I’m the real owner”

---

## What the gateway checks (simple)

The gateway does **two checks**, both fast:

### Check 1 — Is the card legit?

Gateway verifies `desktop_signature_over_blob` using the **desktop public key**.

If valid → the card was signed by the desktop, not forged.

### Check 2 — Is the phone really the owner of that card?

The card contains `device_public_key`.

Gateway uses that `device_public_key` to verify `device_signature_over_nonce`.

If valid → the phone has the matching private key → it’s the real device, not someone who copied the blob.

✅ If both checks pass: gateway marks this socket as authenticated as `device_id=phone-1` and allows routing.

❌ If either fails: gateway closes the connection.

---

## Why do we need BOTH?

* If you only had the **desktop-signed card**, someone could steal/copy it and reuse it.
* If you only had the **device key**, anyone could generate a key and claim to be allowed.

Together they mean:

* The desktop approved *this* device key
* The connecting device really owns that key

---

## What about the desktop “server app” authentication?

Same exact mechanism:

* Desktop agent also has its own keypair
* Desktop signs an attestation for itself (or you treat the desktop as the root)
* Gateway verifies it the same way

Then the gateway can enforce:

* only devices approved by **this desktop ecosystem** can talk to **that desktop connection**

---

## Revoking a device

Desktop keeps a list: allowed device IDs.

When you revoke `phone-1`:

* gateway can either:

  * have a short expiry on cards (e.g., 7 days), so it stops working soon, **or**
  * ask the desktop “is phone-1 still allowed?” on connect (immediate revoke)

---


