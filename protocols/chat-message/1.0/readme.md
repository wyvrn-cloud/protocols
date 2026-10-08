---
title: Chat Message
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/chat-message/1.0
status: Proposed
summary: A chat message for one-to-one and group conversations that can reply to an earlier message, mention people, carry pictures, files, stickers and GIFs, and travel with a link preview; plus the edit and delete of a sent message. Defines the message reference and conversation model that the companion chat protocols (reactions, threads, typing, pins, disappearing messages) share.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A chat message, the way a modern messaging app understands one: Markdown text
that may reply to an earlier message, mention members of a group, carry
pictures, files, a sticker or a GIF, and bring a preview of a link it contains.
After it is sent, its author can edit its text or delete it.

This is the core of a small family of protocols. The rest — reactions, threads,
typing indicators, pins, a disappearing-message timer — are separate protocols
so that an agent can disclose exactly which it supports, but they all refer to
messages and conversations the same way, and that way is defined here:

| Protocol | Adds |
|---|---|
| `chat-message/1.0` (this one) | the message, replies, mentions, media, link previews, forwards, edits, deletes |
| [`message-reactions/1.0`](../../message-reactions/1.0/readme.md) | emoji reactions to a message |
| [`chat-threads/1.0`](../../chat-threads/1.0/readme.md) | turning a reply chain into a named side conversation |
| [`typing-indicators/1.0`](../../typing-indicators/1.0/readme.md) | "Alice is typing" |
| [`chat-pins/1.0`](../../chat-pins/1.0/readme.md) | pinning a message for everyone in a conversation |
| [`disappearing-messages/1.0`](../../disappearing-messages/1.0/readme.md) | a per-conversation timer after which messages are removed |
| [`group-chat/2.0`](../../group-chat/2.0/readme.md) | the group conversations all of the above can take place in |

## Motivation

[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0) is deliberately
minimal, and its own endnote lists replies, emoji responses, typing indicators,
read receipts, group messages and attachments as out of scope, anticipating
"more advanced and full-featured message protocols" for them. Nothing in the
didcomm.org registry provides one.

Adding fields to `basicmessage/2.0` would change a Production protocol under
every other implementation of it, so the richer message is a type of its own.
It is designed so that an agent supporting it can still talk to one that only
has `basicmessage/2.0`: every message defined here has a defined plain-text
form (see Composition), and a sender picks, per recipient, the richest form that
recipient has disclosed support for.

Two things are kept out of the message on purpose. Reactions, threads, typing,
pins and the disappearing timer are separate protocols (above): each is a
distinct behaviour an agent may or may not have, and
[`discover-features/2.0`](https://didcomm.org/discover-features/2.0) works per
protocol. And read receipts are the already-published
[`receipts/1.0`](https://didcomm.org/receipts/1.0), which this protocol only
composes with.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `sender` | Sends a message, or an edit or delete of its own earlier message. |
| `receiver` | Receives and shows them. |

Every party in a conversation plays both roles.

## Connectivity

Pairwise and mediated, like any DIDComm v2 message. A one-to-one conversation is
two parties. In a group conversation
([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)) every message is sent separately, with
the same `id`, to every other member the sender knows of — there is no
server and no shared group key.

## States

The protocol is stateless on the wire: no message here requires a reply. What a
receiver keeps is the message itself, and the edits and deletes applied to it.

| Event | Effect on the receiver's copy of the message |
|---|---|
| `message` received, `id` unknown | stored and shown |
| `message` received, `id` already held from the same sender | ignored (a redelivery, a sibling device's copy, or a group fan-out retry) |
| `edit` received from the message's author | the named fields replaced; shown as edited if `content` changed |
| `delete` received from the message's author | content, media, embeds removed; the message shown as deleted; its `id` kept so references to it still resolve |
| `edit` or `delete` received for a message not held | kept until the message arrives, then applied; discarded after a reasonable time if it never does |

## Basic Walkthrough

Alice and Bob are contacts, and each has learned through
`discover-features/2.0` that the other supports this protocol.

1. Alice sends Bob a message with a picture. The picture is small enough to
   travel inline, as a DIDComm attachment; the body says how to show it:

   ```json
   {
     "id": "m1",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400000,
     "lang": "en",
     "body": {
       "content": "Dinner at 7? This place:",
       "media": [
         { "attachment": "photo", "width": 1280, "height": 960, "blurhash": "LGF5?xYk^6#M@-5c,1J5@[or[Q6." }
       ]
     },
     "attachments": [
       {
         "id": "photo",
         "media_type": "image/jpeg",
         "filename": "bistro.jpg",
         "byte_count": 183220,
         "data": { "base64": "/9j/4AAQSkZJRg..." }
       }
     ]
   }
   ```

2. Bob replies. His message names Alice's by its `id` and author and quotes its
   first words, so that his reply makes sense even to a device that never
   received `m1`:

   ```json
   {
     "id": "m2",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791400060,
     "lang": "en",
     "body": {
       "content": "Yes! See you there",
       "reply_to": { "id": "m1", "author": "did:example:alice", "snippet": "Dinner at 7? This place:" }
     }
   }
   ```

3. Alice notices a typo and edits her message. Only the text changes; the
   picture stays:

   ```json
   {
     "id": "m3",
     "type": "https://wyvrn.app/chat-message/1.0/message-edit",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400120,
     "body": {
       "target": { "id": "m1", "author": "did:example:alice" },
       "content": "Dinner at 7:30? This place:"
     }
   }
   ```

   Bob's agent replaces the text of `m1` and marks it edited. Bob's reply
   still quotes "Dinner at 7? This place:" — a snippet is what the message
   said when it was quoted.

4. Later Alice deletes it:

   ```json
   {
     "id": "m4",
     "type": "https://wyvrn.app/chat-message/1.0/message-delete",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400300,
     "body": {
       "target": { "id": "m1", "author": "did:example:alice" }
     }
   }
   ```

   Bob's agent drops the text and the picture and shows "Message deleted" in
   their place. Bob's reply still points at `m1`; selecting its quote goes to
   the deleted line.

Had Bob's agent only supported `basicmessage/2.0`, Alice's agent would have sent
step 1 as a basic message reading `Dinner at 7? This place:` followed by a line
`[Photo: bistro.jpg]`, step 3 as a new basic message beginning `Edited:`, and
nothing at all for step 4 (see Composition).

## Design By Contract

### Conversations

A **conversation** is either a *pair* (two parties) or a *group*. The two are
told apart on the wire by one header:

| | `pthid` | Who it is sent to |
|---|---|---|
| Pair | absent | the other party |
| Group | the group's id, as [`group-chat/2.0`](../../group-chat/2.0/readme.md) (or 1.0) defines | every other member, separately, with the same message `id` |

A receiver places a message in the conversation its `pthid` and sender name,
and a group message from a DID that is not, in the receiver's own record, a
member of that group is ignored (see `group-chat/2.0`).

A **thread** ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)) is a
side conversation inside a conversation. A message in a thread carries the
thread's id in `thid`; this protocol itself never sets `thid`, and a receiver
that doesn't implement threads treats a message carrying one as an ordinary
message of its conversation.

"The **same conversation**" means the same pair, or the same group id. Every
reference defined below is confined to the conversation the message carrying it
is sent in. A receiver MUST NOT resolve a reference to a message in any other
conversation, even one it holds with a matching `id`.

### The message reference

A message reference identifies one earlier message in the same conversation:

| Field | Type | Description |
|---|---|---|
| `id` | string | REQUIRED. The `id` of the message referred to. |
| `author` | string | REQUIRED. The DID that sent it, as the referring party knows it. |
| `snippet` | string | OPTIONAL. The start of the referred message's text, at most 100 characters, as it read when the reference was made. For a message with no text, its *label* (below). |

- `id` is compared the way DIDComm compares every message id:
  case-insensitively.
- `author` lets a receiver that doesn't hold the message still say whose it
  was, and tells apart two messages that — against the rules — share an id.
  A receiver that holds the message MUST compare `author` against the
  message's sender *allowing for DID rotation*: the sender's current DID or
  any DID it has rotated away from with a verified `from_prior` both match. If
  neither does, the reference is treated as unresolved.
- A `snippet` is the referring party's claim about what the message said. A
  receiver that holds the message MAY show the message's own current text
  instead; one that doesn't MUST make clear the snippet is a quotation.
- A reference stays valid whatever later happens to its target. If the
  target is edited, a snippet already sent is not updated. If it is deleted,
  the reference remains, and what it points at is shown as deleted: deletion
  cannot be enforced on every agent, so a rule that forbade referring to a
  deleted message would only be obeyed by those that knew of the deletion.
- An unresolvable reference is not an error. The receiver shows what it has
  (the snippet, or "Original message unavailable") and MAY resolve it later,
  if the message arrives.

The companion protocols use this reference unchanged: a reaction's `to`, a
thread's `root`, a pin's `target`, and this protocol's own `reply_to` and
`target` are all message references.

### The label of a message with no text

Every message has a one-line plain-text **label** for wherever its text would
be shown but can't be — a snippet, a notification, a conversation list. It is
the message's `content` if that is non-empty; otherwise, for its first media
item: `Photo` (an image), `Video`, `Audio`, `GIF`, `Sticker`, or `File:
<filename>`. An implementation MAY localize these.

### Sending a message

- `content` is the text of the message in Markdown, at most 8,000 characters.
  The dialect is CommonMark with GitHub extensions (tables, strikethrough,
  task lists, autolinks, fenced code blocks naming a language), where a line
  break the author typed is a line break, and `||text||` marks a spoiler. A
  receiver renders what it understands; Markdown read as text is still
  readable, which is the point of using it.
- `content` MAY be empty only when `media` is not. A message needs text or
  media; it MUST NOT have neither.
- `created_time` MUST be set, and `lang` SHOULD be (the language of
  `content`), as for `basicmessage/2.0`.
- A message's `id` SHOULD be a UUID. In a group the same `id` is sent to every
  member.
- A sender MUST NOT set `reply_to` to a message from another conversation.
  A sender SHOULD include a `snippet` in `reply_to`: a receiver may never have
  had the original.

**Mentions.** A mention is written in `content` as a Markdown link whose
destination is the mentioned member's DID — `[@Alice](did:example:alice)` —
and listed in `mentions`. The text form is what any receiver shows (a
receiver that knows this protocol shows it as a mention; one that doesn't, as
a link whose text is a readable name); the list is what a receiver acts on,
without parsing the text. The two MUST agree: every DID in `mentions` appears
as a link destination in `content`, and vice versa. `{ "everyone": true }`
mentions everyone in the conversation, written in the text as `@everyone`.
Mentions are for groups: a sender MUST NOT mention in a pair, and a receiver
ignores `mentions` on a pair message. A sender MUST NOT mention a DID that is
not a member of the group; a receiver ignores one.

**Media.** Pictures, files, GIFs and stickers all travel the same way: a
DIDComm attachment in `attachments[]`, and an entry in `body.media` that
points at it and says how to show it.

- An attachment MUST have an `id`, a `media_type`, and SHOULD have a
  `filename` and `byte_count`. Its `description` is alternative text.
- The bytes are either **inline** (`data.base64`), for an attachment of up to
  256 KiB, or **by reference** (`data.links`, one or more URLs), for anything
  larger, in which case `data.hash` MUST be present: a
  [multihash](https://multiformats.io/multihash/), base58btc-encoded, of the
  bytes at the link, exactly as stored. A sender SHOULD shrink a picture to
  fit inline unless the person chose to send the original.
- Bytes by reference on a storage service SHOULD be encrypted before upload,
  and the item's `ciphering` then carries the key, in the shape
  [`media-sharing/1.0`](https://didcomm.org/media-sharing/1.0) defines
  (`algorithm`, and `parameters` holding `key`, `iv`, and `tag`, hex-encoded).
  This protocol REQUIRES support for `aes-256-gcm`, whose `tag` is the GCM
  authentication tag. A receiver MUST verify `data.hash` and the tag before
  treating the bytes as the attachment. Bytes at a link a sender does not
  control (a GIF on its provider) are sent without `ciphering`.
- `media[].kind` is how to show it: `attachment` (the default — a picture or
  video shown in a frame, any other file as a file), `gif` (an animated image
  shown looping, without a frame), or `sticker` (a single image shown large
  and alone, without a frame). A `sticker` item also carries `sticker`: the
  pack and sticker ids, and the service the pack can be fetched from (see
  `discussions/chat-services.md`). A sticker SHOULD still be attached inline
  or by reference so that it shows without the service.
- `width`, `height`, `duration` (seconds), a `preview` (the attachment id of
  a small inline thumbnail) and a `blurhash` let a receiver lay the message out
  before it has the bytes, and decide whether to fetch them at all: a
  receiver MAY defer fetching bytes by reference until asked (a mobile-data
  or tap-to-load setting).
- How long bytes stay at a link is the storage service's business; a receiver
  that finds a link gone MAY ask the sender for the item again with
  `media-sharing/1.0`'s `request-media`, naming the attachment id.

**Link previews.** A sender that has link previews turned on MAY include, in
`embeds`, a preview it built of a link that appears in `content`: the page's
title, description, site name, and a thumbnail attached inline. A sender MUST
NOT include an embed for a URL that is not in `content`. A receiver shows the
preview as sent and never has to contact the site; it MAY offer to load the
live page instead, and it MAY ignore embeds entirely. A preview that is ready
only after the message went out follows as a `message-edit` carrying `embeds`
(see Editing); a sender SHOULD give up on that after about 10 seconds.

**Forwarding.** A message copied from another conversation carries
`forwarded`. The sender chooses whether to name the original author
(`author`, and `author_name` as the sender knew them) and when it was sent
(`created_time`). A forwarded message is otherwise an ordinary new message of
the conversation it is sent in: it has its own `id`, and it never carries a
`reply_to`, since a reference cannot cross conversations.

### Editing

- A `message-edit` names its `target` and carries the fields it changes:
  `content`, `mentions`, `embeds`, each optional, each replacing that field
  of the target entirely. A field absent from the edit is unchanged. `media`,
  `reply_to`, `forwarded` and the attachments cannot be edited.
- Only the target's author may edit it. A receiver MUST ignore an edit whose
  authenticated sender is not the target's sender (DID rotation allowed for,
  as for references).
- There is no time limit on editing. A receiver shows a message whose
  `content` was changed by an edit as edited; an edit that changes only
  `embeds` or `mentions` does not mark it so.
- Edits are ordered by `created_time`: for each field, the edit with the
  latest `created_time` wins, and an edit older than one already applied to
  the same field is ignored. A sender's edits of one message MUST carry
  strictly increasing `created_time`.
- What a receiver does with earlier versions is its own choice; the wire
  carries only the new text.

### Deleting

- A `message-delete` names its `target`. Only the target's author may delete
  it; a receiver MUST ignore a delete from anyone else. (A group admin cannot
  delete another member's message — see `group-chat/2.0`.)
- On a delete the receiver removes the message's text, media, attachment
  bytes and embeds, and shows a placeholder ("Message deleted") in its place.
  It keeps the `id`, sender and time, so that references to it still resolve
  and reactions to it still show under the placeholder.
- A delete for a message the receiver doesn't hold is kept as a tombstone,
  so that the message is not shown if it arrives afterwards.
- A delete is a request. It cannot remove a message from a device that keeps
  it, and this protocol does not pretend otherwise.

### Receiving

- A receiver MUST accept a `message` it already holds under the same `id` from
  the same sender without storing or showing it again.
- Unknown body fields MUST be ignored, so that a later minor version can add
  to the message without breaking this one.
- A receiver SHOULD treat a reply to one of its own messages like a mention
  for notification purposes (breaking through a muted conversation), subject
  to the person's settings.
- A `message` carrying an unknown `pthid` (a group the receiver has no record
  of) is not shown; a receiver MAY keep it briefly in case the group's
  invitation is about to arrive.

## Security

- **The sender is the DID the encryption authenticates.** Every message here
  MUST be sent sender-authenticated (`authcrypt`), and a receiver MUST ignore
  one that is not. No DID named inside a message — `reply_to.author`,
  `target.author`, `forwarded.author`, a mention — is authenticated by it.
- **Only the author edits or deletes.** The rule is enforced by comparing the
  authenticated sender with the held message's sender; a receiver that does
  not hold the target cannot check and MUST wait for it rather than apply the
  change on trust.
- **A snippet can misquote**, and a `forwarded.author` can lie. A receiver
  that holds the original shows the real text; one that doesn't cannot tell,
  which is why a snippet is presented as the replier's quotation and a
  forward as "forwarded, said to be from". An implementation MUST NOT show a
  forwarded message as if it had received it from its claimed author.
- **A reference reveals** that its target exists, and a snippet reveals part
  of what it said, to everyone the message is sent to — in a group, members
  who joined after the original was sent.
- **A link is a fetch.** Bytes by reference and `gif` items are fetched from
  a third-party host by every receiver that shows them, revealing the
  receiver's address to that host. A receiver SHOULD offer a setting to load
  them only on request. Link previews are built by the *sender* for exactly
  this reason: a link can be sent precisely to learn who opens it.
- **A key in a message is a key for everyone who has the message.** The
  `ciphering` of a stored item protects it from the storage service, not from
  any recipient; a storage service should delete an item once every recipient
  has fetched it or after a time limit (see `discussions/chat-services.md`).
- **Markdown is untrusted input.** A receiver MUST sanitize rendered content:
  no raw HTML, no scripts, link destinations limited to safe schemes (and the
  DID of a mention), images only from attachments it already holds. Mention
  links in particular MUST be rendered from the `mentions` list and the
  receiver's own record of the member, never by trusting the link text as a
  name: `[@Alice](did:example:mallory)` is a message that lies.
- **Attachments are untrusted bytes.** A receiver MUST treat `media_type` as a
  claim, never execute an attachment, and should bound what it is willing to
  store or fetch.
- **Non-repudiation is not offered.** As `basicmessage/2.0`, messages are
  sent `authcrypt`, which the recipient can verify but not prove to a third
  party.

## Composition

- **With `discover-features/2.0`.** A sender learns which of this family a
  recipient supports and sends each recipient the richest form it supports.
  For a group this means asking *every member*, not only direct contacts, and
  one group message may go out in different forms to different members.
- **With `basicmessage/2.0`** — the plain form. To a recipient that does not
  disclose this protocol, a `message` is sent as a
  `basicmessage/2.0/message` whose `content` is, in order: the `reply_to`
  snippet as a Markdown quotation (`> …`) followed by a blank line, if any;
  the message's `content` as it is (mention links read as names); and then
  one line per media item: its link, for an item sent by reference without
  `ciphering` (a GIF), otherwise its label in brackets (`[Photo: bistro.jpg]`,
  `[Sticker]`, `[File: report.pdf]`). The two forms carry the same `id`, so a
  party that receives either stores the same message. A `message-edit` that
  changes `content` is sent as a *new* basic message, with its own `id`,
  whose content is `Edited:` followed by the plain form; an edit of anything
  else, and a `message-delete`, are not sent.
- **With `group-chat/2.0` and `1.0`.** Group content may be this message
  type, with `pthid` used identically to `basicmessage/2.0` content.
- **With `receipts/1.0`.** Unchanged: a receipt names a message by `id`,
  whichever type it was. In a group, `message-receipts` go to the message's
  author only, not to every member.
- **With `media-sharing/1.0`.** This protocol reuses its `ciphering` shape
  and its `request-media` message (naming an attachment id) for an item whose
  link has gone, rather than its `share-media`, so that a picture is a chat
  message like any other — one thing to reply to, react to, pin or delete.
- **With DIDComm threading.** This protocol sets neither `thid` nor, in a
  pair, `pthid`. A reply says which single message it answers; it does not by
  itself form a DIDComm thread. `thid` is used by `chat-threads/1.0`.
- **With `disappearing-messages/1.0`.** A message in a conversation with a
  timer carries `expires_time`.

## Message Reference

### `message`

Message Type URI: `https://wyvrn.app/chat-message/1.0/message`

Headers: `created_time` REQUIRED; `lang` SHOULD be set; `pthid` in a group;
`thid` only in a thread; `expires_time` only with a disappearing timer.

| Field | Type | Description |
|---|---|---|
| `content` | string | REQUIRED. The text, in Markdown, at most 8,000 characters. May be empty only if `media` is not. |
| `reply_to` | message reference | OPTIONAL. The message this one answers. |
| `mentions` | array of object | OPTIONAL. Each `{ "did": "<member DID>" }` or `{ "everyone": true }`. Groups only. |
| `media` | array of media item | OPTIONAL. Pictures, files, GIFs, stickers — each pointing at an attachment. |
| `embeds` | array of link preview | OPTIONAL. Previews of links in `content`, built by the sender. |
| `forwarded` | object | OPTIONAL. Present when the message was forwarded from another conversation: `author` (DID, optional), `author_name` (string, optional), `created_time` (integer, optional). |

A **media item**:

| Field | Type | Description |
|---|---|---|
| `attachment` | string | REQUIRED. The `id` of the entry in `attachments[]`. |
| `kind` | string | OPTIONAL. `attachment` (default), `gif`, or `sticker`. |
| `ciphering` | object | OPTIONAL. For bytes by reference that were encrypted: `algorithm` (`aes-256-gcm` REQUIRED to be supported) and `parameters` (`key`, `iv`, `tag`, hex). |
| `width`, `height` | integer | OPTIONAL. Pixels, for an image or video. |
| `duration` | number | OPTIONAL. Seconds, for audio or video. |
| `preview` | string | OPTIONAL. The attachment id of a small inline thumbnail. |
| `blurhash` | string | OPTIONAL. A [BlurHash](https://blurha.sh) placeholder. |
| `sticker` | object | REQUIRED when `kind` is `sticker`: `pack_id` (string), `sticker_id` (string), `service` (URL, optional). |

A **link preview**:

| Field | Type | Description |
|---|---|---|
| `url` | string | REQUIRED. The link, exactly as it appears in `content`. |
| `title` | string | OPTIONAL. |
| `description` | string | OPTIONAL. |
| `site_name` | string | OPTIONAL. |
| `image` | string | OPTIONAL. The attachment id of an inline thumbnail. |

Schema: [`schemas/message.json`](schemas/message.json).

### `message-edit`

Message Type URI: `https://wyvrn.app/chat-message/1.0/message-edit`

Headers: `created_time` REQUIRED; `pthid` and `thid` as the target's.

| Field | Type | Description |
|---|---|---|
| `target` | message reference | REQUIRED. The message edited (`id` and `author`; no snippet needed). |
| `content` | string | OPTIONAL. The new text, replacing the old. |
| `mentions` | array of object | OPTIONAL. Replaces the old list. |
| `embeds` | array of link preview | OPTIONAL. Replaces the old list. |

At least one of `content`, `mentions`, `embeds` MUST be present.

Schema: [`schemas/message-edit.json`](schemas/message-edit.json).

### `message-delete`

Message Type URI: `https://wyvrn.app/chat-message/1.0/message-delete`

Headers: `created_time` REQUIRED; `pthid` and `thid` as the target's.

| Field | Type | Description |
|---|---|---|
| `target` | message reference | REQUIRED. The message deleted. |

Schema: [`schemas/message-delete.json`](schemas/message-delete.json).

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. Its `basicmessage/2.0` handler (`src/handlers/basicMessage/basicMessageHandler.ts`) and Markdown rendering (`src/components/chat/MessageMarkdown.tsx`) are the starting point.

## Endnotes

### Why the plain form is not a lossless one

A `basicmessage/2.0` receiver gets the text, a quotation of what was replied
to, and a line saying a picture or file was there. It does not get the bytes:
a basic message has no defined attachments, and a line of base64 in the text
would be worse than nothing. Someone who needs the picture needs the app
updated, which every device of this family is expected to do together.

### Why a forward carries no reference

A reference is confined to one conversation so that a receiver can never be
induced to resolve, and reveal, a message from a different one. A forward is
by definition from somewhere else, so it carries a claim about its origin
rather than a reference to it.

### Future Considerations

- Custom emoji in text, as a media item inline with the text rather than
  below it.
- Voice notes: `audio` media with a waveform preview.
- Pictures edited after sending (today, media is immutable).
- A server-relayed form, for community channels, where the author signs the
  plaintext and a relay forwards it; the message reference and conversation
  model here are meant to hold up under that.
