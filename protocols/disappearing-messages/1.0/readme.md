---
title: Disappearing Messages
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/disappearing-messages/1.0
status: Proposed
summary: A per-conversation timer after which messages are removed from every device. The timer is set with one message; each message sent under it then carries its own removal time in the standard DIDComm `expires_time` header, which this protocol gives the meaning "receivers remove this message at that time" for the whole chat family.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A conversation can be given a timer: one hour, one day, one week. Every
message sent while it is set is removed, from the sender's devices and from
every receiver's, that long after it was sent. The timer is set and cleared
with one message type, `timer`, shown in the conversation as a line
("Alice set messages to disappear after 1 day"). The removal time of each
message travels in the standard DIDComm `expires_time` header, which this
protocol defines, for every message of the chat family, to mean *remove
this message then*.

Changing or clearing the timer affects only messages sent afterwards. A
message keeps the expiry it was sent with.

## Motivation

Disappearing messages are what messaging apps offer for a conversation that
should not leave a record on every device for ever, and nothing in the
didcomm.org registry provides them. DIDComm Messaging already has the
header this needs: `expires_time` is "when the sender will consider the
message to be expired", with a default meaning (abort the protocol) that the
spec says a protocol may nuance. This protocol nuances it for chat.

[`chat-message/1.0`](../../chat-message/1.0/readme.md) keeps the timer out
of the message itself so that an agent can disclose support separately
through [`discover-features/2.0`](https://didcomm.org/discover-features/2.0),
and so that the header can be set on every message of the family, whichever
protocol it belongs to.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `setter` | Sets or clears the conversation's timer. |
| `participant` | Receives the timer, sends its messages under it, and removes messages when they expire. |

Every party in a conversation plays `participant`; who may play `setter`
is defined under Design By Contract.

## Connectivity

The same as the conversation: two parties, or, in a group
([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)), the setter sends `timer`
separately, with the same `id`, to every other member. The messages sent
under the timer travel exactly as they would without one.

## States

Each participant keeps, per conversation, the current timer: the `timer`
message with the latest `created_time` from an allowed setter, or none.

| State | Meaning |
|---|---|
| `off` | No timer. Messages sent in the conversation carry no `expires_time`. |
| `set` | A timer of `seconds`. Each message sent carries `expires_time` = its `created_time` + `seconds`. |

| Event | `off` | `set` |
|---|---|---|
| `timer` received with `seconds` > 0, later than the one held | → `set` | → `set` with the new value |
| `timer` received with `seconds` 0 or null, later than the one held | stays `off` | → `off` |
| `timer` received, earlier than the one held | ignored | ignored |
| `timer` received from a party not allowed to set it | ignored | ignored |

Independently of the timer, every message held with an `expires_time` is
removed when that time comes.

## Basic Walkthrough

Alice and Bob are contacts, and each has learned through
`discover-features/2.0` that the other supports this protocol.

1. Alice sets the conversation to disappear after a day. Her agent sends:

   ```json
   {
     "id": "d1",
     "type": "https://wyvrn.app/disappearing-messages/1.0/timer",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400000,
     "body": { "seconds": 86400 }
   }
   ```

   Both agents show a line: "Alice set messages to disappear after 1 day".

2. Alice sends a message. Her agent stamps it with its removal time, a day
   after it was created:

   ```json
   {
     "id": "m1",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400060,
     "expires_time": 1791486460,
     "lang": "en",
     "body": { "content": "Meet at the usual place?" }
   }
   ```

   Bob's agent shows it with a small timer, as does Alice's own.

3. Bob reacts with a thumbs-up. His reaction is about `m1`, so it carries
   `m1`'s `expires_time` and goes when `m1` goes:

   ```json
   {
     "id": "r1",
     "type": "https://wyvrn.app/message-reactions/1.0/reactions",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791400120,
     "expires_time": 1791486460,
     "body": {
       "to": { "id": "m1", "author": "did:example:alice" },
       "emoji": ["👍"]
     }
   }
   ```

4. At `1791486460`, a day after `m1` was sent, both agents remove `m1` and
   the reaction — whether or not Bob ever read it, and whether or not
   either device was on at the time: an agent that was off removes it when
   it next runs.

5. Later Alice turns the timer off:

   ```json
   {
     "id": "d2",
     "type": "https://wyvrn.app/disappearing-messages/1.0/timer",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791500000,
     "body": { "seconds": 0 }
   }
   ```

   Both agents show "Alice turned off disappearing messages". Messages sent
   from now on carry no `expires_time`; a message sent before this, still
   held, keeps the expiry it was sent with and goes at that time.

Had Bob's agent not supported this protocol, Alice's agent would have sent
nothing in steps 1 and 5, and shown Alice that Bob's app does not remove
messages. Step 2 would still have carried `expires_time` — the header
travels to everyone — which Bob's agent would have ignored.

## Design By Contract

### The meaning of `expires_time`

For every message of the chat family — a `chat-message/1.0` `message`,
`message-edit` or `message-delete`, a
[`message-reactions/1.0`](../../message-reactions/1.0/readme.md) statement,
a [`chat-pins/1.0`](../../chat-pins/1.0/readme.md) pin or unpin, a
[`chat-threads/1.0`](../../chat-threads/1.0/readme.md) creation, and
`basicmessage/2.0` content in a chat conversation — this protocol defines
the `expires_time` header to mean: **every receiver removes this message
at that time**, and the sender removes its own copy too.

- `expires_time` is UTC epoch seconds, as DIDComm Messaging defines it.
- At that time, by its own clock, a participant MUST remove the message
  entirely: its text, media, attachment bytes, embeds, and anything derived
  from them — notifications, search indexes, media caches, thumbnails. The
  message's `id` is not kept: a reference to it afterwards is simply
  unresolved, which `chat-message/1.0` already handles ("Original message
  unavailable"). A participant that was not running at the time removes it
  when it next runs, before showing anything.
- A message that arrives already expired — `expires_time` in the past by
  the receiver's clock — MUST be discarded on arrival, never shown and
  never stored.
- The header is the fact; the timer is how senders set it. A participant
  MUST honour `expires_time` on a message even when it believes the
  conversation has no timer, and MUST NOT compute an expiry from the timer
  for a message that carries none.
- A message with no `expires_time` has none, as DIDComm says.

### Which messages carry an expiry

- A **new message** in a conversation whose timer is `set` — a
  `chat-message/1.0` `message`, or its `basicmessage/2.0` plain form — MUST
  carry `expires_time` = its `created_time` + the timer's `seconds`. The
  timer starts when the message is *sent*, not when it is read: every copy,
  on every device of every party, goes at the same moment, and nobody has
  to know who has read what.
- A **message about an earlier message** — an edit or delete of it, a
  reaction to it, a pin or unpin of it, a thread created from it — carries
  that message's `expires_time` if it has one, and none otherwise,
  whatever the timer is, so that it goes when the message goes.
- A `timer` message itself MUST NOT carry `expires_time`. It is the
  conversation's state, not a message under the timer, and a participant
  that joins the conversation later needs to find it.
- A sender MUST NOT set `expires_time` on a chat-family message outside
  these rules — on a new message in a conversation without a timer, say.
  Per-message timers are a possible later version, not a loophole in this
  one.
- Changing or clearing the timer does not touch a message already sent. A
  participant MUST NOT change the `expires_time` of a message it holds.

### Setting the timer

- `seconds` is a positive integer, the time after which a message sent
  under this timer is removed; or `0` or `null`, which both clear the
  timer.
- `created_time` MUST be set. A setter's later `timer` for the same
  conversation MUST carry a later `created_time` than its earlier ones.
- In a group, `timer` carries the group's id in `pthid`. It carries no
  `thid`: the timer is the conversation's, threads included.
- A setter SHOULD offer the fixed choices 1 hour (`3600`), 8 hours
  (`28800`), 1 day (`86400`) and 1 week (`604800`), so that people on
  different apps see the same options, but any positive value is valid and
  a participant MUST accept one it would not have offered.

### Who may set it

| Conversation | May set or clear the timer |
|---|---|
| Pair | either party |
| Group with no admin (`group-chat/1.0`) | every member |
| Group with an admin (`group-chat/2.0`) | the admin only |

A participant MUST ignore a `timer` from a party that, in its own record of
the conversation, is not allowed to set it. The record it checks is the one
it holds when the message arrives.

### Receiving a timer

- Per conversation, the **latest `created_time` wins**: a participant
  replaces the timer it holds with a `timer` that is later, and ignores one
  that is earlier. When two carry the same `created_time`, the shorter
  stands, a cleared timer counting as the longest.
- A `timer` is shown as a line in the conversation, saying who set what:
  "Alice set messages to disappear after 1 day", "Alice turned off
  disappearing messages". It is a change to the conversation, not a message
  in it: a participant SHOULD NOT count it as unread, but MAY notify, since
  what the person can expect of the conversation has changed.
- A participant SHOULD show, on each message with an `expires_time`, that
  it will disappear, and when.
- A `timer` from a sender the participant has no conversation with, or
  carrying an unknown `pthid`, is not applied; a participant MAY keep it
  briefly in case the group's invitation is about to arrive.

## Security

- **A timer is a request to cooperating apps.** It removes a message from
  every device that honours it and from none that does not. Nothing stops a
  device from keeping a message, copying it, photographing the screen, or
  running an agent that ignores the header; and a party whose agent does not
  disclose this protocol keeps every message for ever. This protocol does
  not pretend otherwise, any more than `chat-message/1.0`'s delete does. A
  participant SHOULD show, in a conversation with a timer, which parties'
  agents do not honour it.
- **The setter is the DID the encryption authenticates.** `timer` MUST be
  sent `authcrypt`, and a participant MUST ignore one that is not.
- **Who may set the timer is enforced by every participant for itself**,
  against its own record of the group. An unauthorised `timer` is ignored;
  it cannot make anyone's messages disappear, or stop them disappearing.
- **A sender decides its own messages' expiry**, since it sets the header;
  a sender that puts a short `expires_time` on its own message is only
  doing early what a delete would do. It cannot set one on anyone else's.
- **Clocks differ.** A participant removes by its own clock, so a device
  with a wrong clock removes early or late, and may discard a fresh message
  as already expired. A participant SHOULD warn when its clock is far from
  the `created_time` of the messages it receives.
- **A mediator may keep a copy** until it delivers it. A mediator that
  drops a queued message once its `expires_time` has passed is doing what
  the receiver would do on arrival, and is compatible with this protocol;
  one that does not is no worse than a receiver that was off.
- **Removal is local and leaves no trace by design.** Nothing is sent when
  a message expires; every party removes it on its own. A receiver that
  wants to know a message was there cannot tell from the wire that it is
  gone.

## Composition

- **With `chat-message/1.0`, `message-reactions/1.0`, `chat-pins/1.0`,
  `chat-threads/1.0`, and `basicmessage/2.0` content in a chat
  conversation.** This protocol gives their `expires_time` header its
  meaning, and says which of their messages carry one. Their own rules for
  keeping an edit, delete, reaction or pin "until the message arrives" are
  bounded by it: once the target would have expired, there is nothing to
  wait for.
- **With `group-chat/2.0` and `1.0`.** `timer` carries the group id in
  `pthid`. Whether the group has an admin decides who may set it. A member
  who joins later does not learn the timer unless it is set again; an
  allowed setter MAY re-send the current timer to a new member.
- **With `discover-features/2.0`.** A setter sends `timer` only to parties
  that disclose this protocol. It has no plain form, so nothing is sent in
  its place to a party that doesn't; the `expires_time` header is set on
  that party's messages all the same, including a `basicmessage/2.0` plain
  form, and a sender SHOULD show that such a party keeps messages for ever.
- **With [`history-sync/1.0`](../../history-sync/1.0/readme.md).** A
  person's own devices sync their copies of a message with its
  `expires_time`, so that every device removes it at the same time. A device
  that syncs a message already expired discards it.
- **With `receipts/1.0`.** A `timer` is not something to be marked read. A
  receipt for a message that has since expired is not an error.
- **With `coordinate-mediation/3.0`.** No change. A mediator MAY drop a
  queued message whose `expires_time` has passed.

## Message Reference

### `timer`

Message Type URI: `https://wyvrn.app/disappearing-messages/1.0/timer`

Headers: `created_time` REQUIRED; `pthid` in a group; never `thid` or
`expires_time`.

| Field | Type | Description |
|---|---|---|
| `seconds` | integer or null | REQUIRED. A positive integer: messages sent from now on are removed this many seconds after they are sent. `0` or `null`: the timer is cleared. |

Schema: [`schemas/timer.json`](schemas/timer.json) validates the whole
message, headers included.

### Messages under the timer

No new type. Any message of the chat family sent under the timer, or about a
message that was, carries:

| Header | Description |
|---|---|
| `expires_time` | UTC epoch seconds at which every party removes the message. A new message: its `created_time` + the timer's `seconds`. A message about an earlier message: that message's `expires_time`. |

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. The starting point is a new `src/handlers/disappearingMessages/disappearingMessagesHandler.ts` registered in `src/services/didcomm/messageRouter.ts` for `timer`; stamping `expires_time` on outgoing messages and removing expired ones belong in `src/worker/agentWorker.ts`, with the stored expiry in `src/services/storage/messagesRepository.ts`.

## Endnotes

### Why the timer starts at sending

Some apps start a message's timer when it is read, so that a message waits
for its reader. That needs every device to know when every other device
read it, which needs receipts from everyone — and a group of this family
has no receipts. Starting at sending needs nothing: the sender writes the
time into the message, and every copy anywhere goes at that time. It is also
the stricter choice, which is the right default for a feature about not
keeping things.

### Why a header, not a body field

The removal time has to be on every kind of message in the conversation —
a reaction, a pin, an edit — not only on the chat message. Putting it in a
header means each of those protocols need say nothing about it, and
`expires_time` was already defined for exactly this shape of meaning,
awaiting a protocol to say what "expired" is.

### Future Considerations

- A per-message timer, set by the sender on one message.
- View-once media: a message removed after it is first shown, which needs
  the receiver's cooperation in a way a timed removal does not.
- Telling a member who joined later what the conversation's timer is,
  without the setter re-sending it.
