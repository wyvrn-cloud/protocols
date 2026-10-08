---
title: Chat Pins
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/chat-pins/1.0
status: Proposed
summary: Lets a party pin a message for everyone in a conversation, and unpin it, so that every member sees the same list of pinned messages; who may pin in a group follows the group's settings.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A pin marks a message as worth finding again — a door code, a date, a
decision — and puts it in a list at the top of the conversation that every
member sees. This protocol carries the pin and the unpin. Who pinned is
visible; who may pin is a rule of the conversation.

A pin is shared. A person's *private* bookmarks — messages marked for
themselves alone — are not sent to anyone, and are no part of this protocol
(see Composition).

## Motivation

Pinned messages are a fixture of messaging apps, and nothing in the
didcomm.org registry provides them. `chat-message/1.0` keeps them out of the
message itself so that an agent can disclose pin support separately through
[`discover-features/2.0`](https://didcomm.org/discover-features/2.0), and
defines the message reference this protocol uses to name what is pinned.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `pinner` | Pins a message of the conversation, or unpins one. |
| `observer` | Receives that and shows the conversation's pins. |

Every party in a conversation plays `observer`; who may play `pinner` is
defined under Design By Contract.

## Connectivity

The same as the conversation the message belongs to: two parties, or, in a
group ([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)), the pinner sends its pin or unpin
separately, with the same `id`, to every other member.

## States

There is no exchange to track. Each observer keeps, per conversation and per
target message, the latest of the `pin` and `unpin` messages it has received
about that message from an allowed pinner, and shows the targets whose
latest is a `pin`.

| Event | Effect on the observer's record for the target |
|---|---|
| `pin` or `unpin` received, later `created_time` than the one held, or none held | replaces it |
| `pin` or `unpin` received, earlier `created_time` than the one held | ignored |
| `pin` and `unpin` with equal `created_time` | the `unpin` stands |
| `pin` or `unpin` received from a party not allowed to pin | ignored |
| `pin` received for a message not held | kept; the target shown from its snippet, and resolved when it arrives |
| the target is deleted | stays pinned, shown as deleted |

## Basic Walkthrough

Alice and Bob are contacts, and each has learned through
`discover-features/2.0` that the other supports this protocol.

1. Bob sent Alice the message `m1`: "The door code is 4471".

2. Alice pins it. Her agent sends:

   ```json
   {
     "id": "p1",
     "type": "https://wyvrn.app/chat-pins/1.0/pin",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400000,
     "body": {
       "target": { "id": "m1", "author": "did:example:bob", "snippet": "The door code is 4471" }
     }
   }
   ```

   Bob's agent adds `m1` to the conversation's pinned list, marked as
   pinned by Alice. Nothing is notified and nothing is marked unread.

3. The code changes, and Bob unpins the message — in a pair either party
   may, and anyone who may pin may unpin any pin:

   ```json
   {
     "id": "p2",
     "type": "https://wyvrn.app/chat-pins/1.0/unpin",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791403600,
     "body": {
       "target": { "id": "m1", "author": "did:example:bob" }
     }
   }
   ```

   Alice's agent removes `m1` from the list. The message itself is
   untouched.

In a group, Alice's agent would have sent `p1` to every other member, each
of which would have checked, against its own record of the group, that Alice
may pin.

## Design By Contract

### Pinning and unpinning

- `target` is a message reference as
  [`chat-message/1.0`](../../chat-message/1.0/readme.md) defines it. It MUST
  refer to a message in the conversation the pin is sent in. The message may
  be of any type. A `pin` SHOULD carry a `snippet`, since an observer may
  not hold the target and the list has to show something; an `unpin` needs
  none.
- `created_time` MUST be set. A pinner's later pin or unpin of the same
  target MUST carry a later `created_time` than its earlier ones.
- In a group, a pin or unpin carries the group's id in `pthid`. It carries
  the target's `thid` if the target is in a thread
  ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)).
- A pin and an unpin are **idempotent**: pinning a pinned message, or
  unpinning one not pinned, is a statement of the same state, not an error,
  and may safely be received twice. Because of this, a pinner MAY send its
  standing pins again — to a member who joined after they were made, say.
- A pinned message that is later deleted stays pinned, and is shown in the
  list as deleted; an observer MAY hide it from the list. Deletion cannot be
  enforced on every agent (see `chat-message/1.0`), so a rule that unpinned
  a deleted message would be obeyed only by those that knew of the
  deletion.
- This protocol sets no limit on the number of pins. An implementation that
  wants one applies it when pinning, not when receiving.

### Who may pin

| Conversation | May pin and unpin |
|---|---|
| Pair | either party |
| Group, `group-chat/1.0` | every member |
| Group, `group-chat/2.0`, setting `who_may_pin` is `members` (the default) | every member |
| Group, `group-chat/2.0`, setting `who_may_pin` is `admin` | the admin only |

- Anyone allowed to pin may unpin any pin, whoever made it.
- An observer MUST ignore a pin or unpin from a party that, in its own
  record of the conversation, is not allowed to pin — a member of the group
  at all, and the admin where the setting requires it. The record it checks
  is the one it holds when the message arrives: a pin that races a change of
  the setting may be accepted by some members and ignored by others, and
  this protocol does not resolve that; the next pin or unpin from an allowed
  pinner does.
- Changing `who_may_pin` to `admin` does not unpin what members pinned
  before; the admin unpins what it wants gone.

### Observing

- Per target, the **latest `created_time` wins**: an observer replaces what
  it holds for a target with a pin or unpin that is later, and ignores one
  that is earlier. When a `pin` and an `unpin` carry the same
  `created_time`, the `unpin` stands.
- An observer MUST keep an `unpin` as it keeps a `pin`, so that a `pin`
  arriving afterwards with an earlier `created_time` is ignored rather than
  applied. It MAY discard a held `unpin` after a reasonable time.
- A pin for a message the observer doesn't hold MUST be kept and applied
  when the message arrives: the two travel separately and can arrive in
  either order. Until then the observer MAY show the pin from its snippet,
  making clear it is a quotation, or leave it out of the list.
- The conversation's pins are shown as a list, in the order they were made
  (by the standing pin's `created_time`), each with who pinned it; selecting
  one goes to the message. A pin of a message in a thread belongs to the
  conversation's list; an observer MAY also show it in the thread.
- A pin or unpin is not a message in the conversation: an observer SHOULD
  NOT notify its user of one or count it as unread. It MAY show a line in
  the conversation saying who pinned what.

## Security

- **The pinner is the DID the encryption authenticates.** Every message
  here MUST be sent `authcrypt`, and an observer MUST ignore one that is
  not. `target.author` is not authenticated by it.
- **Who may pin is enforced by every observer for itself**, against its own
  record of the group's membership and settings. A party that is not
  allowed cannot pin or unpin for anyone whose record says so; there is no
  way to make an observer with a wrong record agree, which is the group
  protocol's problem, not this one's.
- **Who pinned is visible** to every party the pin is sent to.
- **A pin reveals** that its target exists, and its snippet reveals part of
  what it said, to everyone it is sent to — in a group, members who joined
  after the target was sent. A member who re-sends its standing pins to a
  new member does so knowingly.
- **A snippet can misquote**, as `chat-message/1.0` says of every snippet;
  an observer that holds the target shows its own text.
- **Non-repudiation is not offered.** Messages are sent `authcrypt`, which
  the recipient can verify but not prove to a third party.

## Composition

- **With `chat-message/1.0`.** Uses its message reference, and its rule
  that a reference to a deleted message stays valid.
- **With `group-chat/2.0` and `1.0`.** A pin carries the group id in
  `pthid`. `group-chat/2.0`'s `who_may_pin` setting, and its `admin`, decide
  who may pin; a group made under `1.0` has neither, and every member may.
- **With `chat-threads/1.0`.** A pin carries the `thid` of its target.
- **With [`disappearing-messages/1.0`](../../disappearing-messages/1.0/readme.md).**
  A pin or unpin carries the `expires_time` of its target, when it has one,
  and is removed with it.
- **With `discover-features/2.0`.** A pinner sends pins and unpins only to
  parties that disclose this protocol. A pin has no meaningful plain form,
  so nothing is sent in its place to a party that doesn't; such a party sees
  no pins.
- **With [`history-sync/1.1`](../../history-sync/1.1/readme.md).** A
  person's private bookmarks — messages marked for themselves alone — are
  that protocol's `bookmarks` collection, synced between the person's own
  devices and never sent to anyone else. They are the private counterpart of a pin and
  no part of this protocol.
- **With `receipts/1.0`.** A pin is not something to be marked read.

## Message Reference

### `pin`

Message Type URI: `https://wyvrn.app/chat-pins/1.0/pin`

Headers: `created_time` REQUIRED; `pthid` and `thid` as the target's.

| Field | Type | Description |
|---|---|---|
| `target` | message reference | REQUIRED. The message pinned. SHOULD carry a `snippet`. |

Schema: [`schemas/pin.json`](schemas/pin.json) validates the whole message,
headers included.

### `unpin`

Message Type URI: `https://wyvrn.app/chat-pins/1.0/unpin`

Headers: `created_time` REQUIRED; `pthid` and `thid` as the target's.

| Field | Type | Description |
|---|---|---|
| `target` | message reference | REQUIRED. The message unpinned (`id` and `author`; no snippet needed). |

Schema: [`schemas/unpin.json`](schemas/unpin.json) validates the whole
message, headers included.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. The starting point is a new `src/handlers/chatPins/chatPinsHandler.ts` registered in `src/services/didcomm/messageRouter.ts`, with the who-may-pin check against the group record from `src/services/storage/groupsRepository.ts`.

## Endnotes

### Why a pin is not a reaction

A reaction is one party's statement about its own feelings, and
`message-reactions/1.0` has each party restate its whole set. A pin is a
statement about the conversation, which anyone allowed may undo whoever made
it, so it is a per-target state with a last-writer-wins order rather than a
per-party set.

### Future Considerations

- A pinned message's position in the list chosen by the pinner, rather than
  by when it was pinned.
- A limit on the number of pins agreed by the conversation, as a group
  setting.
- Telling a member who joined later about the pins a conversation already
  has, without each pinner re-sending its own.
