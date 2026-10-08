---
title: Typing Indicators
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/typing-indicators/1.0
status: Proposed
summary: Lets a party tell the others in a conversation that it is typing a message right now, with one short-lived message that is delivered live or not at all — never queued, never pushed — so that a lost one leaves nothing stuck. A companion to chat-message/1.0, whose conversation model it uses.
tags:
  - messaging
  - chat
  - presence
authors:
  - name: wyvrn
---

## Summary

"Alice is typing…". A party that is typing a message sends the conversation
a `typing` message that expires about ten seconds later, and sends another
before that one expires if it is still typing. A receiver shows the
indicator until the latest one expires or the message itself arrives. There
is no "stopped typing" message, and nothing here is ever stored, queued for
an offline recipient, or pushed to a closed app.

This is one of the companion protocols of
[`chat-message/1.0`](../../chat-message/1.0/readme.md), which defines the
conversation model (pair or group, thread) this protocol addresses
indicators within.

## Motivation

[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0) lists typing
indicators as out of its scope, and nothing else in the didcomm.org registry
covers them. `chat-message/1.0` keeps them out of its message on purpose: an
agent may well support rich messages and not want presence information
sent about its user, and [`discover-features/2.0`](https://didcomm.org/discover-features/2.0)
works per protocol.

The difficulty is not the message, which is trivial, but delivery. A typing
indicator is worth something for a few seconds and worth less than nothing
afterwards: delivered late, it says someone is typing who isn't; queued at a
mediator, it is a pile of stale presence waiting for a phone to wake up;
pushed, it wakes a closed app for nothing. A DIDComm sender cannot see
whether its recipient is online, so the requirement that these messages are
*live or nothing* falls on the mediator, through the one header DIDComm
already has for it: `expires_time`, on the message and on the `forward`
that carries it. This protocol says exactly what a mediator does with that
(see Composition).

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `typist` | Says it is typing in a conversation. |
| `observer` | Receives that and shows it, for as long as it holds. |

Every party in a conversation may play both roles.

## Connectivity

The same as the conversation, as `chat-message/1.0` defines it: in a pair,
the typist sends to the other party; in a group
([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)), to every other member that
discloses this protocol, separately, with the same `id`.

Delivery is mediated like any other DIDComm v2 message, but a `typing`
message is meant to reach an observer only over a live connection the
observer currently holds with its mediator (`messagepickup/3.0`'s live
delivery, or the equivalent). An observer that is not connected does not get
it later; see Composition for what the mediator does instead.

## States

The protocol is stateless on the wire: no message requires a reply. An
observer keeps, per conversation and per typist, one time: until when that
typist is typing. Nothing is persisted.

| Event | Effect on the observer |
|---|---|
| `typing` received, `expires_time` in the future | that typist is shown as typing in that conversation until `expires_time` |
| `typing` received, `expires_time` already past | ignored |
| `typing` received with an earlier `expires_time` than the one held | ignored |
| `expires_time` reached | the indicator is removed |
| a message in that conversation arrives from that typist | the indicator is removed at once |

## Basic Walkthrough

Alice and Bob are contacts, each has learned through `discover-features/2.0`
that the other supports this protocol, and both are connected live to their
mediators.

1. Alice starts typing a reply to Bob. After the first keystroke her agent
   sends:

   ```json
   {
     "id": "t1",
     "type": "https://wyvrn.app/typing-indicators/1.0/typing",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400000,
     "expires_time": 1791400010,
     "body": {}
   }
   ```

   Bob's agent shows "Alice is typing…" and notes that this holds until
   `1791400010`.

2. Alice is still typing six seconds later. Her agent sends another, with a
   new `id`, `created_time` `1791400006` and `expires_time` `1791400016`.
   Bob's agent extends the indicator.

3. Alice sends her message. It arrives at Bob's agent, which removes the
   indicator at once and shows the message. Nothing was sent to say she
   stopped.

Had Alice instead put her phone down, no further `typing` would have been
sent, and Bob's indicator would have gone away at `1791400016` by itself.

Had Bob's agent been offline at step 1, Bob's mediator would have found
nobody to deliver the `forward` to live, seen its `expires_time`, and
dropped it rather than queuing it or waking Bob's phone — so when Bob next
connected there was nothing stale waiting.

## Design By Contract

### Sending

- A `typing` message means "its sender is typing a message in this
  conversation now". That is all it means: it carries no text, no draft,
  and no indication of what the message will be a reply to.
- `created_time` MUST be set, and `expires_time` MUST be set to about 10
  seconds after it. An observer may shorten what it shows (see Observing)
  but a typist MUST NOT set an `expires_time` more than 30 seconds after
  `created_time`.
- While typing continues, a typist re-sends the message — a new `id`, new
  times — before the previous one expires, and not more often than once
  every few seconds; `wyvrn-chat` intends every 6 seconds for a 10-second
  expiry. A typist that has stopped typing simply stops sending.
- **There is no "stopped typing" message.** An explicit stop would be the
  one message whose loss matters: a lost stop leaves an indicator stuck
  until the observer gives up on its own. With expiry alone, the worst a
  lost message can do is end an indicator a few seconds early, and the
  normal case — the person sent the message — is covered by the message
  itself arriving.
- A typist SHOULD send a `typing` only while the person is actually
  composing: `wyvrn-chat` intends to send only while the message box of
  that conversation has focus and its text is changing, and nothing while
  the text is unchanged, however long it stays. A typist SHOULD NOT send
  one for a conversation the recipient is not going to see soon; this
  version makes no attempt to know that beyond the rule above.
- A typist sends only to parties that disclose this protocol, and only when
  the person has not turned the feature off (see Security).
- The message carries the conversation's headers as `chat-message/1.0`
  defines them: in a group, the group's id in `pthid`; when the person is
  typing in a thread ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)),
  the thread's id in `thid`, otherwise no `thid`. The `expires_time` here
  is the indicator's own and has nothing to do with a
  `disappearing-messages/1.0` timer, which does not apply to this message.

### Observing

- The typist is the DID the message's encryption authenticates. Every
  `typing` MUST be sent sender-authenticated (`authcrypt`), and an observer
  MUST ignore one that is not.
- An observer shows the typist as typing in the conversation the message's
  `pthid` and sender name, until the message's `expires_time`, or until a
  message from that typist arrives in that conversation, whichever is
  first. A later `typing` from the same typist in the same conversation
  replaces the time held; an earlier one is ignored.
- An observer MUST ignore a `typing` whose `expires_time` has already
  passed when it arrives, and SHOULD cap the time it shows an indicator at
  30 seconds from receipt whatever the header says, so that a typist's
  wrong clock cannot pin an indicator on the screen.
- A `typing` from a DID that is not, in the observer's own record, a
  member of the group it names is ignored, as `chat-message/1.0` says of
  every message in a group. In a thread, an observer that doesn't implement
  threads treats it as typing in the thread's conversation.
- A `typing` is not a message in the conversation: an observer MUST NOT
  notify the person of one, count it as unread, store it, or synchronize it
  to its own other devices. What a `typing` can do is make the conversation
  list say "typing…" in place of the last message's preview.
- A `typing` that was queued after all (a mediator that does not implement
  the behaviour in Composition) and arrives after its `expires_time` is
  ignored by the first rule above; the protocol is correct without the
  mediator's help, only wasteful.

## Security

- **Typing leaks presence.** A `typing` says that the person is at the
  device, in this conversation, right now; sent to a group, it says so to
  every member. A typist SHOULD offer a setting that turns sending off, and
  MUST NOT send one to a party that has not disclosed this protocol. An
  observer MAY offer a setting that hides what it receives.
- **It says nothing about the message.** A `typing` carries no draft text,
  no length, and no `reply_to`; an observer learns only that a message may
  be coming. Nothing here should be extended to carry more.
- **A typist can only speak for itself.** The observer takes the typist
  from the authenticated sender; nobody can make another party appear to be
  typing.
- **An observer bounds what it tracks.** A `typing` is cheap to send, and a
  group member can send one every few seconds to every member. An observer
  keeps at most one time per typist per conversation, and SHOULD bound the
  number of conversations and typists it tracks at once, dropping the
  oldest; it never persists any of it.
- **The mediator sees timing, not content.** A `forward` carrying an
  `expires_time` a few seconds ahead is recognizably a typing indicator (or
  something equally ephemeral) to the mediator, which thereby learns when
  its client is active — but it already knows that from the live
  connection the indicator rides on.

## Composition

- **With `chat-message/1.0`.** Uses its conversation model (pair or group by
  `pthid`; the same conversation only). The arrival of any message in the
  conversation from the typist ends the indicator — a `chat-message/1.0`
  message, a `basicmessage/2.0` message, or anything else that is shown as
  a message.
- **With `discover-features/2.0`.** A typist sends only to parties that
  disclose this protocol. A typing indicator has no plain form, so nothing
  is sent in its place to a party that doesn't; in a group, a `typing` may
  go to some members and not others.
- **With `group-chat/2.0` and `1.0`.** A `typing` in a group carries the
  group's id in `pthid` and is fanned out like a message.
- **With `chat-threads/1.0`.** A `typing` sent while composing in a thread
  carries the thread's `thid`, so that an observer can show the indicator
  in the thread rather than, or as well as, in the conversation.
- **With `routing/2.0`, `coordinate-mediation/3.0`, `messagepickup/3.0`,
  and push notifications (`push-notifications-fcm/1.0`,
  `push-notifications/1.0`).** This is where the protocol's one real
  requirement lives. A DIDComm sender cannot tell whether a recipient is
  connected, so it cannot itself make a `typing` "live or nothing"; the
  mediator can, and the sender tells it how by the standard header:
  - A typist MUST set `expires_time` on every `routing/2.0/forward` it
    wraps a `typing` in, at every hop, to the same value as the inner
    message's. The routing protocol already provides for this ("when the
    internal message expires, it's a good idea to also include an
    expiration for forward requests"); here it is required.
  - A mediator that receives a `forward` whose plaintext carries an
    `expires_time` SHOULD deliver it live if it can, and otherwise SHOULD
    drop it once that time has passed rather than queue it — and, if it
    had queued it, SHOULD remove it from the queue at that time rather than
    hand it over on the next pickup. It MUST NOT send a push notification
    for a `forward` that would have expired before a woken app could
    connect and pick it up; a mediator that would rather not reason about
    that treats any `forward` expiring within a minute of arrival as such.
    A `forward` with a longer-lived `expires_time` — a message under a
    `disappearing-messages/1.0` timer — is queued and pushed as usual.
  - A mediator that implements none of this still complies with
    `routing/2.0`, which makes `expires_time` optional for mediators; the
    cost is stale `typing` messages delivered to and discarded by the
    observer, and pointless pushes.
- **With `receipts/1.0`.** A `typing` is not something to be marked read.
- **With `multi-device/1.0` and `history-sync/1.0`.** A typist with several
  devices sends from whichever device the person is typing on; nothing is
  coordinated between its devices, and a `typing` is never synchronized.

## Message Reference

### `typing`

Message Type URI: `https://wyvrn.app/typing-indicators/1.0/typing`

Sent by a `typist` to every `observer` in the conversation. Means: the sender
is typing a message in this conversation now.

Headers: `created_time` REQUIRED; `expires_time` REQUIRED, about 10 seconds
and at most 30 seconds after `created_time`; `pthid` in a group; `thid`
only in a thread.

The body is an empty object. A `typing` has no fields; an observer MUST
ignore any it finds, so that a later minor version can add some.

Schema: [`schemas/typing.json`](schemas/typing.json).

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. A handler at `src/handlers/typingIndicators/` registered in `src/services/didcomm/messageRouter.ts` is the starting point for receiving; sending hangs off the message box (`src/components/chat/MessageInput.tsx`) and goes through the worker like any other send.
[`wyvrn-didcomm`](https://github.com/wyvrn-cloud/didcomm) | Builds the `routing/2.0/forward` wrapper for a mediated recipient (`crates/didcomm-core/src/routing.rs`, `create_forward_message`), setting `created_time` only. It needs to copy the inner message's `expires_time` onto every forward it wraps it in, as this protocol's Composition requires of the sender; it does not today.
[`wyvrn-mediator`](https://github.com/wyvrn-cloud/mediator) | Needs the mediator behaviour in Composition: deliver live or drop an expired `forward` rather than queue it, purge one from the queue at its `expires_time`, and never push for one about to expire. It does not today: every `forward` it cannot deliver live is queued, and a queued message is what triggers a push.

## Endnotes

### Why there is no "stopped typing" message

Other chat systems send one, and all of them also have a timeout for the
case where it is lost — so the timeout is the mechanism, and the stop
message an optimization that saves a few seconds of indicator in the case
where someone stopped typing and sent nothing. That case is the least
interesting one: the common end of typing is a message, which ends the
indicator by itself. A stop message would also be one more thing to get to
the recipient live or not at all. Leaving it out keeps this protocol to a
single message that is safe to lose.

### Why the mediator, and not the sender, enforces "live or nothing"

A sender behind a mediator sends the same way whether or not the recipient
is connected; the mediator is the only party that knows. The alternative —
asking the recipient's mediator first, or keeping a presence channel between
parties — is a protocol of its own and a bigger presence leak than the
indicator. `expires_time` on the `forward` is the one piece of
sender-to-mediator signalling DIDComm already has for a message that is
not worth keeping, and it needs no new message type on either side.

### Future Considerations

- A `typing` for a draft being recorded (a voice note) rather than typed,
  if a body field for the kind of composing is wanted; this version's
  empty body leaves room for it.
