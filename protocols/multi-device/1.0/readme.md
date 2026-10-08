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
| Receive a `device-enroll-response` (`rotates: true`), signed by the Identity DID it is on and next in order | n/a (not addressed to an unenrolled device) | adopts the new Identity DID document and its roster (removing any device no longer listed), re-`recipient-update`s (add new, remove old) | same, and re-evaluates its own trust (a rotation may promote or demote it) |
| Receive one that is properly signed but ahead of the next in order | n/a | holds it, sends a `device-rotation-request` | same |
| Receive a `device-enroll-request` answering a live invitation it issued | n/a | no-op (cannot mint a rotation) | holds it for its user to accept (mints and sends the rotation) or deny (`device-enroll-deny`) |
| Receive a `device-rotation-request` | n/a | no-op (cannot sign a roster change) | re-sends, freshly signed, each later roster change it still has and was trusted for |
| Receive `device-announce` | no-op (not enrolled, nothing to update) | stays in state, roster gains an entry | stays in state, roster gains an entry |
| Receive `device-revoke` for another device, from a trusted device | no-op | stays in state, roster loses an entry, expects a rotating `device-enroll-response` to follow shortly | same, and may itself perform the rotation if no other trusted device does first |
| Receive `device-revoke` for *this device's own* Device DID | no-op | this device should stop presenting itself as enrolled — see Security | same |
| Receive a `device-remint` keeping the sender's `keyAgreement` key, vouched for by an enrolled Device DID | no-op | stays in state, the roster entry moves to the new Device DID | same |
| Receive a `device-remint` with a new `keyAgreement` key, vouched for by an enrolled Device DID | no-op | no-op (cannot mint a rotation) | mints and sends the rotation listing the new Device DID and key |

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
   talking to me," carrying no key material itself. Its `id` is random,
   it carries an `expires_time` a few minutes out, and the phone remembers
   having issued it: it is what authorizes whoever answers it, once. The
   laptop scans it and sends a `device-enroll-request`, mediated and
   sender-authenticated like any ordinary DIDComm v2 message, from its new
   Device DID (from step 2) to the phone's, quoting the invitation's `id`
   as its `pthid`:
   ```json
   {
     "id": "b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
     "type": "https://wyvrn.app/multi-device/1.0/device-enroll-request",
     "pthid": "9f8e7d6c-5b4a-3c2d-1e0f-a9b8c7d6e5f4",
     "body": {
       "device_id": "laptop",
       "device_did": "did:peer:4...laptop",
       "key_agreement_public": "z6LSb..."
     }
   }
   ```
   Possession of the displayed invitation is what gets a request
   considered — the same starting point Signal's and WhatsApp's
   device-linking flows have — but it is not the whole trust basis. The
   phone checks that the request answers an invitation it issued, that
   hasn't expired and hasn't been answered already, and then **shows the
   request to its own user** — "laptop wants to join this identity" —
   who accepts or denies it. Nothing is minted, and no reply is sent,
   until they do. The invitation is displayed where others may see or
   photograph it and carries the phone's Device DID in the clear, so
   neither knowing that DID nor having seen the code can be allowed to
   enroll a device unattended. A denied request gets a
   `device-enroll-deny`, so the laptop stops waiting. Only a **trusted**
   device can complete this exchange, since doing so mints a new Identity
   DID document and signs a `from_prior` — an enroll request that reaches
   an enrolled-but-untrusted sibling should be re-requested against a
   trusted one instead. Once accepted, the phone mints a new Identity DID
   document — every currently-listed `keyAgreement` entry plus the
   laptop's new public one, `authentication` entries unchanged — and
   replies with a `device-enroll-response`, sender-authenticated from its
   own Device DID and encrypted specifically to the laptop's new one (the
   laptop accepts this reply only from the Device DID the invitation
   named):
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
   `device-enroll-response` body, with `rotates: true` and no `thid`
   (it isn't a reply to anything from that sibling), but sent as a
   **signed** message: `anoncrypt(sign(plaintext))` per DIDComm Messaging's
   Message Signing, whose `from` is the Identity DID being rotated *from*
   and whose signature is by the phone's `authentication` key in that
   document. That is what lets a sibling act on it: the signature covers
   the whole message — the new document, the sequence number, every
   roster entry — and proves a trusted device of the identity the sibling
   is already on authorized it. Which device relayed it proves nothing,
   and is not asked. This is what actually propagates the new roster: not a
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

**Replacing a Device DID** (a *remint*). A device may move to a new Device
DID, with `device-remint` (see Message Reference) telling its siblings, and
there are two cases, decided by whether its `keyAgreement` key changes:

- **New keys** (a *hard* remint — the device generates a new Device DID and a
  new `keyAgreement` key). The Identity DID document lists device keys, never
  Device DIDs, so only the key change makes this a roster change at all, and
  it is made like any other: a trusted device mints the new document itself
  with steps 1-3 above, sent from its old Device DID (the one its siblings
  still know). An untrusted device cannot; it moves to its new Device DID,
  keeps using its current `keyAgreement` key, and sends `device-remint` to
  **one** trusted sibling — the one with the lexically lowest Device DID, so
  that two trusted devices never each mint a different change with the same
  `rotation_seq` — which performs steps 1-3 for it without asking anyone
  (it changes nothing but that device's own keys, which that device alone
  holds). The device switches to its new `keyAgreement` key with the
  rotation that lists it, and until then sends `device-remint` again on
  every start.
- **Same keys** (a *soft* remint — the same keys minted into a new document,
  e.g. one written by a newer library with a different `accept` order, or
  through a mediator with a new routing DID; a `did:peer:4` is its whole
  document, so this gives a new Device DID). The current Identity DID
  document already lists the device's `keyAgreement` key, so there is
  nothing to sign or accept: the device sends `device-remint` to **every**
  sibling, and any device — trusted or not — moves that roster entry to the
  new Device DID. No rotation is minted, so several siblings handling the
  same notice cannot produce competing changes. (A trusted device whose
  *Identity* DID would also come out different under the newer document
  makes that an ordinary rotation instead.)

In both cases the new Device DID is registered with the mediator before
anything is sent from it, and the old one's registration is removed once
nothing will be sent to it.

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
- **A Device DID is not a secret, so nothing may rest on knowing one.**
  It is in every enrollment invitation, in the clear; every device ever
  enrolled knows every sibling's, including devices since revoked; the
  mediator holds it. A receiving device therefore decides who it is
  hearing from only by what vouches for a message, and what must vouch
  depends on the message:
  - A message nothing vouches for has no sender. DIDComm requires the
    plaintext `from` to match the encryption layer's `skid`
    ([Message Layer Addressing Consistency](https://identity.foundation/didcomm-messaging/spec/v2.1/#message-layer-addressing-consistency)),
    but an anonymously encrypted message has no `skid` to match, so its
    `from` is whatever its sender wrote. A receiver MUST treat such a
    message as having no `from` (and no `from_prior`) and MUST NOT act on
    it under this protocol.
  - A **roster change** (`device-enroll-response` with `rotates: true`)
    MUST be a signed message whose signer is an `authentication` key of
    the Identity DID the receiver is currently on. Sender authentication
    alone MUST NOT be accepted for it: that would show which device sent
    it, not that a trusted device authorized it.
  - **Every other message** MUST be sender-authenticated by a Device DID
    that is in the receiver's roster and has not been revoked. A
    signature MUST NOT be accepted in its place. The one message exempt
    from "in the roster" is `device-enroll-request`, which by nature
    comes from a device not yet enrolled, and is authorized by the
    invitation it answers instead. The other is `device-remint`, which
    comes from a Device DID nobody has heard of yet by design, and is
    authorized by its `from_prior`: signed by a Device DID that *is* in
    the roster (and not revoked), naming the sender as its successor.

  The same rule governs every protocol that runs over the Device DID
  channel, [`history-sync/1.0`](../../history-sync/1.0/readme.md)
  included.
- **A roster change is applied only in order, and only from the document
  the receiver is on.** Each one is numbered (`rotation_seq`) and signed
  as the Identity DID it rotates from, so a device on change *n* can act
  on change *n+1* and on nothing else. One that arrives ahead of the
  change it builds on MUST be held, not applied and not discarded, until
  the changes before it have been; the receiver asks for those with a
  `device-rotation-request`. A change signed by any other document is
  not an authority to this device no matter how it is numbered, which is
  what stops a validly signed message from an unrelated DID being taken
  for one of this identity's.
- **A verified roster change is the roster.** It lists every enrolled
  device, so a device it leaves out has been revoked and MUST be removed,
  whether or not a `device-revoke` ever arrived. A revoked device MUST
  NOT be re-added by anything other than a later verified roster change
  that lists it — not by its own `device-announce` (it is never told it
  was revoked, and carries on announcing itself), and not by a sibling's
  stale copy of the roster arriving through `history-sync/1.0`. Nothing a
  revoked device sends over the Device DID channel is acted on or
  answered.
- **How far behind a device may fall is bounded, deliberately.** Catching
  up means being sent each missed change, signed by a device that was
  trusted when it was made. Devices keep only their most recent changes
  to send again (an implementation choice; `wyvrn-chat` keeps 16), so
  that neither that log nor the chain a lagging device must verify grows
  with every device an identity has ever added or removed. A device
  further behind than its siblings' logs reach cannot be caught up and
  has to be enrolled afresh.
- **A same-key `device-remint` is the one roster edit no signed roster
  change makes.** It is safe to apply unsigned because it changes nothing
  the Identity DID document says — only which Device DID an already-listed
  key's device is reached at, attested by that device's own previous Device
  DID — and grants no trust. Its limit: a trusted device that has not yet
  received the notice and mints a roster change in the meantime lists the
  old Device DID, and a receiver applying that change moves the entry back.
  The notice is queued at the mediator for an offline sibling, so this
  takes a roster change made before the notice is picked up.
- **An invitation admits one device, once, briefly, and only with a
  person's say-so.** See Basic Walkthrough step 3. An implementation MUST
  NOT enroll a device on receipt of a `device-enroll-request` alone.
- **A device may only ask to have its own key listed.** A
  `device-promote-request` carries proof that the requester holds the
  private half of the `authentication` key it names; without it, an
  enrolled device could have a key belonging to someone else listed as a
  trusted one.
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
freshly-generated Device DID, requesting to be enrolled. Sender-authenticated.
Does not take effect on receipt: the receiving device holds it for its
own user to accept or deny.

The message's `pthid` header MUST be the `id` of the invitation being
answered (out-of-band/2.0's own correlation rule). The receiver MUST
ignore a request whose `pthid` is absent, names no invitation it issued,
names one past its `expires_time`, or names one a request has already
been received for.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | A human-meaningful local label for this device, same meaning as `device-announce`'s field of the same name. Shown to the person accepting the request; supplied by the requester, so it identifies nothing by itself. |
| `device_did` | string | The requesting device's own independently-generated Device DID — not yet registered with the mediator; that happens after this exchange completes. |
| `key_agreement_public` | string | The requesting device's own, independently-generated `keyAgreement` public key, multikey-encoded (the same encoding a `keyAgreement` entry's own `publicKeyMultibase` uses) — the one it will keep using for the rest of its enrolled life. Never a private key; the requesting device already holds the matching private half locally. |

### `device-enroll-response`

Sent two ways, which differ in how they are packed and what makes them
believable:

- **As the reply to an accepted `device-enroll-request`** (`thid` set to
  the request's `id`, `rotates: false`): sender-authenticated from the
  accepting device's own Device DID, encrypted specifically to the
  requesting device's `device_did`. The requesting device has no prior
  document to judge a signature by; it accepts this reply only from the
  Device DID its invitation named.
- **As a roster change** (`rotates: true`, no `thid`), sent to every
  other currently-enrolled sibling whenever a trusted device mints a new
  Identity DID document (see Key Rotation), and again on request (see
  `device-rotation-request`): a **signed** message,
  `anoncrypt(sign(plaintext))`, whose `from` is the Identity DID being
  rotated *from* and whose signer is an `authentication` key that
  document lists. A receiver MUST ignore one that is not signed, whose
  signer's DID is not the Identity DID the receiver is currently on (it
  holds such a message rather than discarding it if its `rotation_seq` is
  ahead — see below), or whose `from_prior` is not a valid rotation from
  that same DID to `identity_did`.

| Field | Type | Description |
|---|---|---|
| `identity_did` | string | The new Identity DID this response is establishing (or rotating to). |
| `mediator_did` | string | The mediator to register with — needed by a newly-enrolling device, which has no prior mediation relationship for the Identity DID yet. |
| `from_prior` | string | A signed `from_prior` JWT (per [DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/)) naming the immediately-prior Identity DID this one supersedes. Absent only for a founding device's very first document, which supersedes nothing. |
| `roster` | array of object | The sender's current roster (after this change), `{ device_id, device_did, key_agreement_public, authentication_public?, trusted }` per entry — every device's own *public* keys, never a private one, so the receiving device can itself mint a future rotation (see Key Rotation: any trusted device can do this, not just whichever one enrolled or revoked last) without a separate roster-fetch mechanism. |
| `rotates` | boolean | `false`/absent for ordinary enrollment of the device this response is addressed to. `true` means this response is Key Rotation fan-out to an *already*-enrolled sibling — it keeps its existing `device_did` and its own `keyAgreement`/`authentication` keys (if still listed in `roster`), and only needs to re-`recipient-update` onto the new `identity_did`. |
| `rotation_seq` | integer | Which roster change this is: how many the identity has gone through, counting this one — `1` for the very first (an identity's founding document has no rotation at all, so there's nothing to number before it). Roster changes are applied **strictly in this order**. A device that has applied change *n* applies *n+1* next and nothing else: it discards one numbered *n* or lower (already applied or superseded — including its `roster`, which would otherwise resurrect whatever a later change dropped), and **holds** one numbered above *n+1* until the changes before it have been applied, asking for them with a `device-rotation-request`. This exists because Identity DID *values* have no inherent ordering (each is an unpredictable hash of its own document), and each fan-out is an independent per-sibling send that can arrive out of order or not at all. The number orders changes; it does not authorize them — that is the signature's job, and a correctly numbered change signed by the wrong document is still ignored. |
| `device_did` | string | Roster changes only. The Device DID of the device sending this copy — covered by the signature, so a receiver that has to ask for missing changes knows one device able to supply them. |

No field in this message is ever a private key. The single most sensitive
value an earlier draft of this protocol transmitted no longer needs to be
transmitted at all.

### `device-enroll-deny`

Sent in reply (`thid` set to the request's `id`) to a `device-enroll-request`
the receiving device's user declined. Sender-authenticated. Empty body.
Nothing else follows: no document is minted and the roster is unchanged.
The requesting device stops waiting and discards the keys it generated
for the attempt.

### `device-rotation-request`

Sent by an enrolled device that is holding a roster change it cannot yet
apply, to ask for the ones it is missing — to the device named by the held
change's `device_did`, and to any trusted sibling it knows of.
Sender-authenticated; the sender must be in the receiver's roster like any
other.

| Field | Type | Description |
|---|---|---|
| `after_seq` | integer | The `rotation_seq` of the last roster change the sender has applied (`0` if none). |

A receiver that is trusted replies with a roster-change
`device-enroll-response` for each change it still has numbered above
`after_seq`, in order. Each is signed afresh by the replying device: a
signed message is encrypted to its one recipient and cannot simply be
passed on, and a device can only sign a change made while it was itself
trusted. Changes it cannot sign, or no longer has, it omits — another
sibling may be able to supply them. There is no "nothing to send" reply.

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
the rotation. It is advance notice, not the authority: a receiver MUST
ignore one whose sender is not a trusted device in its roster, and the
roster change that follows removes the device regardless (see Security:
a verified roster change is the roster). Never sent to the revoked device itself — telling it it's been
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
| `proof` | string | Proof of that: a JWT in the same form as `from_prior` (EdDSA, `iss`/`sub`/`iat`), signed with the private half of `authentication_public`, whose `iss` is that key's own `did:key` (`did:key:<authentication_public>`, `kid` `did:key:<authentication_public>#<authentication_public>`) and whose `sub` is the requesting device's Device DID. A receiver MUST ignore a request whose `proof` is absent, does not verify, is not issued under the `did:key` of exactly the key in `authentication_public`, or is not made out to the Device DID the request was sent from. |

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

### `device-remint`

Sent from a device's **new** Device DID, after it has registered that DID
with the mediator, to announce that it replaces the device's previous one
(see Key Rotation: Replacing a Device DID). Sent to every sibling when
`key_agreement_public` is the device's current `keyAgreement` key (a soft
remint), and to one trusted sibling — the one with the lexically lowest
Device DID — when it is a new one (a hard remint by an untrusted device).

| Field | Type | Description |
|---|---|---|
| `from_prior` | string | A JWT in the `from_prior` form ([DIDComm Messaging v2.1](https://identity.foundation/didcomm-messaging/spec/v2.1/), EdDSA, `iss`/`sub`/`iat`) whose `iss` is the device's previous Device DID, signed with an `authentication` key that DID's document lists, and whose `sub` is the Device DID the message is sent from. |
| `key_agreement_public` | string | The `keyAgreement` public key, multikey-encoded, the device is to be listed with in the Identity DID document: its current one (soft remint) or a new one it generated (hard remint). |

A receiver MUST ignore one whose `from_prior` is absent, does not verify,
does not name the sending Device DID as its `sub`, or whose `iss` is not an
enrolled, unrevoked device in its roster. Then:

- `key_agreement_public` equals the key the roster lists for that device:
  the receiver moves that device's roster entry to the new Device DID,
  keeping everything else about it (name, trust), and treats the previous
  Device DID as revoked (never re-added, never heard from again).
- Otherwise: a trusted receiver mints and sends the rotation listing the new
  Device DID and key in place of the old ones (Key Rotation steps 1-3);
  any other receiver ignores it.

A receiver whose roster already lists the sending Device DID has applied the
request before; a trusted one sends that device its latest roster change
again, for a device that missed it.

```json
{
  "type": "https://wyvrn.app/multi-device/1.0/device-remint",
  "id": "5b0c3e1a-6f2d-4d8e-9a71-3c4f2e8b9d10",
  "from": "did:peer:4zQmNewDeviceDid...",
  "to": ["did:peer:4zQmSiblingDeviceDid..."],
  "body": {
    "from_prior": "eyJ0eXAiOiJKV1QiLCJhbGciOiJFZERTQSJ9.eyJpc3MiOiJkaWQ6cGVlcjo0elFtT2xkRGV2aWNlRGlkLi4uIiwic3ViIjoiZGlkOnBlZXI6NHpRbU5ld0RldmljZURpZC4uLiIsImlhdCI6MTc5MTQzNDI3Nn0.signature",
    "key_agreement_public": "z6LSphoneKeyAgreementKey..."
  }
}
```

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | `src/handlers/multiDevice/multiDeviceHandler.ts`; who is heard on the Device DID channel is enforced in `src/services/multiDevice/deviceChannelGuard.ts`. Keeps its 16 most recent roster changes for `device-rotation-request`; invitations last 10 minutes. Reminting is under Settings → Developer: *soft* and *hard* (`softRemintDeviceDid`/`remintDeviceDid` in `src/worker/agentWorker.ts`). Every start re-sends `recipient-update` for the device's own Device DID, and for the Identity DID only while its document lists that device's key alone — a revoked device is never told it was revoked, and re-adding a shared Identity DID would undo the removal its revoking sibling made.

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
