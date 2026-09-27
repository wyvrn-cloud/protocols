---
title: Push Notifications FCM
publisher: Aries community (Hyperledger/OpenWallet Foundation)
license: Apache-2.0
piuri: https://didcomm.org/push-notifications-fcm/1.0
status: Adopted
summary: An adopted protocol (Aries RFC 0734), not wyvrn-authored -- lets a client register a Firebase Cloud Messaging device token with its own mediator, so the mediator can wake a fully closed/killed native mobile app via Firebase when it queues a message instead of delivering it live. Covers Android and iOS both, since Firebase relays an FCM-registered iOS token to APNs internally.
tags:
  - notifications
  - mediation
  - mobile
authors:
  - name: Aries community
    url: https://github.com/hyperledger/aries-rfcs/tree/main/features/0734-push-notifications-fcm
---

## Summary

This is **not a wyvrn-authored protocol** -- per this workspace's own convention of
checking for an existing protocol before inventing another custom one (see
`multi-device/1.0`/`history-sync/1.0`'s own precedent), the native-mobile-push half
of the Tauri native-builds plan's Part 6 adopts
[Aries RFC 0734](https://github.com/hyperledger/aries-rfcs/tree/main/features/0734-push-notifications-fcm),
`push-notifications-fcm/1.0`, as-is, rather than extending wyvrn's own
[`push-notifications/1.0`](../../push-notifications/1.0/readme.md) (a Web Push/VAPID
design, scoped to the browser PWA build only -- see that document's own README) with
ad hoc platform fields.

**A precision worth stating plainly**: this specific protocol is *not* actually
present in the current [didcomm.org](https://didcomm.org) registry this repo's own
README points at (checked directly against the local clone's
`site/content/protocols/` listing -- it isn't there). It comes from the older,
separate Aries RFCs catalog instead, which happens to also mint `didcomm.org/...`
PIURIs by long-standing convention predating the newer registry site. The PIURI
below is real and already used in production by the Credo reference implementation
(confirmed directly from its source, not assumed) -- it just isn't the *same*
registry wyvrn-protocols' own README describes checking first.

Verified directly against a real, working reference implementation --
[`didcomm-mediator-credo`](https://github.com/openwallet-foundation/didcomm-mediator-credo),
the OpenWallet Foundation's Credo-based mediator -- not just the RFC text. Its
`@credo-ts/didcomm-push-notifications` package implements exactly this shape: one
`set-device-info` message carrying a nullable `device_token`/`device_platform` pair
(sending both `null` unregisters -- no separate unsubscribe message needed), a
`get-device-info`/`device-info` query/response pair, and a `problem-report`. Records
are keyed by the client's own connection (the direct analog of `recipient_did` in
wyvrn-mediator's `RegistrationStore`), and the mediator sends via Firebase Cloud
Messaging as the *sole* backend for both Android and iOS -- an iOS device token
registered with FCM (via Firebase's own iOS SDK) gets relayed to APNs by Firebase
internally, so the mediator only ever calls one API
(`admin.messaging().send({ token, ... })` in Credo's own Node implementation)
regardless of platform, never a separate direct-APNs client.

wyvrn-mediator implements the mediator role of this same protocol in Rust: a
`fcm_device` table (`wyvrn-mediator-storage-sea`, one row per `recipient_did`,
mirroring Credo's own `DidCommPushNotificationsFcmRecord`), `set-device-info`/
`get-device-info`/`device-info` handlers in `wyvrn-mediator-protocols`, and an FCM
HTTP v1 sender (a Google service-account JWT signed and exchanged for an OAuth2
access token, then a plain `reqwest` POST to
`https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`) invoked from
`deliver_or_queue`'s queue-fallback branch -- never on the live-delivery path, the
same gating Credo's own mediator and wyvrn's `push-notifications/1.0` Web Push design
both already use.

## Message Reference

Reproduced here for convenience; the Aries RFC 0734 text and the Credo reference
implementation above are both normative.

### `set-device-info`

Message Type URI: `https://didcomm.org/push-notifications-fcm/1.0/set-device-info`

Sent by the `client` to register, update, or clear its FCM registration.

| Field | Type | Description |
|---|---|---|
| `device_token` | string \| null | The FCM registration token. `null` (with `device_platform` also `null`) clears any stored registration. |
| `device_platform` | string \| null | A free-form platform label (`"android"`/`"ios"`). Must be `null` iff `device_token` is `null`. |

### `get-device-info`

Message Type URI: `https://didcomm.org/push-notifications-fcm/1.0/get-device-info`

Sent by the `client` to ask the mediator what it currently has on file for this
connection. No body.

### `device-info`

Message Type URI: `https://didcomm.org/push-notifications-fcm/1.0/device-info`

Sent by the `mediator` in reply to `get-device-info`, threaded via `thid`.

| Field | Type | Description |
|---|---|---|
| `device_token` | string \| null | As currently stored. |
| `device_platform` | string \| null | As currently stored. |

### `problem-report`

Message Type URI: `https://didcomm.org/push-notifications-fcm/1.0/problem-report`

Standard `report-problem/1.0`-style problem report, sent when `set-device-info`
carries a `device_token`/`device_platform` pair that violates the both-or-neither-null
rule above.

## wyvrn-specific notes

- **Client-side FCM token acquisition inside a Tauri app has no first-party Tauri
  solution as of Tauri 2.x.** wyvrn-chat uses the community
  [`tauri-plugin-notifications`](https://github.com/Choochmeque/tauri-plugin-notifications)
  (`registerForPushNotifications()`, `push-notifications` Cargo feature) for this --
  not an official Tauri plugin, evaluated and adopted as this plan's own explicitly
  flagged research spike. Requires a real Firebase project's `google-services.json`
  placed in `gen/android/app/` at build time; see `wyvrn-chat`'s own README for the
  exact steps, since this is a per-deployment secret/config file, never committed.
- **Only Android is wired up in wyvrn-chat today.** iOS has no Tauri build at all yet
  (see the Tauri native-builds plan's Part 5) -- the APNs half of this protocol's
  "Firebase relays to APNs" property is real and already covered by the same mediator
  code, but there is nothing on the client side to test it against until an iOS build
  exists.
- **The browser PWA build is unaffected.** It continues toward wyvrn's own
  `push-notifications/1.0` (Web Push/VAPID) design, not this protocol at all.
