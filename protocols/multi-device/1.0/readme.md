---
title: Multi-Device Identity
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/multi-device/1.0
status: Proposed
summary: Lets one person use several devices that all independently send and receive as the same Identity DID, with no central account server and no key ever shared between devices, by giving every enrolled device its own independent keyAgreement key (encrypted to directly, via a multi-recipient JWE) and, for devices trusted with roster changes, its own independent authentication key -- and by giving each device its own separate Device DID for device-to-device coordination, synchronized via a locally-kept, fan-out roster.
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

- The **Identity DID** — a document listing one independent `keyAgreement`
  entry per enrolled device (what a contact's sender encrypts real content
  to — every entry, via a multi-recipient JWE, per
  [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)'s
  own recommended default of encrypting to every `keyAgreement` a
  recipient's document lists) and one independent `authentication` entry
  per **trusted** device only (used to sign
  [DID rotations](https://identity.foundation/didcomm-messaging/spec/v2.1/)).
  No private key of either kind is ever copied between devices — each
  device mints its own, and only ever hands out the *public* half. A device
  is enrolled the moment its own `keyAgreement` key is listed; it is
  trusted only once its own `authentication` key is listed too, which is
  never automatic.
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

DIDComm's standard building blocks assume one identity is one keypair. An
earlier draft of this protocol worked around that by copying the *same*
keypair to every device — simple, but with a real cost: any one compromised
device exposes every message ever sent to the identity, for as long as the
compromise goes unnoticed, since every device holds a live copy of the same
content-decryption key.

Per-device keys avoid that cost, and are not actually blocked by anything
DIDComm-specific: the concern that "a sender only uses the first
`keyAgreement` entry it finds" turned out not to hold once checked directly
against [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)'s
own text, rather than assumed by analogy to how a single-device resolver
happens to behave. The spec's own recommended default is the opposite:
encrypt to *every* `keyAgreement` entry a recipient's document lists, so
that recipient "can decrypt his messages on any device he controls, without
sharing keys across his devices" — precisely this protocol's situation, not
an edge case the spec left unaddressed. `wyvrn-didcomm`'s own packaging
resolves a bare-DID recipient this way now (encrypting to every listed
`keyAgreement` entry, producing one multi-recipient JWE any of them can
independently decrypt), so this protocol can rely on it directly rather
than working around a limitation that isn't actually there.

What this design still has to accept, and does deliberately: **because
`did:peer`'s DID value is a hash of its own document, any roster change —
enrolling a device, revoking one, promoting or demoting trust — changes
every listed key's containing document and therefore the Identity DID's own
value.** Every such change requires a `from_prior` rotation broadcast to
every contact. This is a real, recurring cost this protocol accepts in
exchange for never sharing a private key between devices — not an oversight
or a case to optimize away later.

The Device DID layer exists for a separate reason: *this protocol's own*
traffic (who's enrolled, rotation announcements, roster changes) needs a
channel that exists before a device has any Identity DID keys of its own at
all — an unenrolled device has no `keyAgreement` entry yet to be encrypted
to under the identity, so it needs some other independently-addressable DID
to receive its enrollment response on in the first place.

## Roles

There are two roles, distinguished only by whether a device's own
`authentication` key is currently listed in the Identity DID document:

- **`device`** — any enrolled device. Holds its own independent
  `keyAgreement` key (listed in the Identity DID document, so it can
  independently receive and decrypt real content the moment it arrives —
  no device is a bottleneck the others wait on) and its own Device DID. Can
  send and receive as the Identity DID, and can request enrollment or
  promotion, but cannot by itself add another device, revoke one, or
  change trust — those require signing a `from_prior` rotation, which needs
  an `authentication` key this role doesn't hold.
- **`trusted device`** — an enrolled device that additionally holds its own
  independent `authentication` key, listed in the Identity DID document.
  Can single-handedly enroll a new device, revoke any device (including
  itself), or promote/demote another device's trust, because each of those
  is exactly the same operation: mint a new Identity DID document and sign
  a `from_prior` transition from the old one.

The founding device (the one that generated the identity) is a trusted
device from the start — a document with no `authentication` entry at all
couldn't sign the first rotation should one ever be needed — but is not
otherwise distinguished: losing it later is exactly as recoverable as
losing any other trusted device, provided at least one trusted device
survives it (see Design By Contract, and Key Rotation). A new device is
**untrusted by default** on enrollment; promotion is always a separate,
explicit step (see Key Rotation), never automatic.

## Connectivity

Every message in this protocol is sent device-to-device, mediated exactly
like any other pairwise DIDComm v2 message — addressed to a specific
sibling device's own Device DID, through the same shared mediator every
device is already registered with. There is no broadcast primitive,
`device-announce`/`device-revoke`/a rotating `device-enroll-response` are
fanned out to each known sibling individually, mirroring `group-chat/1.0`'s
own fan-out for membership changes. This is separate from, and irrelevant
to, how contacts reach the *Identity* DID directly — see Design By
Contract.

Separately, every device — trusted or not — also independently completes
its own `coordinate-mediation/3.0` handshake for the Identity DID itself
(`mediate-request` → `mediate-grant`, `recipient-update`), authenticated as
the Identity DID via its own `keyAgreement` key. This is what actually lets
several devices each receive the identity's content independently; see
Design By Contract for why it has to be authenticated this way rather than
through a separate per-device "control" identity.

## States

| State | Meaning |
|---|---|
| `unenrolled` | This device does not yet hold a `keyAgreement` entry in the Identity DID document. |
| `enrolled` | This device's own `keyAgreement` key is listed in the current Identity DID document, it has its own registered Device DID, and has a (locally-known, possibly incomplete) roster of sibling devices. |
| `trusted` | `enrolled`, and this device's own `authentication` key is also listed in the current Identity DID document. |

| Event | `unenrolled` | `enrolled` | `trusted` |
|---|---|---|---|
| Receive a `device-enroll-response` (`rotates: false`) | → `enrolled`, adopts the new Identity DID, registers its own `keyAgreement` key with the mediator, roster seeded from what it carried | n/a (already enrolled) | n/a |
| Receive a `device-enroll-response` (`rotates: true`) | n/a (not addressed to an unenrolled device) | adopts the new Identity DID document, re-`recipient-update`s (add new, remove old) | same, and re-evaluates its own trust (a rotation may promote or demote it) |
| Receive `device-announce` | no-op (not enrolled, nothing to update) | stays in state, roster gains an entry | stays in state, roster gains an entry |
| Receive `device-revoke` for another device | no-op | stays in state, roster loses an entry, expects a rotating `device-enroll-response` to follow shortly | same, and may itself perform the rotation if no other trusted device does first |
| Receive `device-revoke` for *this device's own* Device DID | no-op | this device should stop presenting itself as enrolled — see Security | same |

## Basic Walkthrough

Alice generates her identity on her phone, then later adds a laptop.

1. **Founding device.** Alice's phone generates its own `keyAgreement` key
   and its own `authentication` key, mints the first Identity DID document
   (both keys, so the phone is trusted from the start), and completes
   `coordinate-mediation/3.0` for it. It *separately* generates its own
   independent Device DID and mediates that too, for device-to-device
   traffic. The phone's roster starts as just itself:
   `[{ device_id: "phone", device_did: "did:peer:4...phone", key_agreement_public: "z6LSp...", authentication_public: "z6Mkp...", trusted: true }]`.
2. **New device prepares.** Before scanning anything, the laptop generates
   its *own* independent Device DID, and its *own* independent
   `keyAgreement` keypair — the one it'll use for the rest of its enrolled
   life, not a throwaway. It needs the `keyAgreement` key ready before
   enrollment even starts, because it's the phone that will mint the new
   document listing it — the laptop hands over only its *public* key,
   never receiving anyone else's private key in return. It does not
   generate an `authentication` key yet: it isn't trusted, and won't need
   one unless later promoted.
3. **Out-of-band enrollment.** The phone displays a QR code: a real
   [`out-of-band/2.0`](https://didcomm.org/out-of-band/2.0) invitation
   (`goal_code: "wyvrn.multi-device.enroll"`, `from` the phone's own
   Device DID), the standard DIDComm mechanism for "here's how to start
   talking to me," carrying no key material itself — its only job is
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
       "device_did": "did:peer:4...laptop",
       "key_agreement_public": "z6LSb..."
     }
   }
   ```
   Physical possession of the displayed QR code is the entire trust basis
   here — the same assumption Signal's and WhatsApp's device-linking flows
   make — so the phone can reply without any further out-of-band
   confirmation (an implementation may still choose to show a confirmation
   prompt on the phone before replying, but this protocol doesn't require
   one). Only a **trusted** device can complete this exchange, since doing
   so mints a new Identity DID document and signs a `from_prior` — an
   enroll request that reaches an enrolled-but-untrusted sibling should be
   forwarded to (or re-requested against) a trusted one instead. The phone
   mints a new Identity DID document — every currently-listed
   `keyAgreement` entry plus the laptop's new public one, `authentication`
   entries unchanged — and replies with a `device-enroll-response`,
   encrypted specifically to the laptop's new Device DID:
   ```json
   {
     "id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
     "type": "https://wyvrn.app/multi-device/1.0/device-enroll-response",
     "thid": "b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
     "body": {
       "identity_did": "did:peer:4...identity-v2",
       "mediator_did": "did:peer:2...mediator",
       "from_prior": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDpwZWVyOjQuLi5pZGVudGl0eS12MSNrZXktMiJ9...",
       "roster": [
         {
           "device_id": "phone",
           "device_did": "did:peer:4...phone",
           "key_agreement_public": "z6LSp...",
           "authentication_public": "z6Mkp...",
           "trusted": true
         },
         {
           "device_id": "laptop",
           "device_did": "did:peer:4...laptop",
           "key_agreement_public": "z6LSl...",
           "trusted": false
         }
       ],
       "rotates": false,
       "rotation_seq": 1
     }
   }
   ```
   No private key of any kind appears in this message, or anywhere in this
   protocol — the single most sensitive thing an earlier draft of this
   protocol ever transmitted no longer needs to be transmitted at all.
4. **New device registers itself.** Holding the new Identity DID now (its
   own `keyAgreement` entry is in it, and it was already given
   `mediator_did`), the laptop sends a bare `recipient-update` (`action:
   "add"`) for it — no `mediate-request` needed, since the document's
   endpoint was already the real one by the time it was minted (see Design
   By Contract). It separately registers its own Device DID the normal way,
   under its own, already-established mediation relationship from step 2.
5. **The phone fans the rotation out to every *other* sibling it already
   knows about** (there are none yet in this two-device example; with a
   third device already enrolled, it would get this step too) — the same
   `device-enroll-response`, but with
   `rotates: true` and no `thid`, since it isn't a reply to anything from
   that sibling. This is what actually propagates the new roster: not a
   separate `device-announce` from the laptop, which would be redundant
   here and, more fundamentally, *couldn't* carry the authority a real
   rotation needs — only a trusted device's signed `from_prior` (which the
   laptop, freshly enrolled and untrusted, has no way to produce) makes a
   new Identity DID value legitimate to a sibling that doesn't already
   know it's coming. `device-announce` still exists for a narrower case:
   telling a specific sibling "I'm here" when it *missed* a fan-out it
   should have already gotten (e.g. it was offline, and later catches up
   via [`history-sync/1.0`](../../history-sync/1.0/readme.md) reconciling
   the roster as an ordinary collection) — not the normal path.
6. Every device that received the rotation (directly, as the reply to its
   own request; or via a `rotates: true` fan-out) now has the same updated
   roster and the same new Identity DID. Both the phone and the laptop can
   now independently receive as it — a contact's message, encrypted to
   every listed `keyAgreement` entry, reaches whichever of them is online,
   live, with no relay or handoff needed between them for ordinary
   delivery. The phone also includes the `from_prior` it just signed on its
   next outgoing message to each contact (or a dedicated one), per
   [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/):
   keep including it until a reply addressed to the new DID confirms the
   contact has switched over.
7. Months later, Alice's phone is stolen. From the laptop — now promoted to
   trusted, see Key Rotation — she sends a `device-revoke`:
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
   The laptop mints a **new** Identity DID document omitting the phone's
   `keyAgreement` (and, since the phone was trusted, its `authentication`)
   entry, signs `from_prior` with its *own* `authentication` key, and
   rotates every known contact onto it (see Key Rotation). Since there was
   no other sibling to fan this out to, that's the whole of it: the phone's
   copy of the old document's keys is now worthless — no sender still
   addressing the old Identity DID will keep doing so once contacts
   process the rotation, and the phone was never in possession of anything
   that decrypts content sent to the *new* one.

## Design By Contract

- **Why the keys are per-device, not shared: checked against the real spec
  text, not assumed by analogy.** An earlier draft of this protocol copied
  one shared keypair to every device, reasoning that "a DIDComm sender only
  ever uses the first `keyAgreement` entry it finds" — a claim about how a
  *single-recipient-oriented* resolver happens to behave, not something
  [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)
  itself requires. The spec's own text recommends the opposite as the
  default: encrypt to every `keyAgreement` entry a recipient's document
  lists. `wyvrn-didcomm`'s packaging implements exactly this now for a
  bare-DID recipient, so per-device keys need no special-casing on the
  sending side at all — from a sender's perspective, packing to the
  Identity DID looks exactly like packing to any other DID; the
  multiplicity is purely on the decrypting side.
- **How a device obtains its place in the Identity DID document is
  defined, not left open — see Basic Walkthrough steps 2-4.** The real
  [`out-of-band/2.0`](https://didcomm.org/out-of-band/2.0) protocol carries
  a QR-encoded invitation whose only job is establishing a route between
  the two devices, and this protocol's own `device-enroll-request`/
  `device-enroll-response` (see Message Reference) carry the new device's
  public key and the resulting document over the ordinary encrypted
  DIDComm connection that invitation leads to — no separate file format or
  transfer mechanism this protocol doesn't already speak. Physical
  possession of the displayed QR code is the trust basis, the same
  assumption Signal's and WhatsApp's own device-linking flows make.
- **Every device independently authenticates its own mediator registration
  as the Identity DID itself — there is no separate shared "control"
  identity.** This is what the mediator's own anti-hijack rule requires:
  a `recipient-update` claiming a given `recipient_did` is only honored
  when the caller is that same DID (or the DID's registration doesn't
  exist yet). A per-device control identity would fail this the moment a
  second device tried to register — the mediator would see a different
  claimed owner for the same `recipient_did` and reject it. Each device's
  own `keyAgreement` key, once listed in the Identity DID document, is
  what lets it authenticate as the Identity DID for exactly this purpose,
  with no separate credential needed.
- **Every roster change — enroll, revoke, promote, demote — is the same
  operation: mint a new Identity DID document and sign a `from_prior`.**
  Because `did:peer`'s DID value is a hash of its own document, there is no
  way to add or remove one `keyAgreement`/`authentication` entry without
  producing a new DID value. This protocol does not try to avoid that cost;
  it reuses one mechanism (`from_prior` rotation, see Key Rotation) for
  every case that needs it, rather than defining a separate one per case.
- **Only a trusted device can perform a roster change**, because doing so
  requires signing `from_prior`, which requires an `authentication` key —
  the one thing an ordinary enrolled-but-untrusted device never holds. An
  enroll request or promotion request that reaches an untrusted sibling has
  nothing it can do with it beyond relaying it to a trusted one.
- **No distributed consensus, same as `group-chat/1.0`.** Two trusted
  devices rotating at close to the same time (e.g. enrolling two different
  new devices concurrently) can produce two divergent new Identity DID
  documents, each missing the other's change — this protocol does not
  attempt to detect or resolve that race at the protocol level; see
  Security for why reacting quickly still matters more than preventing it.
- **A device that misses announces** can fall behind the real roster with
  no way to self-heal from this protocol alone — there is no `roster`
  snapshot request/response defined here. In practice this is expected to
  be recovered by treating the device roster as just another
  [`history-sync/1.0`](../../history-sync/1.0/readme.md) collection
  (`collection_id: "devices"`) and letting that protocol's periodic
  reconciliation catch a stale roster the same way it catches stale
  message history, rather than duplicating a second bespoke snapshot-fetch
  mechanism here.
- **What contacts actually see as "the DID" is the Identity DID, across
  its whole rotation history.** `did:peer:4` stays immutable per rotation,
  but the *identity* it names isn't tied to any one physical device or any
  one document value, so losing any single trusted device — including the
  one that founded it — is recoverable via Key Rotation as long as at
  least one other trusted device survives it. The only case this doesn't
  cover is an identity that only ever had one trusted device: there is no
  one left who can sign a rotation on its behalf, which is an inherent
  limit of having no redundant trust, not a gap in this protocol (see
  Future Considerations).
- **The mediator needs one real capability beyond a single-device identity:
  several devices independently reachable at one shared recipient DID.**
  Live delivery already supports this (`wyvrn-mediator-protocols`'
  `WsConnStore`/`deliver_or_queue` fan out to every currently-registered
  live connection for a DID, not just the first). Queued delivery
  (`messagepickup/3.0`) is scoped narrower for now: this protocol accepts
  today's single-shared-queue behavior for anything that arrives while
  every device is offline (whichever device polls first gets it), and
  relies on `history-sync/1.0` for every other device to catch up —
  a deliberate scope limit, not an assumption about what the mediator
  guarantees.

## Key Rotation

Rotation is not a rare, special-case recovery path here — it's the
mechanism behind every roster change (see Design By Contract). It reuses
the enrollment exchange rather than defining a new one:

1. Any trusted device mints a **new** Identity DID document: the current
   roster's `keyAgreement` entries, plus/minus whatever this rotation
   changes (a new device's key added; a revoked device's key, and if it
   was trusted its `authentication` key, removed; a promoted device's new
   `authentication` key added; a demoted device's `authentication` key
   removed).
2. It signs a `from_prior` transition (per
   [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/):
   `sub` the new Identity DID, `iss` the old one) using **its own**
   `authentication` key — a key the departing document actually lists,
   which is all the spec requires — and includes it on the next message
   (or a dedicated one) to every known contact, letting each contact verify
   continuity and switch over to the new DID for the same relationship.
3. It sends every *other* currently-enrolled sibling device (trusted or
   not) a `device-enroll-response` with `rotates: true`, carrying the new
   Identity DID and the updated roster — not a private key, since none
   needs to move: each sibling already holds its own `keyAgreement` key
   (and, if trusted, its own `authentication` key), both still valid
   entries in the new document if this rotation didn't remove them.
4. Each device that receives a rotating `device-enroll-response`
   `recipient-update`s the new Identity DID at the mediator (its existing
   `keyAgreement`/`authentication` keys, unchanged, now just live under a
   new DID value), then issues a removal `recipient-update` against the
   old one. Its own Device DID is untouched throughout — only the shared
   Identity layer's current DID value changes.
5. Once every remaining device has rotated, the old Identity DID has no
   recipients left registered under it and can simply be abandoned — no
   explicit "terminate" step needed.

**Promotion and demotion** use the exact same mechanism, with no key ever
changing hands: to be promoted, a device generates its own `authentication`
keypair locally and sends only the *public* half to a trusted sibling as a
`device-promote-request` (see Message Reference). Unlike every other
roster change, this one does not take effect automatically on receipt —
granting trust is a one-way door (a trusted device can single-handedly
enroll, revoke, or promote/demote anyone), so the receiving trusted
device's own user explicitly accepts or denies it first. A
`device-promote-response` (see Message Reference) tells the requester the
outcome either way: on acceptance, the trusted sibling performs steps 1-3
above, adding the new `authentication` entry — its rotating
`device-enroll-response` fan-out is what actually confirms the promotion to
every device, including the newly-promoted one, with the direct
`device-promote-response` only letting the requester's own UI react
immediately rather than waiting on that fan-out to arrive; on denial,
nothing is minted or rotated at all, and the requester drops the
`authentication` keypair it generated, since it was never going to be
listed anywhere. Demotion needs no request at all: any trusted device can
decide to demote another (or itself) unilaterally, the same way revocation
needs none — it's initiated directly with steps 1-3, dropping only the
target's `authentication` entry (its `keyAgreement` entry, and its content
access, is untouched).

This needs no new mediator capability beyond what enrollment already
needs — registering an additional recipient DID under an existing
mediation relationship is ordinary `coordinate-mediation/3.0`. What it does
need, and doesn't get automatically, is **speed**: see Security for why a
slow rotation loses its entire point.

## Security

- **A revoked device is cut off from both content and rotation authority
  the instant the next document is published — there is nothing further
  to contain.** Unlike a shared-key design, a revoked device's own keys are
  simply absent from the new Identity DID document: it cannot decrypt
  anything a sender addressing the new document produces, and (if it was
  trusted) it cannot sign a `from_prior` any contact still has reason to
  trust. What it *can* still do is decrypt anything already encrypted to
  the *old* document by a sender that hasn't yet processed the rotation —
  bounded by how many senders haven't caught up yet, not by anything the
  revoked device does afterward.
- **A rotation is a race only for messages already in flight to the old
  document, not for the revoked device's own future access.** Because the
  revoked device's key isn't in the new document at all, it has no way to
  decrypt anything encrypted under it, regardless of timing. The actual
  risk is narrower than under a shared-key design: a sender who hasn't yet
  seen the rotation keeps addressing the old document for a while, and
  those specific messages remain readable by whatever held the old
  document's keys — which is why revoking-and-rotating promptly still
  matters, just for a smaller and more bounded reason than "the whole
  identity is exposed until this happens."
- **Only a trusted device can forge a roster change, and only within the
  bound of what its own `authentication` key can sign.** A compromised
  *untrusted* device can decrypt real content (it holds a valid
  `keyAgreement` entry) but cannot mint a valid rotation, enroll another
  device, or revoke anyone — it has no `authentication` key to sign with.
  This is why promotion is a deliberate, explicit step rather than
  something every enrolled device gets by default.
- **Losing the last *trusted* device is unrecoverable via this protocol
  alone, even if untrusted devices survive** — none of them can sign a
  rotation. This is different from, and narrower than, losing the last
  *enrolled* device entirely (which is unrecoverable under any design);
  see Future Considerations.

## Message Reference

### `device-enroll-request`

Sent by an unenrolled device to an already-enrolled, trusted one, over the
connection established by scanning that device's `out-of-band/2.0`
invitation (see Basic Walkthrough) — from the unenrolled device's own
freshly-generated Device DID, requesting to be enrolled.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device, same meaning as `device-announce`'s field of the same name. |
| `device_did` | string | The requesting device's own independently-generated Device DID — not yet registered with the mediator; that happens after this exchange completes. |
| `key_agreement_public` | string | The requesting device's own, independently-generated `keyAgreement` public key, multikey-encoded (the same encoding a `keyAgreement` entry's own `publicKeyMultibase` uses) — the one it will keep using for the rest of its enrolled life. Never a private key; the requesting device already holds the matching private half locally. |

### `device-enroll-response`

Sent in reply (`thid` set to the request's `id`), encrypted specifically to
the requesting device's `device_did` — never broadcast, never sent
unprompted. Also reused, unprompted, for Key Rotation (see there) — sent to
every other currently-enrolled sibling whenever a trusted device mints a
new Identity DID document, in which case there is no corresponding
`device-enroll-request` and `thid` is absent.

| Field | Type | Description |
|---|---|---|
| `identity_did` | string | The new Identity DID this response is establishing (or rotating to). |
| `mediator_did` | string | The mediator to register with — needed by a newly-enrolling device, which has no prior mediation relationship for the Identity DID yet. |
| `from_prior` | string | A signed `from_prior` JWT (per [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)) naming the immediately-prior Identity DID this one supersedes. Absent only for a founding device's very first document, which supersedes nothing. |
| `roster` | array of object | The sender's current roster (after this change), `{ device_id, device_did, key_agreement_public, authentication_public?, trusted }` per entry — every device's own *public* keys, never a private one, so the receiving device can itself mint a future rotation (see Key Rotation: any trusted device can do this, not just whichever one enrolled or revoked last) without a separate roster-fetch mechanism. |
| `rotates` | boolean | `false`/absent for ordinary enrollment of the device this response is addressed to. `true` means this response is Key Rotation fan-out to an *already*-enrolled sibling — it keeps its existing `device_did` and its own `keyAgreement`/`authentication` keys (if still listed in `roster`), and only needs to re-`recipient-update` onto the new `identity_did`. |
| `rotation_seq` | integer | How many roster-changing rotations the sender's identity has gone through, counting this one — `1` for the very first (an identity's founding document has no rotation at all, so there's nothing to number before it). A receiving device that already has an equal-or-higher `rotation_seq` recorded discards this message's `roster` and `identity_did` entirely rather than applying them. This exists because Identity DID *values* have no inherent ordering (each is an unpredictable hash of its own document), so without a monotonic counter, several rotations fanning out in quick succession — each an independent per-sibling send, not a single broadcast — can arrive out of order and let an older one silently resurrect a device state a newer one already superseded (e.g. a stale enrollment notice re-adding a device a subsequent revoke had just dropped). Absent only from messages predating this field; a receiver should treat that as "always apply" for backward compatibility, not as automatically stale. |

No field in this message is ever a private key. The single most sensitive
value an earlier draft of this protocol transmitted no longer needs to be
transmitted at all.

### `device-announce`

Sent by a newly enrolled device to every device in the roster it was given
at enrollment time; sent by an already-enrolled device to any sibling it
later learns about (e.g. via `history-sync/1.0` roster reconciliation)
that it has not yet announced itself to.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device (e.g. `"phone"`, a user-chosen name, or a generated id) — display-only, not used for addressing. |
| `device_did` | string | This device's own independently-generated Device DID, already registered with the mediator via `recipient-update`. |
| `trusted` | boolean | Whether this device currently holds an `authentication` entry in the Identity DID document. |
| `announced_at` | integer | Unix epoch milliseconds this device considers itself enrolled as of. |
| `capabilities` | array of string | Optional. What this device can do beyond the symmetric default every device has today — e.g. `"live-push"` (holds a live WebSocket connection to the mediator), `"poll-only"` (never does, relies entirely on periodic pickup). Absent means "treat as fully symmetric with every other device," true for every device this version of `wyvrn-chat` actually produces; the field exists so a future device that's meaningfully different (e.g. a headless relay with no UI) can say so without a protocol version bump. |
| `retention` | string | Optional. `"unbounded"` or `"bounded"`, mirroring this device's own [`history-sync/1.0`](../../history-sync/1.0/readme.md) retention policy — lets a sibling's `backfill-request` skip known-bounded devices instead of asking and getting nothing back. Absent is treated as `"bounded"` (the conservative assumption). |

### `device-revoke`

Sent to every other known device announcing that one device should no
longer be considered part of the identity. Expected to be followed shortly
by a rotating `device-enroll-response` from the sender (see Key Rotation)
— `device-revoke` itself only updates roster knowledge, it doesn't perform
the rotation. Only meaningful coming from a trusted device — see Design By
Contract. Never sent to the revoked device itself — telling it it's been
cut off accomplishes nothing security-relevant (the rotation is what
actually cuts it off), and a lost-or-compromised device is exactly the one
this protocol has no reason to trust with advance notice.

| Field | Type | Description |
|---|---|---|
| `device_did` | string | The `device_did` (from that device's own `device-announce`) being revoked. |
| `reason` | string | One of `"lost"`, `"compromised"`, `"replaced"`. Informational only — every reason requires the same key rotation, since (see Security) the revoked device's own key is what needs to stop being listed, regardless of why. |

### `device-promote-request`

Sent by an already-enrolled, untrusted device to a trusted sibling it
chooses, asking to be promoted. Carries only a public key: the requesting
device generates its own `authentication` keypair locally first (the same
way a founding device or a newly-enrolling one generates its `keyAgreement`
keypair — see Key Rotation) and hands over only the public half, exactly
like `device-enroll-request`'s own `key_agreement_public`. Unlike
`device-enroll-request`, this does not take effect on receipt — see
`device-promote-response` below and Key Rotation's own note on why
promotion specifically gets a human accept/deny step the other roster
changes don't.

| Field | Type | Description |
|---|---|---|
| `authentication_public` | string | The requesting device's own, independently-generated `authentication` public key, multikey-encoded. Never a private key; the requesting device already holds the matching private half locally. |

### `device-promote-response`

Sent by the trusted device a `device-promote-request` was addressed to,
once its own user has explicitly accepted or denied it. On acceptance,
sent alongside (not instead of) the usual rotating `device-enroll-response`
fan-out (see Key Rotation) — that fan-out is still what actually confirms
the promotion to every device, this message just lets the requester's own
UI react the moment its own request is resolved rather than waiting on
that fan-out to arrive. On denial, nothing else follows: no document is
minted, and the requester is expected to drop the `authentication` keypair
it generated, since it was never going to be listed anywhere.

| Field | Type | Description |
|---|---|---|
| `accepted` | boolean | Whether the promotion was granted. |

## Implementations

Name / Link | Implementation Notes
--- | ---
_(none yet)_ | Proposed alongside [`history-sync/1.0`](../../history-sync/1.0/readme.md) for [`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat); not yet implemented.

## Endnotes

### Future Considerations

- **An identity with only ever one trusted device has no recovery if that
  device is lost**, even if other, untrusted devices remain enrolled — none
  of them can sign a rotation. The practical mitigation is entirely UX:
  encourage promoting a second device early, rather than trying to solve
  this cryptographically.
- **Making the required key rotation actually fast in practice** (Security)
  — e.g. a mediator-observable "this device hasn't been seen in N days,
  consider revoking" nudge, or a dead-man's-switch style automatic
  rotation, so a compromised device's exposure window is bounded by
  something other than how quickly a person happens to notice.
- A push-based `roster` snapshot response, if `history-sync/1.0`
  reconciling the device roster as an ordinary collection proves too slow
  to recover from a large miss in practice.
- Letting `device-enroll-request` carry a piggybacked `history-sync/1.0`
  request (e.g. "also send me the last 30 days of every conversation"),
  instead of the new device always waiting for a separate reconciliation
  pass after enrollment completes — today a real but likely small latency
  gap between "enrolled" and "caught up."
