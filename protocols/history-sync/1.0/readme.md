---
title: History Sync
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/history-sync/1.0
status: Proposed
summary: Reconciles locally-stored state (message history, contacts, groups) between a person's own devices with no shared server-side copy, using a cheap count/cursor check, a chunked-hash manifest to localize divergence, and per-message diffing so only what's actually missing or different ever gets transferred — with each device free to keep only a bounded, rolling window of history rather than a full copy.
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
cheap count/cursor comparison first, then chunk-level hashes to localize
where two devices actually differ, then a per-item hash/id diff *within*
only the mismatched chunk, so a transfer only ever contains the specific
items that are missing or different — never a whole re-send of anything
already held identically by both sides. A separate, unrelated request type
covers the reactive case (a person scrolling back further than a device's
local window currently holds), which doesn't need any of the chunking
machinery above.

This protocol assumes [`multi-device/1.0`](../../multi-device/1.0/readme.md)
for how a device learns which sibling devices exist and what their
messaging DIDs are; every message here is addressed to a specific sibling
device, never broadcast.

## Motivation

A DIDComm mediator is a transient relay, not an archive — content is
removed from its queue once picked up and acknowledged, by design (see
`messagepickup/3.0`). That means a device enrolled after some history
already exists, or one that was offline for a while, has no way to recover
anything from the mediator itself; whatever it's missing can only come
from another device that still has it.

The obvious approach — every device eventually holds a full copy of
everything — doesn't fit real devices. A phone has meaningfully less
storage than a laptop and a person may deliberately not want years of
history sitting on a device they carry around and could lose. So this
protocol treats "how much history a device keeps" as a purely local,
per-device policy (unbounded, or a rolling window by count or age) that
reconciliation must respect rather than override: two devices with
genuinely different intended retention are not "out of sync" just because
one has deliberately forgotten what the other still holds.

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
from its `multi-device/1.0` roster; a device backfilling on demand may
likewise ask multiple siblings and use whichever answers first (see
`backfill-request`).

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
arrived on the phone in the meantime.

1. The laptop, on waking, sends the phone a `sync-summary-request` for
   every collection it tracks — one entry per conversation, plus the
   `contacts` and `groups` collections:
   ```json
   {
     "id": "2f6b1e2a-1c3d-4e5f-8a9b-0c1d2e3f4a5b",
     "type": "https://wyvrn.app/history-sync/1.0/sync-summary-request",
     "body": {
       "collections": [
         { "collection_id": "contacts", "count": 12 },
         { "collection_id": "messages:did:peer:2...bob", "count": 340, "oldest_id": "msg-001", "newest_id": "msg-340" }
       ]
     }
   }
   ```
2. The phone compares each against its own local state and replies only
   with what differs:
   ```json
   {
     "id": "8a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
     "type": "https://wyvrn.app/history-sync/1.0/sync-summary-response",
     "thid": "2f6b1e2a-1c3d-4e5f-8a9b-0c1d2e3f4a5b",
     "body": {
       "collections": [
         { "collection_id": "contacts", "in_sync": false, "count": 13 },
         { "collection_id": "messages:did:peer:2...bob", "in_sync": false, "count": 344, "oldest_id": "msg-001", "newest_id": "msg-344" }
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
     "type": "https://wyvrn.app/history-sync/1.0/chunk-manifest-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "chunk_size": 100, "before": null }
   }
   ```
4. The phone replies with its own chunk boundaries and a digest per chunk
   (a hash of that chunk's sorted `(id, message_hash)` pairs — see Message
   Reference for exactly what's hashed):
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.0/chunk-manifest-response",
     "body": {
       "collection_id": "messages:did:peer:2...bob",
       "chunks": [
         { "chunk_index": 0, "first_id": "msg-001", "last_id": "msg-100", "digest": "b3f2..." },
         { "chunk_index": 3, "first_id": "msg-301", "last_id": "msg-344", "digest": "9ac1..." }
       ]
     }
   }
   ```
   Chunks 0-2 match what the laptop already computes locally; only the
   last, partially-new chunk (3) doesn't.
5. The laptop asks for that one chunk's actual membership:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.0/chunk-members-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "chunk_index": 3 }
   }
   ```
6. The phone replies with every `(id, hash)` pair in that chunk. The
   laptop diffs this against its own copy of the same range and finds four
   ids it doesn't have at all:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.0/chunk-members-response",
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
7. The laptop requests exactly those four:
   ```json
   {
     "type": "https://wyvrn.app/history-sync/1.0/item-request",
     "body": { "collection_id": "messages:did:peer:2...bob", "ids": ["msg-341", "msg-342", "msg-343", "msg-344"] }
   }
   ```
8. The phone replies with the full content of just those four items, which
   the laptop merges into local storage. The same `chunk-members-request`/
   diff/`item-request` sequence, applied to the `contacts` collection's one
   chunk, picks up the one new contact the same way.

### On-demand backfill while scrolling

Later, Alice scrolls back past what her phone's rolling window (30 days)
still holds. The phone has nothing older locally, so it asks the laptop
(unbounded retention) directly, independent of any reconciliation pass:

```json
{
  "type": "https://wyvrn.app/history-sync/1.0/backfill-request",
  "body": { "collection_id": "messages:did:peer:2...bob", "before": "msg-001", "limit": 50 }
}
```

The laptop replies with up to 50 messages older than `msg-001` it still
holds, and whether it has more beyond that:

```json
{
  "type": "https://wyvrn.app/history-sync/1.0/backfill-response",
  "body": { "collection_id": "messages:did:peer:2...bob", "messages": [ /* ... */ ], "has_more": true }
}
```

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
- **The item hash used for `chunk-members-response` covers only
  immutable fields** — `id`, `collection_id`, `sender` (where applicable),
  and content, never a locally-mutable field like a read/seen timestamp.
  Including a mutable field would make two devices with identical content
  but different local read-state appear permanently divergent, forcing an
  unnecessary re-diff every reconciliation pass.
- **Diffing is bidirectional in one pass.** After comparing a
  `chunk-members-response`, a device may hold ids the responder's manifest
  didn't include at all. Rather than waiting for the other device to
  separately notice and ask, the requester should proactively include
  those in its own unprompted follow-up (an `item-request` in the other
  direction is unnecessary; sending the content directly, unsolicited, is
  sufficient) — the same exchange should leave both sides in sync, not
  just the one that initiated it.
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
- **`collection_id` is deliberately generic**, not hardcoded to messages.
  `messages:<conversation_id>` is the large, usually-chunked case; small
  local state like `contacts`, `groups`, and even the `multi-device/1.0`
  device roster itself are expected to fit in a single chunk and can skip
  straight from `sync-summary-response` to `chunk-members-request` without
  ever needing a real manifest exchange, exactly as shown for `contacts`
  in the walkthrough above.
- **No ordering or delivery guarantee beyond ordinary pairwise DIDComm.**
  Two reconciliation passes running concurrently between the same pair of
  devices (e.g. both waking up near-simultaneously and reconciling with
  each other) are not coordinated by this protocol; an implementation
  should tolerate a redundant or interleaved exchange rather than assume
  only one runs at a time.

## Security

- This protocol only ever runs between a person's own enrolled devices
  (per `multi-device/1.0`'s roster), so its message trust context is the
  same as that protocol's: possession of the shared control keypair (used
  to register the messaging DID a `history-sync/1.0` message is
  authenticated with) is what makes a peer trusted here at all. It defines
  no new trust boundary of its own.
- Content confidentiality is exactly what pairwise DIDComm v2 encryption
  between the two specific devices already provides; there is no
  additional encryption layer here, and no content is ever exposed to the
  mediator beyond what ordinary message delivery already exposes (the
  mediator relays ciphertext it cannot read either way).
- A device that has been `device-revoke`d but not yet had its mediator
  registration removed could still answer or issue `history-sync/1.0`
  requests until that removal takes effect — this protocol adds no
  independent revocation check of its own; it relies entirely on
  `multi-device/1.0`'s revocation actually being carried out.
- Hashes exchanged here (`chunk-manifest-response`/`chunk-members-response`)
  reveal the *existence and count* of messages in a range to any device
  that can authenticate as a sibling, even before that device fetches
  their content — a consequence of trusting every enrolled device
  equally, consistent with `multi-device/1.0`'s own security model.

## Message Reference

### `sync-summary-request`

Sent to a sibling device to check whether one or more collections are in
sync, before doing any more expensive comparison.

| Field | Type | Description |
|---|---|---|
| `collections` | array of object | The sender's own current state per collection it wants checked. |
| `collections[].collection_id` | string | `"contacts"`, `"groups"`, `"devices"`, or `"messages:<conversation_id>"`. |
| `collections[].count` | integer | Total items the sender currently holds in this collection. |
| `collections[].oldest_id` / `collections[].newest_id` | string | Present for chunkable collections (typically `messages:*`); the sender's own oldest/newest held item id, reflecting its retention window. |

### `sync-summary-response`

| Field | Type | Description |
|---|---|---|
| `collections` | array of object | One entry per collection from the request that the responder has an opinion on (an out-of-window collection may be omitted entirely). |
| `collections[].collection_id` | string | Echoes the request. |
| `collections[].in_sync` | boolean | `true` if the responder's own count/cursors already match the request. |
| `collections[].count` / `oldest_id` / `newest_id` | — | The responder's own current values, same shape as the request. |

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
over items the sender knows the recipient is missing (see Design By
Contract on bidirectional diffing).

| Field | Type | Description |
|---|---|---|
| `collection_id` | string | Which collection. |
| `items` | array of object | Full content for each item, shaped per `collection_id` (a `ChatMessage` for `messages:*`, a `Contact` for `contacts`, etc. — this protocol does not itself define those shapes). |

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
| `items` | array of object | Up to `limit` items older than `before` that the responder still holds, newest-first. |
| `has_more` | boolean | `false` means the responder has nothing older than what it just returned — a requester still wanting more should ask a different sibling. |

## Implementations

Name / Link | Implementation Notes
--- | ---
_(none yet)_ | Proposed alongside [`multi-device/1.0`](../../multi-device/1.0/readme.md) for [`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat); not yet implemented.

## Endnotes

### Future Considerations

- A real Merkle-style recursive split for very large mismatched chunks
  (today: one flat `chunk-members-response` per mismatched chunk), if
  `chunk_size` ever needs to be large enough that a single member-list
  response becomes unwieldy on its own.
- Whether an item fetched only for on-demand `backfill-request` display
  gets persisted back into local storage (subject to the same retention
  policy on the next cleanup pass) or stays purely ephemeral for that
  viewing session — left as an implementation choice for now, not
  specified here.
- A way to signal "don't bother asking me, I'm intentionally
  short-retention for everything," so a backfill requester can skip
  known-bounded siblings and go straight to whichever device is more
  likely to actually hold the answer.
