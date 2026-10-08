---
title: Message Reactions
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/message-reactions/1.0
status: Proposed
summary: Lets a party attach emoji reactions to a message in a conversation, and change or remove them, by stating the full set of emoji it currently has on that message. A companion to chat-message/1.0, whose message reference and conversation model it uses.
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

This is one of the companion protocols of
[`chat-message/1.0`](../../chat-message/1.0/readme.md), which defines how a
message and a conversation are referred to; this protocol adds reactions
and nothing else, so that an agent can disclose exactly that.

## Motivation

[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0) lists "emoji
responses" as out of its scope, and nothing else in the didcomm.org
registry covers them. `chat-message/1.0` keeps them out of its message on
purpose (see its Motivation): a reaction is a distinct behaviour an agent
may or may not have, and
[`discover-features/2.0`](https://didcomm.org/discover-features/2.0) works
per protocol.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `reactor` | States its reactions to a message. |
| `observer` | Receives that statement and shows the reactions. |

Every party in a conversation may play both roles.

## Connectivity

The same as the conversation the message belongs to, as `chat-message/1.0`
defines it: in a pair, the reactor sends its statement to the other party;
in a group ([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)), the reactor sends it separately,
with the same `id`, to every other member that discloses this protocol.

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

- `to` is a **message reference** as `chat-message/1.0`'s Design By
  Contract defines it (`id` and `author`; a `snippet` is not used here).
  Everything that section says about a reference applies: it MUST refer to
  a message in the conversation the statement is sent in, `author` is
  matched allowing for DID rotation, and an unresolvable reference is not
  an error. The message may be of any type; reactions are not limited to
  `chat-message/1.0` messages.
- `emoji` is an array of distinct entries, in the order the reactor added
  them. It MAY be empty. In this version every entry is a **string**: one
  emoji, as a single Unicode emoji sequence (a character with the Emoji
  property, or an emoji modifier, flag, keycap or ZWJ sequence), nothing
  more. A later minor version may add an **object** entry for an emoji
  that is not a Unicode sequence (see Future Considerations); an observer
  of this version MUST treat an entry it does not understand — an object,
  or a string that is not a single emoji — as absent: not shown, and not
  counted towards the limit below. Two entries are the same emoji if they
  are the same string after Unicode normalization (NFC); a reactor SHOULD
  send the fully-qualified form.
- `created_time` MUST be set. A reactor's later statement about the same
  message MUST carry a later `created_time` than its earlier ones.
- The statement carries the conversation's headers as `chat-message/1.0`
  defines them: in a group, the group's id in `pthid`; for a message in a
  thread ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)), the
  thread's id in `thid`, and otherwise no `thid`.
- A reaction to a message that carries an `expires_time` (a conversation
  with a [`disappearing-messages/1.0`](../../disappearing-messages/1.0/readme.md)
  timer) carries the same `expires_time`: the reaction goes when the
  message goes.
- A reactor MAY react to its own message, and to a message that has been
  deleted (see `chat-message/1.0`: deletion cannot be enforced, so it cannot
  be made a condition here; reactions to a deleted message show under its
  placeholder).

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

### What an implementation offers (non-normative)

Nothing here is required by the protocol; it records what `wyvrn-chat`
intends, so that implementations behave alike where it matters to a person.

- A quick-reaction bar offers the person's six most-used emoji, which
  start out as thumbs up, red heart, face with tears of joy, face with open
  mouth, loudly crying face, and folded hands (👍 ❤️ 😂 😮 😢 🙏), with a
  full picker behind it.
- Reacting is offered on a message the agent holds, from anyone, including
  the person's own. It is not offered on a line that is not a message
  anyone sent — a system line such as "Bob joined" — or on a message of the
  person's own that failed to send, since no one else holds it to react to.

## Security

- Who reacted is visible to every party the statement is sent to. There is
  no anonymous reaction.
- A reactor can only speak for itself: an observer takes the reactor from
  the authenticated sender, so nobody can add or remove another party's
  reactions. Every statement MUST be sent sender-authenticated
  (`authcrypt`), and an observer MUST ignore one that is not.
- An `emoji` entry is untrusted text. An observer MUST treat an entry that
  is not a single emoji, or is unreasonably long, as absent rather than
  display it (see Stating reactions).
- In a group, a statement reaches only the members the reactor sends it to.
  Members who join later do not learn of earlier reactions unless a reactor
  states them again. A statement from a DID that is not, in the observer's
  own record, a member of the group it names is ignored, as
  `chat-message/1.0` says of every message in a group.
- A reference reveals that its target exists to everyone the statement is
  sent to, as `chat-message/1.0`'s Security section says of every
  reference.

## Composition

- **With `chat-message/1.0`.** Uses its message reference and its
  conversation model (pair or group by `pthid`; the same conversation only).
  Reactions to a deleted message show under its placeholder, which is why
  a delete keeps the message's `id`.
- **With `discover-features/2.0`.** A reactor sends statements only to
  parties that disclose this protocol. A reaction has no plain form, so
  nothing is sent in its place to a party that doesn't; in a group, a
  statement may go to some members and not others.
- **With `group-chat/2.0` and `1.0`.** A statement in a group carries the
  group's id in `pthid` and is fanned out like the message it reacts to.
- **With `chat-threads/1.0`.** A reaction to a message in a thread carries
  the thread's `thid`. An observer that doesn't implement threads treats
  it as a reaction to that message in its conversation, which is where the
  message is for that observer anyway.
- **With `disappearing-messages/1.0`.** A reaction to a message that
  carries an `expires_time` carries the same `expires_time`, and an
  observer removes it when it removes the message.
- **With `receipts/1.0`.** A statement is not something to be marked read.

## Message Reference

### `reactions`

Message Type URI: `https://wyvrn.app/message-reactions/1.0/reactions`

Sent by a `reactor` to every `observer` in the conversation.

Headers: `created_time` REQUIRED; `pthid`, `thid` and `expires_time` as the
message reacted to carries them.

| Field | Type | Description |
|---|---|---|
| `to` | message reference | REQUIRED. The message reacted to (`id` and `author`). |
| `emoji` | array of string | REQUIRED. The reactor's complete, current set of reactions to that message, each one emoji as a Unicode sequence, distinct, in the order added; at most 20. Empty means none. |

Schema: [`schemas/reactions.json`](schemas/reactions.json).

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. A handler at `src/handlers/messageReactions/` registered in `src/services/didcomm/messageRouter.ts` is the starting point, with the reaction sets kept per message in its message store.

## Endnotes

### Why a statement of a sender's own set, not a count

An observer shows a count per emoji by adding up the reactors it has heard
from. A count sent on the wire would be one party's claim about everyone's
reactions, which nothing authenticates; a set is a claim about the
sender's own, which the encryption does.

### Future Considerations

- Custom emoji as reactions, once sticker packs exist: an `emoji` entry in
  object form, naming an image in a pack rather than a Unicode sequence —
  for example `{ "pack_id": "…", "sticker_id": "…", "service": "…" }` in
  the shape `chat-message/1.0`'s `sticker` item uses. This version already
  says what an observer does with an entry it doesn't understand, so that
  addition is a minor version.
