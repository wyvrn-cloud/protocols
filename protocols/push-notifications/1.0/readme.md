---
title: Push Notifications
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/push-notifications/1.0
status: Proposed
summary: Lets a client register its Web Push subscription with its own mediator, control-plane style like coordinate-mediation/3.0, so the mediator can wake a fully closed/killed client with a generic notification when it queues a message for it instead of delivering it live.
tags:
  - notifications
  - mediation
authors:
  - name: wyvrn
---

## Summary

Push Notifications lets a client register a
[Web Push](https://www.w3.org/TR/push-api/) subscription with its own
mediator — a control-plane protocol in the same family as
[`coordinate-mediation/3.0`](https://didcomm.org/coordinate-mediation/3.0),
not a messaging protocol. It exists so a mediator that ends up queuing a
message instead of delivering it live (see
[Connectivity](#connectivity)) can wake a client that is fully closed or
killed, not just backgrounded, with a generic "you have a new message
waiting" push — never real message content, sender identity, or any other
plaintext the push transport (a browser vendor's push service) could see.

This document is a **design only**; nothing here is implemented yet in the
wyvrn ecosystem. See `wyvrn-chat`'s
[`useBackgroundNotifications`](https://github.com/wyvern-cloud/wyvrn-chat/blob/main/src/hooks/useBackgroundNotifications.ts)
for the already-implemented, simpler case this protocol is *not*
about — a notification shown while the client process is still running,
just not focused, which needs no server-side changes at all.

## Motivation

`wyvrn-chat`'s existing delivery model (live WebSocket + periodic HTTP
pickup, see its own CLAUDE.md) only works while the client's process is
actually running somewhere — a browser tab open, or an installed PWA the
OS hasn't fully suspended. A client that is genuinely closed (tab closed,
app force-quit, phone screen off long enough for the OS to kill background
work) never polls and never holds a live WebSocket connection, so it has
no way to learn a message arrived until the user manually reopens it. Real
background push — the platform waking the client's service worker even
when nothing else is running — is the only way to close that gap, and it
needs genuinely new infrastructure: a way for the *mediator* (the one
party that already knows when it's had to queue something instead of
delivering it) to trigger that wake-up. This protocol is the minimal
control-plane piece of that: how a client tells its mediator where and how
to reach it via Web Push in the first place.

## Roles

- `client`: the DIDComm agent that wants to be woken via push when its
  mediator queues a message for it.
- `mediator`: the agent already mediating for that client (per
  `coordinate-mediation/3.0`), which additionally holds a Web Push
  subscription for it.

A client always registers with the same mediator it already has a
`coordinate-mediation/3.0` relationship with — this protocol adds no new
trust relationship, only new information shared within an existing one.

## Connectivity

Point-to-point, mediated, exactly like any other DIDComm v2 exchange
between a client and its own mediator. The actual push send this protocol
enables is **not** a DIDComm message at all — it goes over the ordinary
[Web Push protocol](https://datatracker.ietf.org/doc/html/rfc8030) from
the mediator's push-sending logic directly to the browser vendor's push
service (e.g. FCM, Mozilla's push service), authenticated with the
mediator's own [VAPID](https://datatracker.ietf.org/doc/html/rfc8292)
keypair. It is triggered specifically on the path where the mediator would
otherwise only *queue* a message for later pickup — a message delivered
live over an already-open WebSocket connection needs no wake-up push,
since the client is demonstrably already reachable.

## States

| State | Meaning |
|---|---|
| `unsubscribed` | The mediator holds no Web Push subscription for this client. |
| `subscribed` | The mediator holds a current Web Push subscription for this client, used to wake it on the next queued (not live-delivered) message. |

| Event | `unsubscribed` | `subscribed` |
|---|---|---|
| Receive `push-subscribe` | → `subscribed` | → `subscribed` (replaces the stored subscription — see Design By Contract on rotation) |
| Receive `push-unsubscribe` | no-op | → `unsubscribed` |
| Push send permanently rejected by the push service (e.g. `410 Gone`) | n/a | → `unsubscribed` (mediator-side cleanup, not itself a DIDComm message — see Design By Contract) |

## Basic Walkthrough

Alice's client has an existing `coordinate-mediation/3.0` relationship
with her mediator, and has just registered a service worker with a Web
Push subscription (`PushManager.subscribe()`, using the mediator's public
VAPID key, itself discoverable the same way the rest of `wyvrn-chat`
discovers mediator-published values — see `discoverMediator.ts`).

1. Alice's client sends her mediator a `push-subscribe`:
   ```json
   {
     "id": "b6f0a9b2-2f1a-4b6d-9b7b-2e9a2b1c4d3e",
     "type": "https://wyvrn.app/push-notifications/1.0/push-subscribe",
     "body": {
       "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
       "keys": {
         "p256dh": "BNcRd...",
         "auth": "tBHI..."
       }
     }
   }
   ```
2. The mediator stores it (see [Design By Contract](#design-by-contract)
   on the storage shape) and replies:
   ```json
   {
     "id": "1e0f8b2b-6f7f-4a34-8e8a-6f0f5b2b1e0f",
     "type": "https://wyvrn.app/push-notifications/1.0/push-subscribe-response",
     "thid": "b6f0a9b2-2f1a-4b6d-9b7b-2e9a2b1c4d3e",
     "body": { "result": "success" }
   }
   ```
3. Later, the mediator has a message queued for Alice (her client isn't
   live-connected) and, instead of only waiting for her next periodic
   pickup poll, also sends a Web Push message to the stored subscription
   with a fixed, generic payload — no sender, no content, not even a
   conversation id:
   ```json
   { "reason": "new-message" }
   ```
4. The browser wakes Alice's service worker (even if no tab/app instance
   is otherwise running) with that payload. The `push` event handler
   shows a generic OS notification ("New message" / "Open wyvrn-chat to
   view it") — it cannot decrypt or otherwise identify anything, since the
   service worker never has access to the unlocked DIDComm identity (see
   [Security](#security)). Opening the notification focuses/opens the app,
   which then unlocks normally and does a real pickup, exactly as if the
   user had opened it on their own.
5. If Alice later disables notifications or uninstalls the app, her client
   sends `push-unsubscribe`:
   ```json
   {
     "id": "9d8c7b6a-5e4f-3d2c-1b0a-9f8e7d6c5b4a",
     "type": "https://wyvrn.app/push-notifications/1.0/push-unsubscribe"
   }
   ```
   and the mediator replies with `push-unsubscribe-response` and deletes
   the stored subscription.

## Design By Contract

- **One subscription per client DID, last-write-wins.** A second
  `push-subscribe` from the same DID (e.g. re-registering after a browser
  clears its subscription, or switching devices) replaces whatever was
  stored, rather than accumulating multiple targets — this version pushes
  to exactly one endpoint per client, not a fan-out to every device a
  DID's identity might be used from. Multi-device fan-out is a natural
  extension once combined with
  [`multi-device/1.0`](../../multi-device/1.0/readme.md), but is out of
  scope here.
- **No delivery confirmation for the push itself.** `push-subscribe`/
  `push-unsubscribe` get DIDComm-level acks (`*-response` messages), but
  the actual Web Push send triggered later has no such round trip back to
  the client over DIDComm — the mediator only knows what the push
  service's HTTP response to *it* says (success, or a rejection like `410
  Gone` meaning the subscription is dead).
- **Mediator-side cleanup on permanent rejection is not itself a DIDComm
  event.** When a push send comes back `410 Gone` (or similar), the
  mediator should drop the stored subscription so it stops trying — but
  it has no channel to tell the client that happened except the client
  noticing (on its own initiative) that push wake-ups have silently
  stopped, and re-subscribing. A future version could define a way to
  surface that state on request (mirroring `recipient-query` in
  `coordinate-mediation/3.0`), but doesn't yet.
- **Only triggered on the queue path, never on live delivery.** A message
  delivered directly over an already-open live connection (see
  `wyvrn-mediator`'s `deliver_or_queue`) never triggers a push send — doing
  so on every message regardless of live status would wake a
  fully-foregrounded client's OS-level push machinery for no reason, and
  would defeat the purpose (the client is already receiving it).
- **New non-protocol infrastructure this implies, not covered by the wire
  format above:**
  - A VAPID keypair configured on `wyvrn-mediator-service`, analogous to
    (but distinct from) the mediator's own DIDComm identity keys — VAPID
    authenticates the mediator to push *services*, not to DIDComm peers.
  - A new `push_subscription` table in `wyvrn-mediator-storage-sea`,
    following the same one-row-per-owner shape already used for
    `mediator_identity` and the existing recipient-registration table:
    keyed on the client's DID, storing `endpoint`/`p256dh`/`auth`.
  - The actual Web Push send call, added specifically to the
    queue-not-live-deliver branch of `deliver_or_queue`.
  - The client-side service worker's `push` event handler (`self.addEventListener('push', ...)`),
    showing a generic notification via `registration.showNotification()`
    — the same API `useBackgroundNotifications.ts` already uses for the
    backgrounded-tab case, just triggered by a different event source.

## Security

- **The push payload must never contain real message content, sender
  identity, or conversation identifiers** — only a fixed, generic trigger.
  The [Web Push encryption spec](https://datatracker.ietf.org/doc/html/rfc8291)
  does protect a payload's confidentiality in transit from the push
  service itself, but this protocol deliberately doesn't rely on that as
  its only safeguard: the payload is generic regardless, so even a
  misconfigured or compromised push-sending path leaks nothing beyond
  "some client got a wake-up."
- **A Web Push subscription (`endpoint` + `keys`) is itself
  capability-bearing** — whoever holds it can send that browser a push
  message. It must only ever travel over the client's already-encrypted,
  already-authenticated DIDComm channel to its own mediator (exactly as
  `push-subscribe` does here), never over an unauthenticated side channel.
- **The service worker cannot decrypt anything on push.** It runs without
  access to the unlocked DIDComm identity (which lives behind
  PIN/WebAuthn-gated `crypto.subtle` unwrapping in the main app, see
  `wyvrn-chat`'s vaultService) — this is a deliberate consequence of the
  existing key-protection design, not something this protocol works
  around. A push notification can therefore only ever say "something
  happened, go open the app," never anything about what.
- **A malicious mediator already sees when it queues a message for a
  client** (it has to, in order to queue it) — this protocol gives it no
  new information about the client it didn't already have as their
  mediator. What it does newly grant the mediator is the *ability to wake
  the client's device* at will (any time, for any or no queued message),
  which a compromised or malicious mediator could abuse as a denial-of-
  service/annoyance vector against the client. This is a real, accepted
  trade-off of opting into push wake-ups at all, not something this
  protocol's design can eliminate.

## Message Reference

### `push-subscribe`

Sent by the `client` to register or replace its Web Push subscription.

Message Type URI: `https://wyvrn.app/push-notifications/1.0/push-subscribe`

| Field | Type | Description |
|---|---|---|
| `endpoint` | string | The push service URL from `PushSubscription.endpoint`. |
| `keys.p256dh` | string | The subscription's public key, base64url-encoded, from `PushSubscription.getKey('p256dh')`. |
| `keys.auth` | string | The subscription's auth secret, base64url-encoded, from `PushSubscription.getKey('auth')`. |

### `push-subscribe-response`

Sent by the `mediator` in reply to `push-subscribe`, threaded via `thid`.

Message Type URI: `https://wyvrn.app/push-notifications/1.0/push-subscribe-response`

| Field | Type | Description |
|---|---|---|
| `result` | string | One of `success`, `client_error`, `server_error` — mirrors `coordinate-mediation/3.0`'s `recipient-update-response` result vocabulary. |

### `push-unsubscribe`

Sent by the `client` to remove its stored subscription. No body — the
subscription being removed is always the sender's own, identified by the
envelope `from`.

Message Type URI: `https://wyvrn.app/push-notifications/1.0/push-unsubscribe`

### `push-unsubscribe-response`

Sent by the `mediator` in reply to `push-unsubscribe`, threaded via `thid`.

Message Type URI: `https://wyvrn.app/push-notifications/1.0/push-unsubscribe-response`

| Field | Type | Description |
|---|---|---|
| `result` | string | One of `success`, `client_error`, `server_error`. |

## Implementations

Name / Link | Implementation Notes
--- | ---
_None yet_ | Design-only at this time — see [Summary](#summary).

## Endnotes

### Future Considerations

- Multi-device fan-out (one push subscription per device, not per DID),
  once combined with [`multi-device/1.0`](../../multi-device/1.0/readme.md).
- A `push-status-query`/response pair mirroring `recipient-query` in
  `coordinate-mediation/3.0`, so a client can proactively notice its
  subscription was dropped mediator-side instead of only inferring it from
  silence.
- Per-conversation push preferences (e.g. mute a specific contact/group
  from waking the device, while still receiving it on next open).
