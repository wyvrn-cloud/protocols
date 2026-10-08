---
title: Message Reactions
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/message-reactions/1.0
status: Proposed
summary: Lets a party attach emoji reactions to a message in a conversation, and change or remove them, by stating the full set of emoji it currently has on that message.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A party reacts to a message by sending the complete set of emoji it
currently has on that message. Sending a different set changes its
reactions; sending an empty set removes them.

## Motivation

`basicmessage/2.0` lists "emoji responses" as out of its scope, and nothing
else in the didcomm.org registry covers them.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `reactor` | States its reactions to a message. |
| `observer` | Receives that statement and shows the reactions. |

Every party in a conversation may play both roles.

## Connectivity

The same as the conversation the message belongs to: two parties, or, in a
group ([`group-chat/1.0`](../../group-chat/1.0/readme.md)), the reactor
sends its statement separately to every other member.

## States

There is no exchange to track. Each observer keeps, per message and per
reactor, the latest set that reactor stated.

## Basic Walkthrough

1. Alice sent a message with `id` `m1`.
2. Bob reacts with a thumbs-up. His agent sends:

   ```json
   {
     "id": "r1",
     "type": "https://wyvrn.app/message-reactions/1.0/reactions",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791400000,
     "body": {
       "to": { "id": "m1", "author": "did:example:alice" },
       "emoji": ["👍"]
     }
   }
   ```
3. Bob adds a heart as well. His agent sends the whole set again, now
   `["👍", "❤️"]`, with a later `created_time`.
4. Bob takes the thumbs-up back: the set becomes `["❤️"]`.
5. Bob removes his last reaction: the set becomes `[]`.

At every step Alice's agent replaces what it held for Bob on `m1` with the
set just received.

## Design By Contract

### Why the whole set, not "add" and "remove"

A reactor's statement is its complete current set, not a change to the
previous one. This makes a statement safe to receive twice, safe to receive
out of order (the later `created_time` wins), and self-correcting: a lost
statement is repaired by the next one, where a lost "remove" would leave a
reaction showing for good. It also suits a reactor with several devices,
which need only agree on the latest set rather than on a history of changes.

### Stating reactions

- `to` is a message reference as defined by
  [`chat-message/1.0`](../../chat-message/1.0/readme.md), without a
  `snippet`. It MUST refer to a message in the conversation the statement is
  sent in. The message may be of any type; reactions are not limited to
  `chat-message/1.0` messages.
- `emoji` is an array of distinct strings, each one emoji as a Unicode
  sequence, in the order the reactor added them. It MAY be empty.
- `created_time` MUST be set. A reactor's later statement about the same
  message MUST carry a later `created_time` than its earlier ones.
- In a group conversation the statement carries the group's id in `pthid`.
- A reactor MAY react to its own message, and to a message that has been
  deleted (see `chat-message/1.0`: deletion cannot be enforced, so it cannot
  be made a condition here).

### Observing

- An observer MUST replace, not merge: the set it holds for a reactor on a
  message becomes the set in that reactor's statement with the latest
  `created_time`. A statement older than the one it holds MUST be ignored.
- The reactor is the DID the statement's encryption authenticates.
- A statement about a message the observer doesn't hold SHOULD be kept and
  applied if the message arrives: the two travel separately and can arrive
  in either order.
- **The limit.** A message shows at most 20 distinct emoji as reactions,
  from all reactors together. An observer that would exceed that shows the
  20 it learned of first and ignores the rest. A reactor SHOULD NOT add an
  emoji that would be the 21st, though it may always add one already
  present. (This limit is on reactions only; it says nothing about emoji in
  a message's own text.)
- A reaction is not a message in the conversation: an observer SHOULD NOT
  notify its user of one or count it as unread.

## Security

- Who reacted is visible to every party the statement is sent to. There is
  no anonymous reaction.
- A reactor can only speak for itself: an observer takes the reactor from
  the authenticated sender, so nobody can add or remove another party's
  reactions.
- An `emoji` entry is untrusted text. An observer MUST treat an entry that
  is not a single emoji, or is unreasonably long, as absent rather than
  display it.
- In a group, a statement reaches only the members the reactor sends it to.
  Members who join later do not learn of earlier reactions unless a reactor
  states them again.

## Composition

- **With `chat-message/1.0`.** Uses its message reference.
- **With `discover-features/2.0`.** A reactor sends statements only to
  parties that disclose this protocol. A reaction has no meaningful plain
  form, so nothing is sent in its place to a party that doesn't.
- **With `receipts/1.0`.** A statement is not something to be marked read.

## Message Reference

### `reactions`

Message Type URI: `https://wyvrn.app/message-reactions/1.0/reactions`

| Field | Type | Description |
|---|---|---|
| `to` | message reference | REQUIRED. The message reacted to (`id` and `author`). |
| `emoji` | array of string | REQUIRED. The reactor's complete, current set of reactions to that message. Empty means none. |

Schema: [`schemas/reactions.json`](schemas/reactions.json) validates the whole message,
headers included.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat) | Not yet implemented.

## Endnotes

### Future Considerations

- Custom emoji as reactions, once sticker packs exist: an `emoji` entry
  that names an image in a pack rather than a Unicode sequence.
