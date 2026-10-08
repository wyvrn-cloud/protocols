---
title: History Sync
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/history-sync/1.1
status: Proposed
summary: Reconciles locally-stored state (message history, contacts, groups, and the small per-person sets a chat app keeps — followed threads, bookmarks, mutes, blocks, sticker packs) between a person's own devices with no shared server-side copy, using a cheap count/cursor/hash check, a chunked-hash manifest to localize divergence, and per-item diffing so only what's actually missing or different ever gets transferred — with each device free to keep only a bounded, rolling window of history rather than a full copy. Messages are no longer append-only: an edit, a delete, a reaction or a pin changes a held message, and this version reconciles those changes. Adds a search of one conversation across the person's devices.
tags:
  - multi-device
  - synchronization
  - messaging
authors:
  - name: wyvrn
---

## Summary

History Sync reconciles a person's own devices with each other so that
each one converges on the *same* local state within whatever range it
actually wants to keep, without any of them ever holding a full permanent
copy of everything, and without a server that stores message content on
their behalf. It borrows rsync's actual technique, not just its name: a
cheap count/cursor/hash comparison first, then chunk-level hashes to
localize where two devices actually differ, then a per-item hash/id diff
*within* only the mismatched chunk, so a transfer only ever contains the
specific items that are missing or different — never a whole re-send of
anything already held identically by both sides. A separate, unrelated
request type covers the reactive case (a person scrolling back further
than a device's local window currently holds), which doesn't need any of
the chunking machinery above; a third covers a search of one conversation
on a sibling that keeps more history than this device does.

This protocol assumes [`multi-device/1.0`](../../multi-device/1.0/readme.md)
for how a device learns which sibling devices exist and what their
messaging DIDs are; every message here is addressed to a specific sibling
device, never broadcast.

Version 1.1 is the version for
[`chat-message/1.0`](../../chat-message/1.0/readme.md) and its companion
protocols. In 1.0 a message, once held, never changed, so a count and two
cursors proved two devices agreed on a conversation. With `chat-message/1.0`
a message's text can be edited and the message deleted, and
[`message-reactions/1.0`](../../message-reactions/1.0/readme.md),
[`chat-pins/1.0`](../../chat-pins/1.0/readme.md) and
[`chat-threads/1.0`](../../chat-threads/1.0/readme.md) attach state to it
after it arrived. 1.1 says exactly what a message's hash covers now, adds a
content hash to the summary of every `messages:*` collection, says how a
deleted message travels, adds the small per-person collections those
protocols need synced (followed threads, bookmarks, mutes, blocks, sticker
packs, and one setting), and adds `search-request`/`search-response`. The
chunk and manifest machinery is unchanged. Everything new syncs between a
person's own devices, as everything in 1.0 did.

## Motivation

A DIDComm mediator is a transient relay, not an archive — content is
removed from its queue once picked up and acknowledged, by design (see
`messagepickup/3.0`). That means a device enrolled after some history
already exists, or one that was offline longer than the mediator's own
retention/queue window, has no way to recover anything from the mediator
itself; whatever it's missing can only come from another device that still
has it.

Since [`multi-device/1.0`](../../multi-device/1.0/readme.md) copies the
Identity DID's own content key to every enrolled device, an *ordinary*
offline period is usually a non-issue for message content specifically —
a device that reconnects while the mediator still holds a message
addressed to the shared Identity DID can pick it up directly, independent
of any sibling. This protocol's real, narrower job is what that doesn't
cover: catching up a device that's newly enrolled (everything that existed
before it joined), recovering from an offline period that outlasted the
mediator's own retention window, and reconciling local state that was
never part of shared-content delivery in the first place — contacts,
groups, read state, and the device roster itself.

The same applies to a change to a message. An edit, a delete, a reaction
or a pin is a message of its own on the wire, picked up by whichever
devices were there to pick it up; a device that was away for longer than
the mediator kept it holds the message as it was. Nothing on the mediator
says which held messages have since changed, so that too can only be
learned from a sibling — and a sibling that never saw the delete must not
hand the deleted text back.

The obvious approach — every device eventually holds a full copy of
everything — doesn't fit real devices. A phone has meaningfully less
storage than a laptop and a person may deliberately not want years of
history sitting on a device they carry around and could lose. So this
protocol treats "how much history a device keeps" as a purely local,
per-device policy (unbounded, or a rolling window by count or age) that
reconciliation must respect rather than override: two devices with
genuinely different intended retention are not "out of sync" just because
one has deliberately forgotten what the other still holds. A search of a
conversation then has the same shape as scrolling back: this device's
window first, and a sibling that kept more for the rest.

Real prior art here is more limited than it looks. Signal's linked devices
(Desktop, etc.) do not backfill retroactively at all — they only see
messages sent after linking, via near-real-time copies relayed alongside
each send; full history only ever moves between a person's own devices via
a separate, one-time, local-network "transfer" flow used for phone
migration, not an ongoing background process. This protocol is meant to
actually do the ongoing reconciliation Signal's linked-device model
doesn't.

## Roles

There is exactly one role, `device` — the same role `multi-device/1.0`
defines; every enrolled device can both initiate and answer every message
type here. There is no designated "source of truth" device, though an
implementation may choose to *configure* one device with unbounded
retention specifically so it's more often the one able to answer requests
for old content (see Design By Contract) — that's a local policy choice
this protocol is indifferent to, not a role it defines.

## Connectivity

Pairwise, device-to-device, mediated exactly like any other DIDComm v2
message — never broadcast. A device that wants to reconcile with *every*
sibling sends the same request individually to each one it knows about
from its `multi-device/1.0` roster; a device backfilling or searching on
demand may likewise ask multiple siblings and use whichever answers (see
`backfill-request` and `search-request`).

## States

This protocol is stateless at the message-type level — every message is a
self-contained request or response, not part of a multi-step handshake
with its own lifecycle. The only "state" that matters is each device's own
local data (which collections/chunks it holds, and its own retention
policy), which this protocol reads and updates but never itself
represents on the wire beyond what's described in Message Reference.

## Basic Walkthrough

### Reconciliation after being offline

Alice's phone and laptop are both already enrolled (`multi-device/1.0`).
The laptop was asleep for a day; several new messages and one new contact
arrived on the phone in the meantime, and Bob edited one message the
laptop already held.

1. The laptop, on waking, sends the phone a `sync-summary-request` for
   every collection it tracks — one entry per conversation, plus the
   `contacts`, `groups` and other single-chunk collections. Every entry
   carries a `content_hash` now, the `messages:*` ones included:
   ```json
   {
     "id": "2f6b1e2a-1c3d-4e5f-8a9b-0c1d2e3f4a5b",
     "type": "https://wyvrn.app/history-sync/1.1/sync-summary-request",
     "body": {
       "collections": [
         { "collection_id": "contacts", "count": 12, "content_hash": "4e7a..." },
         { "collection_id": "mutes", "count": 2, "content_hash": "c01d..." },
         { "collection_id": "messages:did:peer:2...bob", "count": 340, "oldest_id": "msg-001", "newest_id": "msg-340", "content_hash": "7b19..." }
       ]
     }
   }
   ```
2. The phone compares each against its own local state and replies only
   with what differs:
   ```json
   {
     "id": "8a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
     "type": "https://wyvrn.app/history-sync/1.1/sync-summary-response",
     "thid": "2f6b1e2a-1c3d-4e5f-8a9b-0c1d2e3f4a5b",
     "body": {
       "collections": [
         { "collection_id": "contacts", "in_sync": false, "count": 13, "content_hash": "a9f0..." },
         { "collection_id": "mutes", "in_sync": true, "count": 2, "content_hash": "c01d..." },
         { "collection_id": "messages:did:peer:2...bob", "in_sync": false, "count": 344, "oldest_id": "msg-001", "newest_id": "msg-344", "content_hash": "e2c4..." }
       ]
     }
   }
   ```
3. For `contacts` (small enough to always be exactly one chunk — see
   Design By Contract), the laptop skips straight to a `chunk-members-request`.
   For the larger `messages:did:peer:2...bob` collection, it first asks for
   a manifest:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.1/chunk-manifest-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "chunk_size": 100, "before": null }
   }
   ```
4. The phone replies with its own chunk boundaries and a digest per chunk
   (a hash of that chunk's sorted `(id, message_hash)` pairs — see Message
   Reference for exactly what's hashed):
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.1/chunk-manifest-response",
     "body": {
       "collection_id": "messages:did:peer:2...bob",
       "chunks": [
         { "chunk_index": 0, "first_id": "msg-001", "last_id": "msg-100", "digest": "b3f2..." },
         { "chunk_index": 1, "first_id": "msg-101", "last_id": "msg-200", "digest": "51d8..." },
         { "chunk_index": 3, "first_id": "msg-301", "last_id": "msg-344", "digest": "9ac1..." }
       ]
     }
   }
   ```
   Chunks 0 and 2 match what the laptop already computes locally. Chunk 3,
   the partially-new one, doesn't — and neither does chunk 1, which both
   devices hold in full: Bob's edit of `msg-150` changed that message's
   hash on the phone.
5. The laptop asks for each mismatched chunk's actual membership:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.1/chunk-members-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "chunk_index": 3 }
   }
   ```
6. The phone replies with every `(id, hash)` pair in that chunk. The
   laptop diffs this against its own copy of the same range and finds four
   ids it doesn't have at all:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.1/chunk-members-response",
     "body": {
       "collection_id": "messages:did:peer:2...bob",
       "chunk_index": 3,
       "members": [
         { "id": "msg-341", "hash": "..." },
         { "id": "msg-342", "hash": "..." },
         { "id": "msg-343", "hash": "..." },
         { "id": "msg-344", "hash": "..." }
       ]
     }
   }
   ```
   The same exchange for chunk 1 finds one id, `msg-150`, that the laptop
   holds with a different hash.
7. The laptop requests exactly those five:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.1/item-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "ids": ["msg-150", "msg-341", "msg-342", "msg-343", "msg-344"] }
   }
   ```
8. The phone replies with the full content of just those five items, which
   the laptop merges into local storage. `msg-150` is a message the laptop
   already holds, so it is not stored over the top: the laptop applies the
   difference — the edited text, and the time of the edit — as if Bob's
   `message-edit` had arrived (see Design By Contract, "Applying a
   sibling's copy of a message"). The same `chunk-members-request`/diff/
   `item-request` sequence, applied to the `contacts` collection's one
   chunk, picks up the one new contact the same way.

### On-demand backfill while scrolling

Later, Alice scrolls back past what her phone's rolling window (30 days)
still holds. The phone has nothing older locally, so it asks the laptop
(unbounded retention) directly, independent of any reconciliation pass:

```json
{
  "type": "https://wyvrn.app/history-sync/1.1/backfill-request",
  "body": { "collection_id": "messages:did:peer:2...bob", "before": "msg-001", "limit": 50 }
}
```

The laptop replies with up to 50 messages older than `msg-001` it still
holds, and whether it has more beyond that:

```json
{
  "type": "https://wyvrn.app/history-sync/1.1/backfill-response",
  "body": { "collection_id": "messages:did:peer:2...bob", "items": [ /* ... */ ], "has_more": true }
}
```

### Searching a conversation

Alice types "bistro" into the search box of her conversation with Bob, on
her phone. The phone searches its own 30 days first and shows what it
finds. At the same time it asks the laptop, which keeps everything:

```json
{
  "id": "6c2d9f10-5b7e-4a3c-9d1e-2f3a4b5c6d7e",
  "type": "https://wyvrn.app/history-sync/1.1/search-request",
  "from": "did:peer:2...phone",
  "to": ["did:peer:2...laptop"],
  "body": { "collection_id": "messages:did:peer:2...bob", "query": "bistro", "limit": 20 }
}
```

The laptop answers with the messages of that conversation whose text
contains "bistro", newest first, in the same full form a
`backfill-response` carries:

```json
{
  "id": "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f7a",
  "type": "https://wyvrn.app/history-sync/1.1/search-response",
  "from": "did:peer:2...laptop",
  "to": ["did:peer:2...phone"],
  "thid": "6c2d9f10-5b7e-4a3c-9d1e-2f3a4b5c6d7e",
  "body": {
    "collection_id": "messages:did:peer:2...bob",
    "matches": [
      {
        "id": "m1",
        "conversation": "did:peer:2...bob",
        "sender": "did:peer:2...alice",
        "created_time": 1791400000,
        "content": "Dinner at 7:30? This place:",
        "media": [ { "attachment": "photo", "width": 1280, "height": 960 } ],
        "attachments": [ { "id": "photo", "media_type": "image/jpeg", "filename": "bistro.jpg", "byte_count": 183220, "data": { "base64": "/9j/4AAQSkZJRg..." } } ],
        "edited": { "content": 1791400120 },
        "reactions": { "did:peer:2...bob": ["👍"] }
      }
    ],
    "has_more": false
  }
}
```

The phone adds the laptop's matches to the ones it found itself (the same
message found by both is shown once), and stores each match it didn't hold
exactly as it would a backfilled message, so that opening one from the
results list doesn't cost a second request.

## Design By Contract

- **Reconciliation never overrides a device's own retention policy.** A
  bounded device correctly reports `in_sync` for a collection whose only
  difference from a sibling is content outside its intended window — that
  is the policy working, not a fault to correct. Only genuine divergence
  *within* the range a device already intends to keep is something this
  protocol tries to fix.
- **Chunk alignment is the requester's responsibility.** `chunk_size` and
  the starting `before` cursor in `chunk-manifest-request` are dictated by
  the requester specifically so both sides compute the same boundaries;
  the responder does not get to choose its own chunking independently, or
  the two manifests would never line up for comparison.
- **The item hash covers what every device is meant to agree on, and
  nothing that is one device's own.** For every collection it covers the
  item's `id`, its collection, its sender where it has one, and its
  content; it never covers a locally-mutable field like a read/seen
  timestamp. Including one would make two devices with identical content
  but different local read-state appear permanently divergent, forcing an
  unnecessary re-diff every reconciliation pass. What "content" is for a
  message changed in this version — see the next point.
- **A message's hash covers the message as received plus every change a
  peer made to it.** In 1.0 a message's content never changed once held.
  Under [`chat-message/1.0`](../../chat-message/1.0/readme.md) its author
  can edit its text and delete it, and the companion protocols attach
  state to it that other parties set. All of that is something every
  device of the person is meant to agree on, so all of it is hashed. For
  a `messages:*` item the hash covers:
  - the message as received: `id`, `conversation`, `sender`,
    `created_time`, `expires_time` if any, its `content`, `mentions` and `embeds` *as currently
    edited*, its `media` and `attachments` as received (the descriptors and
    either the inline bytes or the links and hashes; an implementation MAY
    stand in a digest of inline bytes for the bytes), `reply_to`,
    `forwarded`, and its `thread` (the `thid` it was sent in, if any);
  - `edited`: for each edited field, the `created_time` of the edit applied
    to it (the text itself is already covered; this is what tells "edited
    at 12:02" from "edited at 12:05");
  - `deleted`, and `deleted_time`;
  - `reactions`: for each reactor DID, the set of emoji that reactor
    currently has on the message
    ([`message-reactions/1.0`](../../message-reactions/1.0/readme.md)),
    sorted, with no times;
  - `pinned`: whether the message is pinned in its conversation, by whom
    and when ([`chat-pins/1.0`](../../chat-pins/1.0/readme.md));
  - the `thread` a message is the root of, once a reply chain has been made
    into one ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)).

  It does not cover: the person's own read and seen timestamps, delivery
  and send-failure flags on an outgoing message, whether the person follows
  the thread (the `threadFollows` collection), whether they bookmarked the
  message (`bookmarks`), or anything derived locally (a rendered preview, a
  decrypted copy of bytes fetched by reference). Those are one device's
  own, or live in a collection of their own.

  The exact serialization hashed is still an implementation's to choose,
  as in 1.0: a hash is only ever compared between a person's own devices,
  which run the same software. What this section fixes is which parts go
  in, so that an implementation neither leaves out a change that must
  propagate nor puts in local state that must not.
- **A `messages:*` summary carries a `content_hash`, like every other
  collection.** 1.0 compared `count` and the two cursors for `messages:*`,
  which proved agreement only because nothing held ever changed. Now an
  edit, a delete, a reaction or a pin changes a message without changing
  the count or either cursor, so `sync-summary-request` and `-response`
  carry, for a `messages:*` collection too, the same order-independent hash
  over every held item's hash that the single-chunk collections already
  carried, and `in_sync` requires it to match as well. The alternative — a
  "latest change" cursor, the `created_time` of the newest change applied
  — was rejected: two devices can have applied different changes with the
  same newest time, and a device that missed a reaction but received a
  later one would carry the newer cursor and look up to date. A hash is
  proof; a cursor is a hint. The cost is the same work the responder
  already does to build a manifest, and an implementation can keep each
  item's hash stored beside the item and recompute only what changed.
  The manifest and chunk exchange that follows a mismatch is exactly 1.0's;
  a changed message simply makes its chunk's digest differ, and the
  member diff then names it as an id held with a different hash.
- **A deleted message is a tombstone, and a tombstone syncs.** A device
  that received a `message-delete` keeps the message's `id`,
  `conversation`, `sender` and `created_time`, sets `deleted: true` and
  `deleted_time` (the delete's `created_time`), and drops its `content`,
  `mentions`, `embeds`, `media`, `attachments`, `reply_to` and `forwarded`;
  attached state that still shows under the placeholder (`reactions`,
  `pinned`, `thread`) is kept. That is the item an `item-batch`,
  `backfill-response` or `search-response` carries for it. A device that
  holds a tombstone never takes a sibling's undeleted copy of the same
  message, whatever its hash: the sibling missed the delete, and this
  exchange is how it learns of it (the reverse direction, this device's
  unprompted `item-batch`, carries the tombstone). A `message-delete` that
  arrived before its message is a tombstone too, with the delete's own
  `created_time` standing in for the message's so that it has a place in
  the order; a tombstone that knows the message's own `created_time` wins
  over one that doesn't, and the two converge on the first exchange.
- **Applying a sibling's copy of a message.** An `item-batch` (or a
  `backfill-response`/`search-response`) can now carry an item this device
  already holds, with a different hash. The device does not store the copy
  over its own. It applies the difference as if the wire messages that
  made it had arrived: an edit state newer than its own as that author's
  `message-edit` (under `chat-message/1.0`'s rules — per field, the latest
  `created_time` wins, an older one is ignored), `deleted` as a
  `message-delete`, a reactor's set as that reactor's reactions, `pinned`
  and `thread` as a pin and a thread. That keeps one code path per
  protocol for "what does this change do to a message", and it is what
  makes the Security rule below enforceable: a change a sibling hands over
  must be one the peer in question could have sent. A copy that differs in
  a part that cannot change — `sender`, `created_time`, `media`,
  `reply_to`, `forwarded` — is a different message that happens to share
  an id, and is ignored.
- **Diffing is bidirectional in one pass.** After comparing a
  `chunk-members-response`, a device may hold ids the responder's manifest
  didn't include at all, or hold a newer state of an id both have. Rather
  than waiting for the other device to separately notice and ask, the
  requester should proactively include those in its own unprompted
  follow-up (an `item-request` in the other direction is unnecessary;
  sending the content directly, unsolicited, is sufficient) — the same
  exchange should leave both sides in sync, not just the one that
  initiated it. For an id both hold with different hashes, both sides send
  their copy and both apply the other's under the rule above; where the
  two copies hold different changes (an edit on one, a reaction on the
  other), each ends up with both.
- **A `backfill-response` with no data anywhere means the content is
  genuinely gone**, not a bug to retry past. If every enrolled device's
  retention policy has already evicted a given range, there is nothing
  left for this protocol — or any protocol — to recover; that is an
  accepted consequence of letting retention be a real per-device choice
  (see Motivation), not a gap this version tries to paper over. A person
  who wants full recall available should deliberately keep one device
  (commonly, a computer with more storage than a phone) at unbounded
  retention specifically so a `backfill-request` almost always has
  somewhere left to succeed — but this protocol does not require or
  enforce that choice.
- **A device should prefer an unbounded-retention sibling when choosing
  who to send a `backfill-request` or `search-request` to**, using
  [`multi-device/1.0`](../../multi-device/1.0/readme.md)'s
  `device-announce.retention` field to skip a known-`"bounded"` sibling
  entirely rather than asking it and getting an empty response back. This
  is a request-time optimization only — nothing stops a device from asking
  a bounded sibling anyway (e.g. it's the only one currently reachable),
  it just shouldn't be the first choice when a better-odds sibling is
  known.
- **An item received via `backfill-response` or `search-response` is
  persisted into local storage exactly like any other item this protocol
  delivers**, subject to the requesting device's own retention policy on
  its next ordinary cleanup pass — not held in some separate, ephemeral
  "viewing cache" that forgets it once the person scrolls away or clears
  the search box. This keeps exactly one code path for "do I already have
  this item locally," and means scrolling back over the same range twice
  in one session, or opening a search result, only ever costs one request,
  not one per visit.
- **Search is one conversation, this device first, siblings for the
  rest.** A search runs over a single `messages:<conversation_id>`
  collection (a thread's messages are in their conversation's collection,
  so they are searched with it). The device searches what it holds and
  shows that at once; in the background it sends the same
  `search-request` to the siblings it chooses (unbounded first, as above),
  and merges whatever answers by message id. It cannot know which siblings
  are online, so it uses the answers that come within a time it sets and
  still stores a later one when it arrives — a late result is a backfill
  like any other. A responder answers only from what it itself holds and
  never passes a search on to a third device: the requester is already
  asking every sibling it wants to.
- **A text match is minimal and the same everywhere.** The `query` is
  split on whitespace into terms; a message matches when every term
  occurs, as a substring, in its current `content`, compared
  case-insensitively after Unicode case folding. A deleted message never
  matches. A message with no text does not match on its label or media
  (an implementation MAY also match attachment filenames, and MAY ignore
  diacritics; it MUST NOT match less than the rule above). Matches come
  newest-first, paged with `before` exactly as `backfill-request` pages.
  Anything cleverer — stemming, ranking, a sender or date filter — is a
  later version's; this one is a substring search that happens to run on
  another device.
- **`collection_id` is deliberately generic**, not hardcoded to messages.
  `messages:<conversation_id>` is the large, usually-chunked case; small
  local state like `contacts`, `groups`, the `multi-device/1.0` device
  roster itself, and this version's `threadFollows`, `bookmarks`, `mutes`,
  `blocks`, `stickerPacks` and `settings` are expected to fit in a single
  chunk and can skip straight from `sync-summary-response` to
  `chunk-members-request` without ever needing a real manifest exchange,
  exactly as shown for `contacts` in the walkthrough above.
- **The new single-chunk collections are sets edited in place, with one
  conflict rule: the latest `updated_at` wins, per item.** Each item of
  `threadFollows`, `bookmarks`, `mutes`, `blocks`, `stickerPacks` and
  `settings` carries `updated_at`, epoch seconds, set by the device that
  last changed it, which MUST make it strictly greater than the item's
  previous value even if its clock has not moved. A device applying a
  sibling's copy keeps whichever of the two copies has the greater
  `updated_at`; on a tie, the copy with the greater item hash, so that both
  sides make the same choice. Nothing is ever removed from one of these
  collections: an unfollow, an unmute, an unblock, an uninstall or a
  bookmark taken away is the item in its *off state* (see Message
  Reference), which syncs like any other change. An implementation MAY
  drop an off-state item once it is older than its own history retention
  window, accepting that a sibling offline for longer may bring the item
  back in its last known state.
- **Where the blocked-messages choice lives.** Whether a blocked contact's
  messages are dropped on arrival or kept hidden is one choice for the
  person, not one per block, so it is a `settings` item
  (`blocked_messages`) rather than a field repeated on every `blocks`
  item — a field per block would have to be rewritten on every block when
  the choice changed, and a block made on a device that hadn't yet heard
  of the change would carry the old value. `settings` holds one item per
  setting, not one item for all of them, so that two settings changed on
  two devices don't overwrite each other.
- **Talking to a 1.0 device.** A device that implements 1.1 MUST accept
  every message of 1.0 (the same types under the `1.0` PIURI) and answer it
  as 1.0 did. It MAY add 1.1's fields to such an answer: a 1.0 receiver
  ignores fields it doesn't know. A requester that has not yet learned that
  a sibling supports 1.1 — through
  [`discover-features/2.0`](https://didcomm.org/discover-features/2.0),
  or by having received a 1.1-typed message from it — sends its requests
  as 1.0 types carrying 1.1's fields, and treats the answer by what it
  carries: a `sync-summary-response` entry for a `messages:*` collection
  with no `content_hash` is a 1.0 answer, and the requester then compares
  that collection as 1.0 did (count and cursors), knowing that a changed
  message cannot be found through that sibling until it is updated. A 1.0
  sibling omits the collections it doesn't know from its response, as 1.0
  already allows, and nothing is sent for them. A `search-request` has no
  1.0 form; it is sent only to a sibling known to support 1.1, and a
  requester with no such sibling searches its own history alone.
- **No ordering or delivery guarantee beyond ordinary pairwise DIDComm.**
  Two reconciliation passes running concurrently between the same pair of
  devices (e.g. both waking up near-simultaneously and reconciling with
  each other) are not coordinated by this protocol; an implementation
  should tolerate a redundant or interleaved exchange rather than assume
  only one runs at a time.

## Security

- This protocol only ever runs between a person's own enrolled devices
  (per `multi-device/1.0`'s roster), so its message trust context is the
  same as that protocol's: every message here is sent device-to-device
  using each device's own independent Device DID (never the shared
  Identity DID), and being enrolled at all — holding a copy of the
  Identity DID's keys — is what makes a peer trusted here. It defines no
  new trust boundary of its own.
- Content confidentiality is exactly what pairwise DIDComm v2 encryption
  between the two specific devices already provides; there is no
  additional encryption layer here, and no content is ever exposed to the
  mediator beyond what ordinary message delivery already exposes (the
  mediator relays ciphertext it cannot read either way). That includes a
  search: the mediator sees neither the query nor the matches.
- That holds only if it is enforced, and a Device DID is not a secret
  (see `multi-device/1.0`'s Security section): it is in every enrollment
  invitation, and every device ever enrolled knows its siblings'. A
  receiver MUST act on a message of this protocol only if it is
  sender-authenticated by a Device DID that is in the receiver's current
  roster and has not been revoked, and MUST silently ignore any other —
  including one that is anonymously encrypted, whatever its plaintext
  `from` claims, and one that is signed rather than sender-authenticated.
  This applies to every message type here, requests and unprompted
  `item-batch`es alike: the requests hand over contacts, complete message
  history and the matches of a search, and the batches are stored as
  received. A `search-request` in particular hands over the text of every
  matching message, and the `blocks` and `mutes` collections let a sibling
  silence a contact or a conversation on this device.
- A revoked device's own Device DID keeps working, and nobody tells it
  that it was revoked, so it will go on issuing `history-sync` requests as
  before. The rule above is what stops them being answered; removing its
  mediator registration is not something its former siblings can do, and
  must not be relied on.
- **An `item-batch` can change a message this device holds, so a sibling's
  copy is applied only when its hash differs and the change is one a peer
  could have made.** The copy is applied through the rules the wire
  message would have met (see Design By Contract, "Applying a sibling's
  copy of a message"), and `chat-message/1.0`'s rules hold here as there:
  a device MUST NOT take an edit or a delete whose recorded editor is not
  the message's author — a copy whose `content` differs under a different
  `sender`, or whose edit state is for a message the author never sent, is
  not an edit of this message — and MUST NOT take a copy that changes a
  part of a message that cannot change. A held tombstone is never
  undeleted by a sibling's copy. A reactor's set is taken for that reactor
  only and only where the reactor is a party to the conversation; a pin
  only from a party allowed to pin under `chat-pins/1.0`. Siblings are
  trusted equally, as everywhere in this protocol, but a device that
  still applies the peer protocols' own rules to what a sibling hands it
  cannot be made, by a sibling's bug or a bad copy, to show text its
  author never sent.
- The roster itself (`devices`) is reconciled like any other collection,
  with two limits that keep reconciliation from overriding
  `multi-device/1.0`: a device that has been revoked is never re-added by
  a sibling's copy of its roster entry, and fields that are one device's
  own bookkeeping about another (an outstanding promotion request) are
  neither sent nor overwritten.
- Hashes exchanged here (`chunk-manifest-response`/`chunk-members-response`)
  reveal the *existence and count* of messages in a range to any device
  that can authenticate as a sibling, even before that device fetches
  their content — a consequence of trusting every enrolled device
  equally, consistent with `multi-device/1.0`'s own security model. A
  `search-request` likewise reveals to the sibling what the person is
  looking for; between a person's own devices that is as intended.

## Message Reference

Every message type here is sent under the `1.1` PIURI; a 1.1 device also
accepts each of 1.0's under the `1.0` PIURI (see Design By Contract,
"Talking to a 1.0 device").

### Collections

A `collection_id` names one of:

| `collection_id` | Chunked | Item id | Item |
|---|---|---|---|
| `messages:<conversation_id>` | yes | the message `id` | A message of the conversation (see "Message items" below). `<conversation_id>` is a contact's DID for a pair, or `group:<group id>` for a group. |
| `contacts` | no | the contact's DID | A contact record. |
| `groups` | no | the group id | A group record. |
| `devices` | no | the Device DID | What a device says about itself in its `multi-device/1.0` `device-announce`. |
| `ownProfile` | no | `default` | The person's own profile. |
| `threadFollows` | no | the thread id | `{ id, conversation, followed, updated_at }` — whether the person follows the thread ([`chat-threads/1.0`](../../chat-threads/1.0/readme.md)) in `conversation`. Off state: `followed: false`. |
| `bookmarks` | no | `<conversation_id>#<message id>` | `{ id, conversation, message: { id, author }, created_at, removed, updated_at }` — a private pin: a message reference (`chat-message/1.0`'s shape) the person saved for themselves, which no one else is told of. Off state: `removed: true`. |
| `mutes` | no | the conversation id | `{ id, until, updated_at }` — the conversation is muted until `until`: epoch seconds, or `"forever"`. Off state: `until: null`. |
| `blocks` | no | the contact's DID | `{ id, blocked, since, updated_at }` — the contact is blocked, `since` epoch seconds. What happens to a blocked contact's messages is the `blocked_messages` setting. Off state: `blocked: false`. |
| `stickerPacks` | no | the pack id | `{ id, service, kind, own, installed, updated_at }` — a sticker or custom-emoji pack the person installed (`installed: true`) or made (`own: true`), `service` being the URL the pack document is fetched from (`chat-message/1.0`'s `media[].sticker.service`; see `discussions/chat-services.md`) and `kind` being `"stickers"` or `"emoji"`. Off state: `installed: false`. |
| `settings` | no | the setting's name | `{ id, value, updated_at }`. One is defined: `blocked_messages`, whose `value` is `"drop"` (a blocked contact's messages are discarded on arrival; the default) or `"keep"` (kept, hidden, and shown if the contact is unblocked). |

`updated_at`, `created_at`, `since` and `until` are UTC epoch seconds. The
item shapes of `contacts`, `groups`, `devices` and `ownProfile` are an
implementation's own, as in 1.0; the six new collections' shapes are given
here because their conflict rule depends on `updated_at` and each one's
off state (see Design By Contract).

### Message items

A `messages:*` item, as `item-batch`, `backfill-response` and
`search-response` carry it, has these parts (named as this specification
names them; an implementation's record may call them what it likes, but
every device of a person must agree on what is sent):

| Part | Description |
|---|---|
| `id`, `conversation`, `sender`, `created_time` | The message's id, its conversation, the DID that sent it (authenticated), and its `created_time`. Never change. |
| `content`, `mentions`, `embeds` | As currently edited. Absent on a tombstone. |
| `expires_time` | The message's `expires_time` header, if it had one ([`disappearing-messages/1.0`](../../disappearing-messages/1.0/readme.md)). Never changes. A device never sends, and discards on receipt, an item whose `expires_time` has passed: every device of the person removes the message at the same moment. |
| `media`, `attachments`, `reply_to`, `forwarded`, `thread` | As received (`chat-message/1.0`; `thread` is the `thid` the message was sent in, or the thread the message is the root of). Never change, except that `thread` is set when a reply chain is made into a thread. Absent on a tombstone, except `thread`. |
| `edited` | Object: for each of `content`, `mentions`, `embeds` that an edit changed, the `created_time` of that edit. |
| `deleted`, `deleted_time` | `true` and the delete's `created_time` on a tombstone; absent otherwise. |
| `reactions` | Object: reactor DID → array of emoji, sorted. |
| `pinned` | `{ by, created_time }` while pinned; absent otherwise. |

The item hash covers all of the above and nothing else (see Design By
Contract). What a device holds beyond them — its read and seen times, an
outgoing message's delivery state — is not sent.

A tombstone as carried on the wire:

```json
{
  "id": "m1",
  "conversation": "did:peer:2...bob",
  "sender": "did:peer:2...alice",
  "created_time": 1791400000,
  "deleted": true,
  "deleted_time": 1791400300,
  "reactions": { "did:peer:2...bob": ["👍"] }
}
```

### `sync-summary-request`

Sent to a sibling device to check whether one or more collections are in
sync, before doing any more expensive comparison.

| Field | Type | Description |
|---|---|---|
| `collections` | array of object | The sender's own current state per collection it wants checked. |
| `collections[].collection_id` | string | One of the collections above. |
| `collections[].count` | integer | Total items the sender currently holds in this collection, tombstones included. |
| `collections[].oldest_id` / `collections[].newest_id` | string | Present for a chunkable collection (`messages:*`); the sender's own oldest/newest held item id, reflecting its retention window. |
| `collections[].content_hash` | string | Present for every collection: a hash over every held item's own content hash (order-independent — the same combining hash a chunk's own `digest` uses, see `chunk-manifest-response` below), covering the collection's *content*, not just its size. Necessary because every collection is now edited in place: a contact's own fields, an own-profile display name, a device's trust flag, and — new in 1.1 — a message's text, its deletion, its reactions and its pin can all change without the collection's item count or cursors changing at all, so those alone can't prove two devices agree. In 1.0 this field was present for the single-chunk collections only. |

### `sync-summary-response`

| Field | Type | Description |
|---|---|---|
| `collections` | array of object | One entry per collection from the request that the responder has an opinion on (an out-of-window collection, or one this responder doesn't know, may be omitted entirely). |
| `collections[].collection_id` | string | Echoes the request. |
| `collections[].in_sync` | boolean | `true` if the responder's own `count` and `content_hash` match the request's, and, for a chunkable collection, its own cursors match too. |
| `collections[].count` / `oldest_id` / `newest_id` / `content_hash` | — | The responder's own current values, same shape as the request. |

### `chunk-manifest-request`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Which collection. |
| `chunk_size` | integer | Items per chunk, dictated by the requester (see Design By Contract). |
| `before` | string \| null | Walk chunks starting immediately before this id (for paging a manifest too large for one message); `null` means start from the newest item. |

### `chunk-manifest-response`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Echoes the request. |
| `chunks` | array of object | The responder's own chunk boundaries and digests, using the requested `chunk_size`. |
| `chunks[].chunk_index` | integer | Position from the most recent chunk (0-based), stable for the request's `before` paging. |
| `chunks[].first_id` / `chunks[].last_id` | string | The chunk's boundary item ids. |
| `chunks[].digest` | string | A hash of the chunk's sorted `(id, item_hash)` pairs (order-independent — see Design By Contract on what `item_hash` covers). |

### `chunk-members-request`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Which collection. |
| `chunk_index` | integer | Which chunk (from a prior `chunk-manifest-response`), or omitted entirely for a single-chunk collection like `contacts`. |

### `chunk-members-response`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Echoes the request. |
| `chunk_index` | integer | Echoes the request, if present. |
| `members` | array of object | Every item in the chunk, as `{ id, hash }` — never full content. |

### `item-request`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Which collection. |
| `ids` | array of string | The specific item ids being requested, after a member-list diff identified them as missing or differing. |

### `item-batch`

Sent either in reply to `item-request`, or unprompted, to proactively hand
over items the sender knows the recipient is missing or holds in an older
state (see Design By Contract on bidirectional diffing).

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Which collection. |
| `items` | array of object | Full content for each item, shaped per `collection_id` (a message item, a tombstone included, for `messages:*`; the shapes above for the six new collections; an implementation's own for `contacts`, `groups`, `devices` and `ownProfile`). An item the receiver already holds is applied as a change, not stored over the top (see Design By Contract and Security). |

### `backfill-request`

Independent of the reconciliation flow above — reactive, triggered by a
person's own scrolling, not a periodic pass.

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Almost always `messages:<conversation_id>` in practice. |
| `before` | string | Fetch items older than this id. |
| `limit` | integer | Maximum items to return. |

### `backfill-response`

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Echoes the request. |
| `items` | array of object | Up to `limit` items older than `before` that the responder still holds, newest-first, tombstones included. |
| `has_more` | boolean | `false` means the responder has nothing older than what it just returned — a requester still wanting more should ask a different sibling. |

### `search-request`

Message Type URI: `https://wyvrn.app/history-sync/1.1/search-request`

Independent of the reconciliation flow, like `backfill-request`: sent when
a person searches a conversation, to siblings that may hold more of it
than this device does (see Design By Contract, "Search is one
conversation").

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | REQUIRED. `messages:<conversation_id>` — the one conversation searched. |
| `query` | string | REQUIRED. Plain text, 1 to 200 characters; split on whitespace into terms, every one of which must occur in a matching message's current text, case-insensitively. |
| `limit` | integer | REQUIRED. Maximum matches to return. A responder MAY return fewer, and SHOULD cap it at a ceiling of its own (100 is reasonable). |
| `before` | string | OPTIONAL. Return only matches older than this message id, for paging; absent means start from the newest. |

Schema: [`schemas/search-request.json`](schemas/search-request.json).

### `search-response`

Message Type URI: `https://wyvrn.app/history-sync/1.1/search-response`

Headers: `thid` REQUIRED, the `search-request`'s `id`.

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | REQUIRED. Echoes the request. |
| `matches` | array of object | REQUIRED. The matching message items the responder holds, newest-first, in the full form `backfill-response` carries (deleted messages never match, so no tombstones); empty if it holds no match, or doesn't hold the collection at all. |
| `has_more` | boolean | REQUIRED. `true` if the responder has older matches beyond the last one returned; the requester pages with `before` set to that one's id. |

Schema: [`schemas/search-response.json`](schemas/search-response.json).

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Implements 1.0 (`src/handlers/historySync/historySyncHandler.ts` for the message types, `src/services/historySync/collections.ts` for the collections and each one's item hash, `hashing.ts` and `reconcile.ts` for the digests and chunking, `syncActivity.ts` for progress). 1.1 is not yet implemented: the message hash there covers `id`, conversation, sender, content and time only (plus an undelivered marker for an outgoing send that never completed, which 1.1 treats as local state), `content_hash` is computed for the single-chunk collections only, and none of the six new collections or `search-request` exist yet.

## Endnotes

### Changes from 1.0

Everything here is additive, and a 1.1 device keeps answering a 1.0 one
as 1.0 did (see Design By Contract, "Talking to a 1.0 device").

- **`messages:*` is no longer append-only.** What a message's item hash
  covers is spelled out: the message as received plus every change a peer
  made to it (edit state and the time of each field's edit, deletion, each
  reactor's reactions, the pin, the thread), and never the device's own
  read, seen or delivery state. `sync-summary-request` and `-response`
  carry `content_hash` for a `messages:*` collection too, and `in_sync`
  requires it to match. The manifest, member and item exchange is
  unchanged.
- **Tombstones.** A deleted message is carried as an item with its `id`,
  `conversation`, `sender`, `created_time`, `deleted: true` and
  `deleted_time`, no content, and is never undeleted by a sibling's copy.
- **A held item can be changed by an `item-batch`.** It is applied as the
  peer's own wire messages would have been, under their rules, never
  stored over the top; and `backfill-response`/`search-response` items go
  through the same path.
- **Six new single-chunk collections**: `threadFollows`, `bookmarks`,
  `mutes`, `blocks`, `stickerPacks`, `settings`, each a set edited in
  place, with item shapes, an off state instead of removal, and one
  conflict rule — latest `updated_at` wins, per item.
- **Search**: `search-request`/`search-response`, a substring search of
  one conversation on a sibling, with results persisted like a backfill.
- **Bidirectional diffing** now also covers an id both devices hold with
  different hashes: both send their copy, and each applies the other's.
- The `backfill-response` example in 1.0's walkthrough showed its items
  under `messages`; the field has always been `items`, as its Message
  Reference and the implementation say. Corrected here.

### Future Considerations

- A real Merkle-style recursive split for very large mismatched chunks
  (today: one flat `chunk-members-response` per mismatched chunk), if
  `chunk_size` ever needs to be large enough that a single member-list
  response becomes unwieldy on its own.
- A dedicated collection-level "don't bother asking me for old content, I
  never retain any" signal, finer-grained than `multi-device/1.0`'s
  blanket per-device `retention` field, if a device ever wants to keep
  some collections unbounded and others bounded rather than one retention
  policy for everything it holds.
- A search across every conversation at once, and a sender or date filter
  on it. Searching one conversation on one sibling at a time is what the
  app's search box does today; a global search would want a different
  request, not a `collection_id` of `messages:*`.
- Syncing a person's own read state (`read_at`) between devices as a
  collection of its own, with a "furthest read" rule, so that a
  conversation read on the phone is read on the laptop. It is deliberately
  not part of the message hash; it would be its own small collection.
