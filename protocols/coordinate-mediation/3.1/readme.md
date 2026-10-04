---
title: Coordinate Mediation
publisher: wyvrn
license: MIT
piuri: https://didcomm.org/coordinate-mediation/3.1
status: Proposed
summary: A minor-version addition to coordinate-mediation/3.0 (Production) -- adds one new, mediator-initiated message, fcm-message, that points a client at a specific queued message from inside an otherwise-opaque FCM push payload. Backward compatible with 3.0; every existing message, role and behavior is unchanged.
tags:
  - mediation
  - notifications
authors:
  - name: wyvrn
  - name: rodolfomiranda
    email:
---

> **A note on this document's PIURI.** `wyvrn-protocols`' own convention is to use a
> `https://wyvrn.app/<name>/<version>` placeholder for anything not yet merged into the
> real [didcomm.org](https://didcomm.org) registry, precisely so nothing claims a real
> PIURI prematurely. This document is a deliberate, acknowledged exception: it's written
> and numbered as the real `coordinate-mediation/3.1` from the start, because the intent
> is to propose it upstream as exactly this -- a minor-version addition to the existing,
> Production `coordinate-mediation/3.0` -- rather than to land it under a wyvrn-specific
> name first and rename it later. Until a real PR to didcomm.org actually merges this,
> treat `3.1` here as proposed, not adopted.

Everything below this note, through Motivation and the existing Mediate
Request/Deny/Grant and Recipient Update/Query messages, is `coordinate-mediation/3.0`'s
own text, reproduced here because a minor version's own readme describes the whole
protocol at that version, not a diff against the last one -- the same convention the
real registry already uses between other majors/minors. The only new material is the
**FCM Message** section under Message Reference, and the one added row in Connectivity.

# Motivation
Use of the forward message in the Routing Protocol 3.0 requires an exchange of information. The _Recipient_ must know which endpoint and routing did(s) to share, and the _Mediator_ needs to know which did should be routed via this relationship.

## Roles
There are two roles in this protocol:

- `mediator`: The agent that will be receiving `forward` messages on behalf of the _recipient_.
- `recipient`: The agent for whom the `forward` message payload is intended.

## Requirements

The `return_route` extension must be supported by both agents (`recipient` and `mediator`).
The common use of this protocol is for the reply messages from the `mediator` to be synchronous, utilizing the same connection channel for the reply. In order to have this synchronous behavior the `recipient` should specify `return_route` header to `all`.
This header must be set each time the communication channel is established: once per established websocket, and every message for an HTTP POST.

`fcm-message` (new in 3.1) is the one exception to this requirement -- see its own
Message Reference entry for why.

## Connectivity

This protocol consists of three different message requests from the `recipient` that should be replied by the `mediator`, plus one new message the `mediator` sends unprompted:

1. Mediate Request -> Mediate Grant or Mediate Deny
2. Recipient Update -> Recipient Update Response
3. Recipient Query -> Recipient
4. *(3.1)* FCM Message -- mediator-initiated, no reply expected; see its own Message Reference entry.

## States

This protocol follows the request-response message exchange pattern, and only requires the simple state of waiting for a response or to produce a response. `fcm-message` (3.1) is the exception: it's fire-and-forget, not request-response.

## Basic Walkthrough

A `recipient` may discover an agent capable of routing using the Discover Features Protocol 2.0. If protocol is supported with the `mediator`, a `recipient` may send a `mediate-request` to initiate a routing relationship.

First, the `recipient` sends a `mediate-request` message to the `mediator`. If the `mediator` is willing to route messages, it will respond with a `mediate-grant` message, otherwise with a `mediate-deny` message. The `recipient` will share the routing information in the grant message with other contacts.

When a new DID is used by the `recipient`, it must be registered with the `mediator` to enable route identification. This is done with a `recipient-update` message.

The `recipient-update` and `recipient-query` methods are used over time to identify and remove DIDs that are no longer in use by the `recipient`.

*(3.1)* Separately, whenever the `mediator` ends up queuing a message for a `recipient` instead of delivering it live (see [`push-notifications-fcm/1.0`](https://github.com/wyvrn-cloud/protocols/blob/master/protocols/push-notifications-fcm/1.0/readme.md), Aries RFC 0734, which this builds on), it may also send that `recipient` an `fcm-message` -- a DIDComm envelope that happens to travel as the `data` payload of the FCM push itself, rather than over this protocol's usual transport. See the FCM Message entry below for the full shape and why this exists.

## Design By Contract

No protocol specific errors exist. Any errors related to headers or other core features are documented in the appropriate places.

*(3.1)* `fcm-message` is sent best-effort, exactly like the underlying FCM wake-up push it rides inside: the mediator does not retry it, and a `recipient` that never sees it (push delivery failed, the device was offline, the app was never reopened) simply falls back to discovering the same message the ordinary way, via `messagepickup/3.0`'s ordinary `status-request`/`delivery-request` poll. `fcm-message` is an optimization on top of that path, never a replacement for it.

## Security

This protocol expects messages to be encrypted during transmission, and repudiable.

*(3.1)* `fcm-message` carries only a `recipient_did` and a `message_id` -- both already meaningless to anyone but the `mediator` and the `recipient` (`messagepickup/3.0`'s own Message Reference already calls a delivery attachment's `id` "an opaque value" the recipient "should not deduce any information from"). It is still a real, authcrypt'd DIDComm message addressed to the `recipient`, not a plaintext hint -- so even though the value it carries is already low-sensitivity, the push transport it travels over (FCM, Google's infrastructure) never sees it in the clear.

## Composition

Supported Goal Code | Notes
--- | ---

## Message Reference

### Mediate Request
This message serves as a request from the `recipient` to the `mediator`, asking for the permission (and routing information) to publish the endpoint as a mediator.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/mediate-request`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/mediate-request",
}
```

### Mediate Deny
This message serves as notification of the `mediator` denying the `recipient`'s request for mediation.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/mediate-deny`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/mediate-deny",
}
```

### Mediate Grant
A mediate grant message is a signal from the `mediator` to the `recipient` that permission is given to distribute the included information as an inbound route.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/mediate-grant`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/mediate-grant",
    "body":
            {
                "routing_did": ["did:peer:0z6Mkfriq1MqLBoPWecGoDLjguo1sB9brj6wT3qZ5BxkKpuP6"]
            }
}
```
where:

- `routing_did`: DID of the mediator where forwarded messages should be sent. The `recipient` may use this DID as an enpoint as explained in [Using a DID as an endpoint](https://identity.foundation/didcomm-messaging/spec/#using-a-did-as-an-endpoint) section of the specification.

**NOTE**: After receiving a `mediate-grant` message the `recipient` should update his `recipient_did` with a `recipient-update` message and add DIDs. In order for the `mediator` to start accepting Forward Message for those DIDs.

### Recipient Update
Used to notify the `mediator` of DIDs in use by the `recipient`.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/recipient-update`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/recipient-update",
    "body": {
        "updates": [
            {
                "recipient_did": "did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
                "action": "add"
            }
        ]
    },
    "return_route": "all"
}
```
where:

- `recipient_did`: DID subject of the update.
- `action`: one of `add` or `remove`.

### Recipient Response
Confirmation of requested Recipient DID updates.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/recipient-update-response`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/recipient-update-response",
    "body": {
        "updated": [
            {
                "recipient_did": "did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
                "action": "" // "add" or "remove"
                "result": "" // [client_error | server_error | no_change | success]
            }
        ]
    }
}
```
where:

- `recipient_did`: DID subject of the update.
- `action`: one of `add` or `remove`.
- `result`: one of `client_error`, `server_error`, `no_change`, `success`; describes the resulting state of the Recipient update.

### Recipient Query
Query `mediator` for a list of DIDs registered for this connection.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/recipient-query`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/recipient-query",
    "body": {
        "paginate": {
            "limit": 30,
            "offset": 0
        }
    }
}
```
where:

- `paginate`: is optional, and if present must include `limit` and `offset`.

### Recipient
Response to recipient query, containing retrieved recipient DIDs.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/recipient`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/recipient",
    "body": {
        "dids": [
            {
                "recipient_did": "did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"
            }
        ],
        "pagination": {
            "count": 30,
            "offset": 30,
            "remaining": 100
        }
    }
}
```
where:

- `pagination`: is optional, and if present must include `count`, `offset` and `remaining`.

### FCM Message *(new in 3.1)*

Sent by the `mediator` to a `recipient`, unprompted, when it queues a message for that
`recipient` instead of delivering it live -- naming which queued message triggered the
notification, so the `recipient` can go fetch (and, once satisfied, acknowledge) that
specific message rather than treating the resulting push as fully generic.

Message Type URI: `https://didcomm.org/coordinate-mediation/3.1/fcm-message`

```json
{
    "id": "123456780",
    "type": "https://didcomm.org/coordinate-mediation/3.1/fcm-message",
    "body": {
        "recipient_did": "did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
        "message_id": "9f1c2e3a-...-abc123"
    }
}
```
where:

- `recipient_did`: which of the `recipient`'s own registered DIDs the named message was
  queued under -- a single mediation relationship may route for more than one DID (for
  example a shared identity DID and a device-to-device DID), and the `recipient` needs
  this to scope its follow-up `messagepickup/3.0` `delivery-request` correctly.
- `message_id`: the `id` of the specific queued message this notification is about, in
  the same opaque form `messagepickup/3.0`'s own `delivery` attachments use.

**Not delivered like the other messages in this protocol.** Every other message here
travels over this protocol's own transport the normal way (HTTPS, a WebSocket). An
`fcm-message` instead travels as the (base64-encoded, still fully encrypted) `data`
payload of the FCM push itself -- see
[`push-notifications-fcm/1.0`](https://github.com/wyvrn-cloud/protocols/blob/master/protocols/push-notifications-fcm/1.0/readme.md),
Aries RFC 0734 -- piggybacking on the exact wake-up push that protocol already defines,
rather than requiring a second round trip over an ordinary DIDComm transport that the
`recipient` may not have a live connection for in the first place (the whole reason a
push was needed at all). This is also why `return_route` doesn't apply to it: there is
no synchronous reply channel to ask for one on.

**No reply.** `fcm-message` has no corresponding response message. The `recipient`
either acts on it (fetches and decrypts the named message locally, entirely
client-side) or doesn't; either way, nothing is reported back to the `mediator` over
this protocol. The `recipient`'s own subsequent `delivery-request`/`messages-received`
exchange (`messagepickup/3.0`) is the only observable effect, and it's indistinguishable
from an ordinary poll-triggered pickup.

**Size.** FCM's own payload limit (around 4KB, notification and data combined) bounds
how large an `fcm-message` envelope can be. This version addresses it to the
`recipient`'s DID using whatever form (short or long) the mediator already has on file
for it -- a `did:peer:4` recipient's long form grows with that identity's own device
roster, so very large rosters could in principle approach the FCM size limit before the
message content itself is even considered. A future minor version may define addressing
by a `did:peer:4` recipient's short form specifically to keep this constant-size; this
version does not yet, so implementers with very large rosters should be aware of the
ceiling.

## L10n

No localization is required.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-mediator`](https://github.com/wyvrn-cloud/wyvrn-mediator) | Implements `fcm-message` on the `mediator` side (Rust); the three pre-existing 3.0 messages were already implemented prior to this addition.
[`wyvrn-chat`](https://github.com/wyvrn-cloud/wyvrn-chat) | Implements the `recipient` side of `fcm-message` natively on Android (decrypts it inside the FCM push handler to drive a richer notification, subject to the device's own configured decryption tier -- see that repo's own notes).

## Endnotes

### Future Considerations
- Should we allow listing dids by date? You could query dids in use by date?
- We are missing a way to check a single did (or a few dids) without doing a full list.
- Mediation grant supports only one endpoint. What can be done to support multiple endpoint options i.e. http, ws, etc.
- Requiring proof of did ownership (with a signature) would prevent an edge case where a malicious party registers a did for another party at the same mediator, and before the other party.
- How do we express terms and conditions for mediation?
- *(3.1)* Addressing `fcm-message` to a `did:peer:4` recipient's short form, to keep its
  size independent of that identity's own device roster size.
- *(3.1)* A way for the `recipient` to opt out of receiving `fcm-message` specifically
  (while still receiving the underlying generic wake-up push), for a `recipient` whose
  own local policy is to never decrypt anything outside of a fully-open app session.
