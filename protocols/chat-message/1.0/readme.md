---
title: Chat Message
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/chat-message/1.0
status: Proposed
summary: A chat message that can say which earlier message it answers. It carries the same text a basicmessage/2.0 message would, plus a reference to the message being replied to, and defines that reference for other protocols to reuse.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A person-to-person chat message, like
[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0), that can also be
a *reply*: it names the earlier message it answers and carries a short copy
of what that message said.

It also defines the **message reference** — how one message points at
another — which [`message-reactions/1.0`](../../message-reactions/1.0/readme.md)
uses, and which later protocols (threads, edits, deletes) are expected to use
too.

## Motivation

`basicmessage/2.0` lists "message replies (threading)" as explicitly out of
its scope, and nothing else in the didcomm.org registry covers a reply.
Adding a field to `basicmessage/2.0` would break compatibility with every
other implementation of it, so a reply needs a message type of its own.

This protocol is deliberately a small step from `basicmessage/2.0`: one
message type, the same `content`, one new optional field. An agent that
supports it can still talk to one that doesn't by sending
`basicmessage/2.0` instead (see Composition).

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `sender` | Sends a message. |
| `receiver` | Receives it. |

Either party in a conversation may play either role at any time.

## Connectivity

Two parties for a one-to-one conversation. In a group conversation
([`group-chat/1.0`](../../group-chat/1.0/readme.md)) the sender sends the
same message — same `id` — separately to every other member.

## States

The protocol is stateless: one message, no reply required. What a receiver
keeps is the message itself.

## Basic Walkthrough

1. Alice sends Bob a message with `id` `m1`: "Dinner at 7?"
2. Later, Bob replies to it. His message has its own `id`, `m2`, and a
   `reply_to` naming `m1`, written by Alice, with the snippet "Dinner at 7?":

   ```json
   {
     "id": "m2",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791400000,
     "lang": "en",
     "body": {
       "content": "Yes, see you there",
       "reply_to": {
         "id": "m1",
         "author": "did:example:alice",
         "snippet": "Dinner at 7?"
       }
     }
   }
   ```
3. Alice's agent shows Bob's message with a quoted preview above it. If it
   still holds `m1`, selecting the preview goes to it. If it doesn't — the
   message was never received, or has since been removed — the snippet is
   what it shows.

A message without `reply_to` is an ordinary message.

## Design By Contract

### The message reference

A message reference is an object that identifies one earlier message in the
**same conversation** as the message carrying it:

| Field | Type | Description |
|---|---|---|
| `id` | string | REQUIRED. The `id` of the message referred to. |
| `author` | string | REQUIRED. The DID that sent it, as the referring party knows it. |
| `snippet` | string | OPTIONAL. The start of the referred message's text, at most 100 characters, as it read when the reference was made. For a message with no text, a short label of what it was (for example `Photo`). |

- "The same conversation" means: between the same two parties, or — for a
  message carrying a `pthid` — within the same group. A receiver MUST NOT
  resolve a reference to a message in any other conversation, even one it
  holds with a matching `id`. A reference it cannot resolve is not an error.
- `id` is compared the way DIDComm compares all message ids:
  case-insensitively.
- `author` lets a receiver that doesn't hold the message still say whose it
  was, and tells apart two messages that — against the rules — share an id.
  A receiver that does hold the message and finds a different sender MUST
  treat the reference as unresolved.
- A `snippet` is the referring party's claim about what the message said.
  A receiver that holds the message MAY show the message's own current text
  instead; one that doesn't MUST make clear the snippet is a quotation, not
  the message.
- A reference stays valid whatever later happens to its target. If the
  target is edited, a snippet already sent is not updated. If it is deleted,
  the reference remains, and what it points at is shown as deleted: deletion
  cannot be enforced on every agent, so a protocol that forbade referring
  to a deleted message would only be obeyed by those that knew.

### Sending

- `content` follows `basicmessage/2.0`: the text of the message. A sender
  MAY use Markdown; a receiver that doesn't render it shows it as text.
- A sender MUST NOT set `reply_to` to a message from another conversation.
- A sender SHOULD include `snippet`: a receiver may never have had the
  original.
- `created_time` MUST be set, and `lang` SHOULD be, as for
  `basicmessage/2.0`.
- In a group conversation the message carries the group's id in `pthid`,
  exactly as `group-chat/1.0` specifies for `basicmessage/2.0` content.

### Receiving

- A receiver MUST accept a message it has already stored under the same
  `id` from the same sender without storing it twice.
- Unknown body fields MUST be ignored, so that a later minor version can add
  to the message (mentions and link previews are expected) without breaking
  this one.

## Security

- The sender of a message is the DID its encryption authenticates, never a
  DID named inside it. `reply_to.author` is a claim about a *different*
  message and is not authenticated by this one.
- A snippet can misquote. Someone can send a reply whose snippet shows words
  the original never contained. A receiver that holds the original can show
  the real text; one that doesn't cannot tell, which is why a snippet must
  be presented as the replier's quotation.
- A reference reveals that its target exists, and a snippet reveals part of
  what it said, to everyone the reply is sent to. In a group, that includes
  members who joined after the original was sent.

## Composition

- **With `basicmessage/2.0`.** A sender learns through
  [`discover-features/2.0`](https://didcomm.org/discover-features/2.0)
  whether a recipient supports this protocol, and sends each recipient the
  richest form it supports. To a recipient that doesn't, a reply is sent as
  a `basicmessage/2.0` message whose `content` begins with the snippet as a
  Markdown quotation, followed by a blank line and the reply:

  ```
  > Dinner at 7?

  Yes, see you there
  ```

  The two forms of one message carry the same `id`, so a party that
  receives either stores the same message.
- **With `group-chat/1.0`.** Group content may be this message type in
  place of `basicmessage/2.0`, with `pthid` used identically.
- **With `receipts/1.0`.** Unchanged: a receipt names a message by `id`,
  whichever type it was.
- **With `message-reactions/1.0`.** A reaction refers to a message with the
  message reference defined here.
- **With DIDComm threading.** This protocol does not use `thid`. A reply
  says which single message it answers; it does not, by itself, form a
  DIDComm thread. That header is left free for a later threads protocol,
  where a named side conversation is a real thread whose `pthid` is the
  conversation it belongs to.

## Message Reference

### `message`

Message Type URI: `https://wyvrn.app/chat-message/1.0/message`

| Field | Type | Description |
|---|---|---|
| `content` | string | REQUIRED. The text of the message. May be empty only if a later version's fields give the message other content. |
| `reply_to` | message reference | OPTIONAL. The message this one answers. See Design By Contract. |

Schema: [`schemas/message.json`](schemas/message.json) validates the whole message,
headers included.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat) | Not yet implemented.

## Endnotes

### Future Considerations

- Structured content beside `content`, as minor versions: mentions of group
  members, and a link preview built by the sender.
- Threads, edits and deletes, each as its own protocol using the message
  reference.
