---
title: Multi-Device Identity
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/multi-device/1.0
status: Proposed
summary: Lets one person use several devices that all appear as the same DID to the outside world, with no central account server, by splitting identity into one shared control keypair (mediator handshake only) and one independent messaging keypair per device, and by having devices track each other via a locally-kept, fan-out-synchronized roster.
tags:
  - identity
  - multi-device
  - key-management
authors:
  - name: wyvrn
---

## Summary

Multi-Device Identity lets a single person's identity span several
independent devices (phone, laptop, tablet) that all appear as one DID to
their contacts, without any of the devices being a required, permanently-
available "server," and without a central account system anywhere. It does
this by splitting what a single-device DIDComm identity normally treats as
one keypair into two: a **control identity**, shared (copied) across every
device and used only to authenticate mediator housekeeping operations, and
a **messaging identity**, generated independently by each device and used
for everything a contact actually sees. Devices learn about each other
through a small, locally-kept roster, synchronized the same
fan-out-with-no-shared-state way [`group-chat/1.0`](../../group-chat/1.0/readme.md)
synchronizes group membership.

This protocol covers device identity, enrollment, and the roster only. It
deliberately does not cover replicating message history to a newly added
device — that's [`history-sync/1.0`](../../history-sync/1.0/readme.md)'s
job, referenced from here at the points where it applies.

## Motivation

DIDComm's standard building blocks assume one identity is one keypair.
Multi-device support could be bolted on by literally sharing that one
keypair across every device, but that means every device can fully
impersonate the identity with no isolation: losing one device compromises
all of them, and there is no way to revoke a single lost device without
rotating keys everywhere at once.

The alternative this protocol uses instead is narrower: only the identity's
*control* keypair — the one used for
[`coordinate-mediation/3.0`](https://didcomm.org/coordinate-mediation/3.0)
operations against the shared mediator (`mediate-request`,
`recipient-update`, pickup/status) — needs to be shared. Each device
generates its own independent messaging keypair (its own `did:peer:2`,
registered as its own mediator recipient under the shared control
identity), which is what it actually uses to encrypt to and decrypt from
contacts. This is forced by the mediator's own authorization model, not a
design preference layered on top of it: `recipient-update` scopes
ownership of a registered recipient DID to whichever control key
authenticated the request, so any device that needs to manage the set of
registered devices — add a new one, remove a lost one — must hold that
same control key. A device compromise under this model only exposes that
one device's own messaging history, not every device's; revoking it means
removing one recipient registration, not rotating a secret every other
device also depends on.

## Roles

There is exactly one role, `device`. Every device that holds the shared
control keypair is a full peer with every other device — there is no
primary/secondary distinction and no device is required to be online for
the others to keep working. A device is enrolled either by generating the
identity in the first place (the founding device) or by being handed a
copy of the control keypair by an already-enrolled device.

## Connectivity

Every message in this protocol is sent device-to-device, mediated exactly
like any other pairwise DIDComm v2 message — addressed to a specific
sibling device's own messaging DID, through the same shared mediator every
device is already registered with. There is no broadcast primitive,
`device-announce`/`device-revoke` are fanned out to each known sibling
individually, mirroring `group-chat/1.0`'s own fan-out for membership
changes.

## States

| State | Meaning |
|---|---|
| `unenrolled` | This device does not yet hold the identity's control keypair. |
| `enrolled` | This device holds the control keypair, has its own registered messaging DID, and has a (locally-known, possibly incomplete) roster of sibling devices. |

| Event | `unenrolled` | `enrolled` |
|---|---|---|
| Receive the control keypair (out-of-band) | → `enrolled` (roster seeded from whatever the enrolling device provided) | n/a (already enrolled) |
| Receive `device-announce` | no-op (not enrolled, nothing to update) | stays `enrolled`, roster gains an entry |
| Receive `device-revoke` for another device | no-op | stays `enrolled`, roster loses an entry (see Design By Contract on revoking *this* device) |
| Receive `device-revoke` for *this device's own* messaging DID | no-op | this device should stop presenting itself as enrolled — see Security |

## Basic Walkthrough

Alice generates her identity on her phone, then later adds a laptop.

1. **Founding device.** Alice's phone generates the control keypair (used
   only for mediator operations) and completes `coordinate-mediation/3.0`
   normally: `mediate-request` → `mediate-grant`, then generates its own
   messaging `did:peer:2` and registers it via `recipient-update`. The
   phone's roster starts as just itself:
   `[{ device_id: "phone", messaging_did: "did:peer:2...phone" }]`.
2. **Out-of-band enrollment.** Alice authenticates her laptop somehow (a
   QR code scanned by the phone, an encrypted export file transferred
   directly — this protocol does not define the transfer mechanism itself,
   only what happens once it's done; see Design By Contract) and hands it
   a copy of the control keypair, plus the phone's current roster.
3. **New device registers itself.** The laptop generates its *own*
   messaging `did:peer:2` and `recipient-update`s it under the shared
   control identity, exactly as the phone did.
4. **Roster fan-out.** The laptop sends every device in the roster it was
   given (just the phone, here) a `device-announce`:
   ```json
   {
     "id": "9d9a5f2a-3b7e-4b8e-9c9a-1f2b3c4d5e6f",
     "type": "https://wyvrn.app/multi-device/1.0/device-announce",
     "body": {
       "device_id": "laptop",
       "messaging_did": "did:peer:2...laptop",
       "announced_at": 1735689600000
     }
   }
   ```
5. The phone adds the laptop to its own roster on receipt. Both devices now
   independently know `[phone, laptop]`; a contact who resolves Alice's
   messaging DID(s) — see Design By Contract on what "Alice's DID" means
   externally — and any device-to-device history sync (`history-sync/1.0`)
   can address either device directly from here on.
6. Months later, Alice sells her phone without wiping it first. From the
   laptop, she sends a `device-revoke`:
   ```json
   {
     "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
     "type": "https://wyvrn.app/multi-device/1.0/device-revoke",
     "body": {
       "messaging_did": "did:peer:2...phone",
       "reason": "lost"
     }
   }
   ```
   Since there is now only one enrolled device to send this to, the laptop
   *also* performs its own `recipient-update` (`action: "remove"`) against
   the mediator for the phone's `messaging_did` directly — see Design By
   Contract for why both steps are required.

## Design By Contract

- **This protocol does not define how a device obtains the control
  keypair.** That's a local, application-level UX problem (QR-code
  transfer, an encrypted export/import file, or any other secure
  device-to-device channel) with real prior art to draw from (Signal's and
  WhatsApp's own device-linking flows), deliberately left out of scope
  here the same way this repo's protocols never define key generation
  itself. What this protocol defines starts *after* that transfer:
  announcing the new device and registering its messaging identity.
- **Revoking a device is two separate actions, and both matter.**
  `device-revoke` only updates other *devices'* local roster knowledge —
  it does not, by itself, stop the mediator from continuing to deliver to
  the revoked device, since the mediator has no concept of a roster at
  all. An enrolled device must also issue its own
  `coordinate-mediation/3.0/recipient-update` (`action: "remove"`) for the
  revoked device's `messaging_did`. If the revoked device is merely lost
  (not believed compromised), this is sufficient — it can no longer
  receive new mediated messages. If it is believed *compromised* (not just
  unavailable), the shared control keypair itself must also be rotated
  (out of scope here, but see Security) — recipient removal alone does not
  stop a still-live attacker from using the same control key to
  `recipient-update` themselves right back in.
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
- **What contacts actually see as "the DID" is an open question this
  version does not resolve**, and implementations should treat this as a
  deliberate choice with real tradeoffs rather than a gap to silently pick
  one side of:
  - *Multi-recipient delivery*: the externally-resolvable DID document
    lists one `keyAgreement` per enrolled device (and correspondingly one
    `service` entry routing to each device's own mediator registration),
    so a sender's single multi-recipient DIDComm v2 JWE is already validly
    encrypted to every device, and delivery fans out per the resolved
    service list. This gives every device live reachability directly, but
    `did:peer:2`/`did:peer:4` are self-certifying and therefore immutable
    — accommodating a changing device set requires either a genuinely
    mutable DID method (`did:web`/`did:webvh`, which needs *some* hosted,
    resolvable document — self-run is still infrastructure, even if not a
    third party) or minting a new DID and rotating it to every known
    contact (`did-rotate/1.0`-shaped) on every enrollment/revocation.
  - *Single external identity, internal relay*: contacts only ever address
    one device's messaging DID (in practice, whichever device is most
    consistently available — see `history-sync/1.0`'s discussion of an
    unbounded-retention device), which then relays received content to
    siblings entirely internally via `history-sync/1.0`, the same channel
    used for catching up a newly enrolled device. This needs no DID
    mutability or rotation at all, at the cost of that one device's
    availability gating real-time delivery to the others.

## Security

- **The control keypair is the actual trust boundary of this whole
  protocol** — anyone who obtains a copy of it can register themselves as
  a full sibling device and both send and receive mediator-plane
  operations as this identity (though, notably, still cannot decrypt any
  *content* already addressed to another device's independent messaging
  keypair). Its secure transfer during enrollment (explicitly out of scope
  above) is therefore the single most security-critical step in this
  entire protocol; a weak transfer channel undermines everything else here
  regardless of how the rest is implemented.
- **A revoked device that retains the control keypair can silently
  re-register itself** unless the control keypair is rotated, not just the
  one recipient removed — see Design By Contract. Implementations should
  treat "revoke because compromised" and "revoke because merely
  unavailable" as genuinely different operations with different required
  follow-up, not the same message with a cosmetic `reason` field.
- Compromise of one device's independent *messaging* keypair exposes only
  that device's own message traffic — this is the isolation property this
  split is specifically for, and is the main security advantage over
  literally sharing one keypair across every device.
- A device that fabricates `device-announce`/`device-revoke` messages can
  only do so if it already holds the control keypair (needed to
  authenticate as a sibling in the first place), so this protocol adds no
  new attack surface beyond "possession of the control keypair is
  possession of the identity," which is already true of the control
  keypair's role in `coordinate-mediation/3.0` itself.

## Message Reference

### `device-announce`

Sent by a newly enrolled device to every device in the roster it was given
at enrollment time; sent by an already-enrolled device to any sibling it
later learns about (e.g. via `history-sync/1.0` roster reconciliation)
that it has not yet announced itself to.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device (e.g. `"phone"`, a user-chosen name, or a generated id) — display-only, not used for addressing. |
| `messaging_did` | string | This device's own independently-generated messaging DID, already registered with the mediator via `recipient-update`. |
| `announced_at` | integer | Unix epoch milliseconds this device considers itself enrolled as of. |

### `device-revoke`

Sent to every other known device announcing that one device should no
longer be considered part of the identity.

| Field | Type | Description |
|---|---|---|
| `messaging_did` | string | The `messaging_did` (from that device's own `device-announce`) being revoked. |
| `reason` | string | One of `"lost"`, `"compromised"`, `"replaced"`. Informational for the recipient's own judgment about whether to also treat the shared control keypair as compromised (see Security) — this protocol does not act on the value itself. |

## Implementations

Name / Link | Implementation Notes
--- | ---
_(none yet)_ | Proposed alongside [`history-sync/1.0`](../../history-sync/1.0/readme.md) for [`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat); not yet implemented.

## Endnotes

### Future Considerations

- Resolving the open "what does a contact actually address" question in
  Design By Contract with one canonical answer, once real usage shows
  which tradeoff matters more in practice.
- A formal control-keypair rotation flow for the "revoked because
  compromised" case (today: out of scope, same as initial enrollment
  transfer).
- Per-device capability/role hints (e.g. "this device does not accept live
  push, poll-only") if devices ever meaningfully differ in what they can
  do, rather than treating every enrolled device as symmetric.
- A push-based `roster` snapshot response, if `history-sync/1.0`
  reconciling the device roster as an ordinary collection proves too slow
  to recover from a large miss in practice.
