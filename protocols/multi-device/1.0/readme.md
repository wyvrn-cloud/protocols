---
title: Multi-Device Identity
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/multi-device/1.0
status: Proposed
summary: Lets one person use several devices that all independently send and receive as the same Identity DID, with no central account server, by copying that identity's own keys to every enrolled device and requiring any revocation to rotate them -- and by giving each device its own separate Device DID for device-to-device coordination, synchronized via a locally-kept, fan-out roster.
tags:
  - identity
  - multi-device
  - key-management
authors:
  - name: wyvrn
---

## Summary

Multi-Device Identity lets a single person's identity span several
independent devices (phone, laptop, tablet), all of which contacts see as
one **Identity DID**, without any device being a required,
permanently-available "server," and without a central account system
anywhere. It does this with two DIDs per person, not one:

- The **Identity DID** — one keyAgreement key (what contacts encrypt
  content to) and one authentication key (used only to sign
  [DID rotations](https://identity.foundation/didcomm-messaging/spec/v2.1/)),
  both copied to every enrolled device. Because every device holds a real
  copy, any of them can independently receive and decrypt content the
  moment it arrives — no device is a bottleneck the others wait on — and
  any of them can single-handedly rotate the identity away from a device
  that's gone missing, without needing that device's cooperation.
- A **Device DID** per device, independently generated, never shared —
  used only for device-to-device coordination (enrollment, the roster,
  rotation announcements). Contacts never see or address it.

Devices learn about each other through a small, locally-kept roster,
synchronized the same fan-out-with-no-shared-state way
[`group-chat/1.0`](../../group-chat/1.0/readme.md) synchronizes group
membership.

This protocol covers device identity, enrollment, the roster, and identity
key rotation. It deliberately does not cover replicating message history to
a newly added device, or reconciling other local state between devices —
that's [`history-sync/1.0`](../../history-sync/1.0/readme.md)'s job,
referenced from here at the points where it applies.

## Motivation

DIDComm's standard building blocks assume one identity is one keypair. The
obvious way to add more devices without changing that is to just copy the
one keypair everywhere — but a real requirement rules out the *opposite*
choice this protocol's own earlier draft tried instead (isolating each
device behind its own independent key, sharing only a narrower
housekeeping credential): **every enrolled device needs to receive and
decrypt content independently, at any time, regardless of whether any
other device is online.** A phone that can only get messages once a laptop
happens to wake up and relay them isn't really a second device — it's a
spectator. And because any DIDComm sender might be a real, independent
implementation this project doesn't control, there's no way to make a
sender address multiple devices itself (see Design By Contract on why
per-device `keyAgreement` entries don't work); the only way several
devices can each decrypt what one sender encrypted once, to one key, is
if they all hold a real copy of that one key.

So this protocol accepts the isolation cost the naive approach has, rather
than trying to design around it: the Identity DID's actual keys —
including the one that decrypts real content — are genuinely copied to
every enrolled device. What contains a device compromise isn't key
separation, it's speed and completeness of revocation: **any**
`device-revoke`, regardless of reason, requires rotating the Identity DID's
keys and propagating the new ones to every remaining device (see Key
Rotation) — not just when the reason is `"compromised"`. Once a device is
gone, the only meaningful question is how fast the identity moves on
without it, not whether losing that one device was somehow contained on
its own.

The Device DID layer exists because *this protocol's own* traffic (who's
enrolled, rotation announcements, roster changes) still benefits from
per-device isolation — a compromised device shouldn't be able to silently
impersonate a *different* sibling device to the rest of the roster, even
though it can, by design, decrypt real content. Splitting these two
purposes is what makes "every device shares the content key" a bounded
decision instead of "every device shares everything."

## Roles

There is exactly one role, `device`. Every enrolled device is a full,
symmetric peer — holds a real copy of the Identity DID's keys, can
independently send and receive as that identity, and can single-handedly
trigger a key rotation. There is no primary/secondary distinction, and
(unlike an earlier draft of this protocol) no device is more
externally-important than any other once it's enrolled: the *founding*
device (the one that generated the identity) is only distinguished by
having been first — losing it later is exactly as recoverable as losing
any other enrolled device, provided at least one sibling survives it (see
Design By Contract, and Key Rotation). A device is enrolled either by
founding the identity, or by exchanging `device-enroll-request`/
`device-enroll-response` with an already-enrolled device (see Basic
Walkthrough).

## Connectivity

Every message in this protocol is sent device-to-device, mediated exactly
like any other pairwise DIDComm v2 message — addressed to a specific
sibling device's own Device DID, through the same shared mediator every
device is already registered with. There is no broadcast primitive,
`device-announce`/`device-revoke` are fanned out to each known sibling
individually, mirroring `group-chat/1.0`'s own fan-out for membership
changes. This is separate from, and irrelevant to, how contacts reach the
*Identity* DID directly — see Design By Contract.

## States

| State | Meaning |
|---|---|
| `unenrolled` | This device does not yet hold a copy of the Identity DID's keys. |
| `enrolled` | This device holds a copy of the Identity DID's keys, has its own registered Device DID, and has a (locally-known, possibly incomplete) roster of sibling devices. |

| Event | `unenrolled` | `enrolled` |
|---|---|---|
| Receive a `device-enroll-response` | → `enrolled` (roster seeded from what it carried) | if `rotates: true`, adopts the new Identity DID keys (see Key Rotation); otherwise n/a (already enrolled) |
| Receive `device-announce` | no-op (not enrolled, nothing to update) | stays `enrolled`, roster gains an entry |
| Receive `device-revoke` for another device | no-op | stays `enrolled`, roster loses an entry, expects a rotating `device-enroll-response` to follow shortly (see Key Rotation) |
| Receive `device-revoke` for *this device's own* Device DID | no-op | this device should stop presenting itself as enrolled — see Security |

## Basic Walkthrough

Alice generates her identity on her phone, then later adds a laptop.

1. **Founding device.** Alice's phone generates the Identity DID's two
   keys (a keyAgreement key contacts will encrypt to, and an
   authentication key used only for signing future rotations), completes
   `coordinate-mediation/3.0` for the Identity DID
   (`mediate-request` → `mediate-grant`, `recipient-update`), and
   *separately* generates its own independent Device DID and mediates
   that too, for device-to-device traffic. The phone's roster starts as
   just itself: `[{ device_id: "phone", device_did: "did:peer:4...phone" }]`.
2. **New device prepares.** Before scanning anything, the laptop generates
   its *own* independent Device DID locally — the same key pair it'll
   keep using for the rest of its enrolled life, not a throwaway. It needs
   this first because the exchange below encrypts the Identity DID's keys
   *to* it; an unenrolled device has to hold some key before it can
   receive anything confidential.
3. **Out-of-band enrollment.** The phone displays a QR code: a real
   [`out-of-band/2.0`](https://didcomm.org/out-of-band/2.0) invitation
   (`goal_code: "wyvrn.multi-device.enroll"`, `from` the phone's own
   Device DID), the standard DIDComm mechanism for "here's how to start
   talking to me," carrying no secret material itself — its only job is
   getting the laptop a route to the phone. The laptop scans it and sends
   a `device-enroll-request`, mediated and encrypted like any ordinary
   DIDComm v2 message, from its new Device DID (from step 2) to the
   phone's:
   ```json
   {
     "id": "b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
     "type": "https://wyvrn.app/multi-device/1.0/device-enroll-request",
     "body": {
       "device_id": "laptop",
       "device_did": "did:peer:4...laptop"
     }
   }
   ```
   Physical possession of the displayed QR code is the entire trust basis
   here — the same assumption Signal's and WhatsApp's device-linking flows
   make — so the phone can reply without any further out-of-band
   confirmation (an implementation may still choose to show a
   confirmation prompt on the phone before replying, but this protocol
   doesn't require one). The phone replies with a `device-enroll-response`,
   encrypted specifically to the laptop's new Device DID, carrying the
   actual secret:
   ```json
   {
     "id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
     "type": "https://wyvrn.app/multi-device/1.0/device-enroll-response",
     "thid": "b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
     "body": {
       "identity_did": "did:peer:4...identity",
       "identity_keys": {
         "key_agreement": { "kty": "OKP", "crv": "X25519", "d": "...", "x": "..." },
         "authentication": { "kty": "OKP", "crv": "Ed25519", "d": "...", "x": "..." }
       },
       "roster": [{ "device_id": "phone", "device_did": "did:peer:4...phone" }]
     }
   }
   ```
4. **New device registers itself.** Holding the Identity DID's keys now,
   the laptop `recipient-update`s the Identity DID as a recipient it can
   also be reached at (see Design By Contract on what this needs from the
   mediator), and separately `recipient-update`s its own Device DID
   (already generated in step 2) under its own mediation relationship,
   exactly as the phone did when it founded the identity.
5. **Roster fan-out.** The laptop sends every device in the roster it was
   given (just the phone, here) a `device-announce`:
   ```json
   {
     "id": "9d9a5f2a-3b7e-4b8e-9c9a-1f2b3c4d5e6f",
     "type": "https://wyvrn.app/multi-device/1.0/device-announce",
     "body": {
       "device_id": "laptop",
       "device_did": "did:peer:4...laptop",
       "announced_at": 1735689600000
     }
   }
   ```
6. The phone adds the laptop to its own roster on receipt. Both devices now
   independently know `[phone, laptop]`, and both can now independently
   send and receive as the Identity DID — a contact's message reaches
   whichever of them is online, live, with no relay or handoff needed
   between them for ordinary delivery.
7. Months later, Alice's phone is stolen. From the laptop, she sends a
   `device-revoke`:
   ```json
   {
     "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
     "type": "https://wyvrn.app/multi-device/1.0/device-revoke",
     "body": {
       "device_did": "did:peer:4...phone",
       "reason": "lost"
     }
   }
   ```
   Since there is now only one enrolled device to send this to, the
   laptop *also* performs its own `recipient-update` (`action: "remove"`)
   for the phone's Device DID, and — this is the step that actually
   matters — immediately generates a **new** Identity DID with fresh
   keys and rotates every known contact onto it via `from_prior` (see Key
   Rotation), since the phone held a real copy of the old Identity DID's
   keys and can no longer be trusted with them. Unlike an earlier draft of
   this protocol, this fully recovers the identity: the laptop didn't need
   the phone's cooperation, and every contact ends up talking to a DID the
   phone never had a copy of. The one real constraint is timing — see
   Security on the risk of an attacker racing this same rotation first.

## Design By Contract

- **Why the keys are shared instead of split per device: a real DIDComm
  sender can't be made to address more than one key.** An earlier draft
  gave each device its own independent `keyAgreement` entry in a shared,
  mutable DID document, hoping a sender's single message could reach every
  device via a multi-recipient JWE. That doesn't hold up: a DIDComm sender
  resolving a DID document only ever uses its *first* usable `service`
  entry and *first* matching `keyAgreement` key — this library's own
  resolvers do exactly that, and it's the only safe assumption for any
  real counterpart this project doesn't control, which won't have been
  specially built to encrypt to every key a document happens to list.
  Copying the *same* key to every device sidesteps this entirely: from a
  sender's perspective there is still exactly one key, one recipient, one
  ordinary JWE — the multiplicity is purely on the decrypting side, invisible
  to anyone outside the identity.
- **How a device obtains the Identity DID's keys is defined, not left
  open — see Basic Walkthrough steps 2-4.** The real
  [`out-of-band/2.0`](https://didcomm.org/out-of-band/2.0) protocol carries
  a QR-encoded invitation whose only job is establishing a route between
  the two devices, and this protocol's own `device-enroll-request`/
  `device-enroll-response` (see Message Reference) carry the actual keys
  over the ordinary encrypted DIDComm connection that invitation leads to
  — no separate file format or transfer mechanism this protocol doesn't
  already speak. Physical possession of the displayed QR code is the trust
  basis, the same assumption Signal's and WhatsApp's own device-linking
  flows make.
- **Every `device-revoke`, regardless of `reason`, requires an Identity DID
  key rotation — there is no "merely lost, no rotation needed" case
  anymore.** Because the revoked device held a real copy of the content
  key, removing its mediator registration (`recipient-update`) doesn't
  actually stop it from decrypting anything: the Identity DID's public key
  hasn't changed, so a sender who hasn't yet seen a rotation keeps
  encrypting to the same key regardless of what's registered at the
  mediator. A "lost" device found later by someone else is
  indistinguishable, in the end, from a "compromised" one — so `reason` is
  informational for the humans involved, not a signal this protocol
  branches on. See Key Rotation for the actual mechanism.
- **No distributed consensus, same as `group-chat/1.0`.** Two devices
  enrolled or revoked at close to the same time can leave the roster
  briefly inconsistent between siblings until every `device-announce`/
  `device-revoke` has been delivered to everyone. This protocol does not
  attempt to detect or resolve that race.
- **A device that misses announces** (was offline, or was enrolled from an
  incomplete roster) can fall behind the real roster with no way to
  self-heal from this protocol alone — there is no `roster` snapshot
  request/response defined here. In practice this is expected to be
  recovered by treating the device roster as just another
  [`history-sync/1.0`](../../history-sync/1.0/readme.md) collection
  (`collection_id: "devices"`) and letting that protocol's periodic
  reconciliation catch a stale roster the same way it catches stale
  message history, rather than duplicating a second bespoke
  snapshot-fetch mechanism here.
- **What contacts actually see as "the DID" is the Identity DID, for the
  identity's whole lifetime (across rotations) — no Device DID is ever
  addressed by a contact.** This needs no DID mutability and no hosted
  document: `did:peer:4` stays immutable per rotation, but the *identity*
  it names isn't tied to any one physical device, so losing any single
  device — including the one that founded it — is recoverable via Key
  Rotation as long as at least one other enrolled device survives it. The
  only case this doesn't cover is an identity that only ever had one
  enrolled device: there is no sibling left to rotate on its behalf, which
  is an inherent limit of having no redundancy at all, not a gap in this
  protocol (see Future Considerations).
- **The mediator needs one real new capability: several devices
  independently reachable at one shared recipient DID.** Live delivery
  already supports this (`wyvrn-mediator-protocols`' `WsConnStore` already
  tracks and fans out to more than one live connection per DID). Queued
  delivery (`messagepickup/3.0`) does not yet: its ordinary semantics
  assume one consumer acks and removes a message, which would let one
  device silently starve another of anything delivered while it was
  offline. This protocol assumes the mediator treats a queued message
  addressed to an Identity DID as available to *every* currently
  `recipient-update`-registered device independently (each with its own
  delivery/ack cursor), not a single shared consume-once queue — a
  mediator implementation detail this protocol depends on but doesn't
  itself define.

## Key Rotation

Rotation is not a rare, special-case recovery path here — it's the normal,
required response to **every** `device-revoke`, whatever the reason (see
Design By Contract). It reuses the enrollment exchange rather than
defining a new one:

1. Any still-trusted device generates a **new** Identity DID (a fresh
   keyAgreement key and a fresh authentication key) and completes
   `coordinate-mediation/3.0` for it against the same mediator.
2. It signs a `from_prior` transition (per
   [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/):
   `sub` the new Identity DID, `iss` the old one) using the **old**
   Identity DID's authentication key — still valid to sign with, since the
   spec only requires a key the *departing* DID authorized, regardless of
   how many copies of it exist — and includes it on the next message (or a
   dedicated one) to every known contact, letting each contact verify
   continuity and switch over to the new DID for the same relationship.
3. It runs the same `device-enroll-request`/`device-enroll-response`
   exchange from Basic Walkthrough with every *other* still-trusted device
   in its roster, one at a time — except the payload is the new Identity
   DID and its keys, not a founding one, so the `device-enroll-response`
   sets `rotates: true` (see Message Reference) to tell the receiving
   device this replaces its existing Identity DID rather than starting a
   fresh enrollment.
4. Each device that receives a rotating `device-enroll-response` adopts
   the new Identity DID and keys, `recipient-update`s the new one at the
   mediator, then issues a removal `recipient-update` against the old one.
   Its own Device DID is untouched throughout — only the shared Identity
   layer changes.
5. Once every remaining device has rotated, the old Identity DID has no
   recipients left registered under it and can simply be abandoned — no
   explicit "terminate" step needed.

This needs no new mediator capability beyond what enrollment already
needs — registering an additional recipient DID under an existing
mediation relationship is ordinary `coordinate-mediation/3.0`. What it does
need, and doesn't get automatically, is **speed**: see Security for why a
slow rotation loses its entire point.

## Security

- **A device holding the Identity DID's keys can decrypt everything ever
  sent to that identity while it holds them — this is the actual cost of
  the design, not an incidental risk.** Compromise of any one currently-
  enrolled device exposes live traffic addressed to the identity, not just
  that device's own history, for as long as the compromise goes
  unnoticed. This is the tradeoff Motivation accepts in exchange for every
  device being independently, immediately reachable; it is bounded by how
  fast a compromise is noticed and rotated away from, not eliminated by
  key design.
- **A rotation is a race, and the compromised device's owner might not be
  the only one who can win it.** If an attacker who stole a device also
  extracts its copy of the Identity DID's authentication key before the
  legitimate owner revokes it, that attacker can sign their *own*
  `from_prior` transition — to a DID they control — and if it reaches
  contacts first, it hijacks the relationship rather than merely reading
  it. [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)
  itself only promises that a receiver processes rotations in whatever
  order messages arrive, not that the "real" owner's rotation wins any
  race — so an implementation should treat "device lost" with the same
  urgency as "device compromised" (Design By Contract already collapses
  these for what action is required; this is why that collapse matters for
  *timing*, not just mechanism) and make revoking-and-rotating from a
  surviving device a fast, one-step action, not something that waits on
  confirming the device is actually being misused.
- **Device DIDs and the Identity DID are independent trust boundaries.** A
  device that fabricates `device-announce`/`device-revoke` can only do so
  if it's already enrolled (holds Identity DID keys, which is what lets it
  authenticate as a sibling at all) — this protocol adds no attack surface
  beyond "an enrolled device is a trusted device," which Motivation already
  accepts as the cost of independent multi-device receipt.
- **Losing the *last* enrolled device is unrecoverable, same as any
  single-key identity with no redundancy** — there is no sibling left to
  rotate on its behalf. This isn't specific to this protocol; it's true of
  a single-device DIDComm identity today, and multi-device enrollment only
  helps once there are at least two devices to lose one of.

## Message Reference

### `device-enroll-request`

Sent by an unenrolled device to an already-enrolled one, over the
connection established by scanning that device's `out-of-band/2.0`
invitation (see Basic Walkthrough) — from the unenrolled device's own
freshly-generated Device DID, requesting to be enrolled.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device, same meaning as `device-announce`'s field of the same name. |
| `device_did` | string | The requesting device's own independently-generated Device DID — not yet registered with the mediator; that happens after this exchange completes. |

### `device-enroll-response`

Sent in reply (`thid` set to the request's `id`), encrypted specifically to
the requesting device's `device_did` — never broadcast, never sent
unprompted.

| Field | Type | Description |
|---|---|---|
| `identity_did` | string | The Identity DID these keys belong to. |
| `identity_keys` | object | `{ key_agreement, authentication }`, each a private JWK. The single most sensitive value this protocol ever transmits — see Security. |
| `roster` | array of object | The sender's current roster, `{ device_id, device_did }` per entry — seeds the new device's own copy. |
| `rotates` | boolean | `false`/absent for ordinary enrollment. `true` means this response carries a **replacement** Identity DID and keys for a device that's already enrolled (see Key Rotation) — the receiving device keeps its existing `device_did` rather than treating this as a fresh enrollment. |

### `device-announce`

Sent by a newly enrolled device to every device in the roster it was given
at enrollment time; sent by an already-enrolled device to any sibling it
later learns about (e.g. via `history-sync/1.0` roster reconciliation)
that it has not yet announced itself to.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device (e.g. `"phone"`, a user-chosen name, or a generated id) — display-only, not used for addressing. |
| `device_did` | string | This device's own independently-generated Device DID, already registered with the mediator via `recipient-update`. |
| `announced_at` | integer | Unix epoch milliseconds this device considers itself enrolled as of. |
| `capabilities` | array of string | Optional. What this device can do beyond the symmetric default every device has today — e.g. `"live-push"` (holds a live WebSocket connection to the mediator), `"poll-only"` (never does, relies entirely on periodic pickup). Absent means "treat as fully symmetric with every other device," true for every device this version of `wyvrn-chat` actually produces; the field exists so a future device that's meaningfully different (e.g. a headless relay with no UI) can say so without a protocol version bump. |
| `retention` | string | Optional. `"unbounded"` or `"bounded"`, mirroring this device's own [`history-sync/1.0`](../../history-sync/1.0/readme.md) retention policy — lets a sibling's `backfill-request` skip known-bounded devices instead of asking and getting nothing back. Absent is treated as `"bounded"` (the conservative assumption). |

### `device-revoke`

Sent to every other known device announcing that one device should no
longer be considered part of the identity. Expected to be followed shortly
by a rotating `device-enroll-response` from the sender (see Key Rotation)
— `device-revoke` itself only updates roster knowledge, it doesn't perform
the rotation.

| Field | Type | Description |
|---|---|---|
| `device_did` | string | The `device_did` (from that device's own `device-announce`) being revoked. |
| `reason` | string | One of `"lost"`, `"compromised"`, `"replaced"`. Informational only (see Design By Contract) — every reason requires the same key rotation. |

## Implementations

Name / Link | Implementation Notes
--- | ---
_(none yet)_ | Proposed alongside [`history-sync/1.0`](../../history-sync/1.0/readme.md) for [`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat); not yet implemented.

## Endnotes

### Future Considerations

- **An identity with only ever one enrolled device has no recovery if that
  device is lost.** Not a gap this protocol can close — there's no
  sibling left to rotate on its behalf, the same as any single-key
  identity today. The practical mitigation is entirely UX: encourage
  enrolling a second device early, rather than trying to solve this
  cryptographically.
- **Making the required key rotation actually fast in practice** (Security)
  — e.g. a mediator-observable "this device hasn't been seen in N days,
  consider revoking" nudge, or a dead-man's-switch style automatic
  rotation, so "the attacker might win the race" isn't left purely to how
  quickly a person happens to notice a device is gone.
- A push-based `roster` snapshot response, if `history-sync/1.0`
  reconciling the device roster as an ordinary collection proves too slow
  to recover from a large miss in practice.
- Letting `device-enroll-request` carry a piggybacked `history-sync/1.0`
  request (e.g. "also send me the last 30 days of every conversation"),
  instead of the new device always waiting for a separate reconciliation
  pass after enrollment completes — today a real but likely small latency
  gap between "enrolled" and "caught up."
