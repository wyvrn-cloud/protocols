---
title: Files
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/files/1.0
status: Proposed
summary: Lets an agent put a file that is too big for a message at a storage host it is allowed to use, over HTTPS in resumable chunks, and hand it to anyone as a DIDComm attachment by reference (links + hash). DIDComm carries the asking, the granting and the bookkeeping; the bytes go over HTTPS. The host stores what it is given and never needs to read it.
tags:
  - files
  - storage
  - attachments
authors:
  - name: wyvrn
---

## Summary

A DIDComm attachment can carry its bytes inline (`data.base64`) or point at
them (`data.links`, with `data.hash`). Inline is right for a thumbnail and
wrong for a recording: every mediator on the route queues, stores and
forwards the whole thing, base64'd, once per recipient, and a dropped
transfer starts again from the first byte.

This protocol is how an agent gets bytes to a place a link can point at. An
`uploader` asks a `host` for room, is given an address to put the bytes at,
puts them there in chunks over HTTPS (so a transfer resumes where it
stopped), and tells the host when it is done. The host checks the hash and
the file is then fetchable by its address until it expires. Anyone the
uploader hands the address to — in a `chat-message/1.0` message, a
`media-sharing/1.0` `share-media`, or any other message with an attachment —
fetches it with a plain `GET`.

The host keeps bytes; it doesn't look at them. An uploader that wants the
host unable to read a file encrypts it before upload and sends the key
inside the DIDComm message that shares it, as `chat-message/1.0`'s
`ciphering` has it. Nothing here changes for that.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Motivation

The didcomm.org registry has `media-sharing/1.0` for *sharing* a file that is
already at a URL, and `vaults/1.0` and `swarm/1.0` for long-term storage.
None of them says how an agent gets a large file onto a server in the first
place, how a transfer that drops partway resumes, or how a host decides who
may use it and how much. That is the gap: a short protocol in front of an
ordinary HTTPS upload and download, so that the rest of the family can
assume a file has somewhere to be.

Two things were learned in deciding the shape:

- **Keep the bytes off the DIDComm route.** Chunks-as-messages works through
  mediators, but every chunk pays a full envelope and a mediator queue is the
  wrong place for a gigabyte. DIDComm asks and grants; HTTPS carries.
- **Resume by offset, not by chunk list.** A host that remembers how many
  bytes it has lets an uploader continue from there after any failure, with
  one `HEAD`. The uploader needn't keep a manifest.

## Roles

| Role | Description |
|---|---|
| `uploader` | An agent that puts files at a host, and may delete them, keep them longer, and ask what it has there. |
| `host` | The storage service: decides who may upload and how much, keeps the bytes, serves them, and removes them when they expire. |

Whoever fetches a file plays no role in this protocol: a link is a link.

## Connectivity

Each request is one DIDComm message from the `uploader` to the `host` and
one answer back, by whatever route the two have: a host is usually a
`did:web` with its own endpoint, and an uploader sends with
`return_route: "all"` to be answered in the same HTTP response. Every message
from the uploader MUST be sender-authenticated (authcrypt): the host's
decisions are per uploader DID, and an anonymous message is refused.

The bytes move over HTTPS, outside DIDComm, at addresses the host hands out.

## States

| Role | State | Enters on | Leaves on |
|---|---|---|---|
| `uploader` | `uploading` | an `upload-granted` | `completed`; or giving the file up |
| `host` (per file) | `uploading` | granting an `upload` | `complete` that checks out → `stored`; the upload's deadline passing, or `delete` → gone |
| `host` (per file) | `stored` | a `complete` that checked out | its expiry passing, or `delete` → gone |

A file that is gone answers nothing but `404` at its addresses, and a
`problem-report` to any message naming it.

## Basic Walkthrough

A build machine (`did:peer:4zQmBuilder…`) has a 310 MB recording to get to
a headset. The host is `did:web:files.example`, and the build machine's DID
is on its list of uploaders.

1. The build machine hashes the file and asks for room:

   ```json
   {
     "id": "4a1f0c9e-2b7d-4c3e-9f8a-6d5b4c3a2b1f",
     "type": "https://wyvrn.app/files/1.0/upload",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:web:files.example"],
     "created_time": 1792000000,
     "return_route": "all",
     "body": {
       "name": "rec1.tar.zst",
       "media_type": "application/zstd",
       "byte_count": 325058560,
       "hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
       "keep_seconds": 1209600
     }
   }
   ```

2. The host has room for it and answers with where to put the bytes:

   ```json
   {
     "id": "9c2e7b1a-0d4f-4a8b-b3c6-e5f4a3b2c1d0",
     "type": "https://wyvrn.app/files/1.0/upload-granted",
     "from": "did:web:files.example",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "4a1f0c9e-2b7d-4c3e-9f8a-6d5b4c3a2b1f",
     "created_time": 1792000001,
     "body": {
       "file": "Hc3kq7vQ2mX9bL0pR5tY8w",
       "upload_url": "https://files.example/u/Hc3kq7vQ2mX9bL0pR5tY8w",
       "chunk_bytes": 67108864,
       "offset": 0,
       "upload_expires_time": 1792086400,
       "expires_time": 1793209601
     }
   }
   ```

3. The build machine puts the bytes, 64 MiB at a time:

   ```http
   PUT /u/Hc3kq7vQ2mX9bL0pR5tY8w HTTP/1.1
   Host: files.example
   Upload-Offset: 0
   Content-Length: 67108864
   Content-Type: application/offset+octet-stream

   <bytes 0 … 67108863>
   ```

   ```http
   HTTP/1.1 204 No Content
   Upload-Offset: 67108864
   ```

   The connection drops during the fourth chunk. The build machine asks
   where things stand and carries on from there:

   ```http
   HEAD /u/Hc3kq7vQ2mX9bL0pR5tY8w HTTP/1.1
   Host: files.example
   ```

   ```http
   HTTP/1.1 200 OK
   Upload-Offset: 213909504
   Upload-Length: 325058560
   ```

4. With the last byte in, it says so:

   ```json
   {
     "id": "d7e6f5a4-b3c2-4d1e-8f9a-0b1c2d3e4f5a",
     "type": "https://wyvrn.app/files/1.0/complete",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:web:files.example"],
     "created_time": 1792000400,
     "return_route": "all",
     "body": { "file": "Hc3kq7vQ2mX9bL0pR5tY8w" }
   }
   ```

   The host hashes what it has, finds the hash it was promised, and answers:

   ```json
   {
     "id": "1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e",
     "type": "https://wyvrn.app/files/1.0/completed",
     "from": "did:web:files.example",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "d7e6f5a4-b3c2-4d1e-8f9a-0b1c2d3e4f5a",
     "created_time": 1792000403,
     "body": {
       "file": "Hc3kq7vQ2mX9bL0pR5tY8w",
       "url": "https://files.example/f/Hc3kq7vQ2mX9bL0pR5tY8w",
       "name": "rec1.tar.zst",
       "media_type": "application/zstd",
       "byte_count": 325058560,
       "hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
       "expires_time": 1793209601
     }
   }
   ```

5. The build machine tells the headset, in whatever message it was going
   to send anyway, with the file as an attachment by reference:

   ```json
   {
     "id": "f0e1d2c3-b4a5-4968-8776-655443322110",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/put",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:peer:4zQmHeadset..."],
     "created_time": 1792000404,
     "expires_time": 1793209601,
     "body": { "path": "recordings/rec1.tar.zst", "file": "rec" },
     "attachments": [
       {
         "id": "rec",
         "filename": "rec1.tar.zst",
         "media_type": "application/zstd",
         "byte_count": 325058560,
         "data": {
           "links": ["https://files.example/f/Hc3kq7vQ2mX9bL0pR5tY8w"],
           "hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
         }
       }
     ]
   }
   ```

   The headset fetches the link (with `Range`, in as many pieces as it
   likes), checks the hash, and has the recording. Two weeks later the host
   removes it.

Had the host been out of room for this uploader, step 2 would have been a
`problem-report` with code `e.p.msg.quota`, saying how much is in use and how
much is allowed, and nothing would have been put anywhere.

## Design By Contract

### Who may upload

- A host decides who is an uploader and how much each may keep there (a
  quota: the sum of `byte_count` over their files not yet gone, uploads in
  progress included). How it decides is its own business: a list in its
  settings, a payment, anyone who authenticates. A message from anyone else
  is answered `e.p.msg.not-allowed`.
- Decisions are per sender DID, the one the message was authenticated as. A
  host SHOULD follow an uploader's change of DID announced with a verified
  `from_prior`, as a mediator does, so that their files stay theirs.

### Asking (`upload`)

- `byte_count` and `hash` are of the bytes exactly as they will be put: an
  uploader that encrypts hashes the ciphertext. The host refuses an `upload`
  whose `byte_count` is over its per-file limit (`e.p.msg.too-large`) or
  would take the uploader over quota (`e.p.msg.quota`), before anything is
  put.
- `keep_seconds` asks how long the file should stay once complete. The host
  grants at most its own maximum, and its default when it is left out; the
  answer's `expires_time` is the truth. An uploader MAY ask for longer later
  (`extend`).
- **An `upload` is idempotent by `hash` and `byte_count`.** An uploader that
  asks again for a file the host is already taking from it, or already holds
  from it, is answered with that file's `upload-granted` again: the same
  `file`, the same `upload_url`, and `offset` saying how much is there. That
  is how an uploader that lost the grant resumes. A file another uploader
  holds with the same hash is not the same file: each uploader's files are
  their own.

### Putting the bytes

- The bytes go to `upload_url` in `PUT` requests of at most `chunk_bytes`
  each, in order, each with `Upload-Offset` saying where its first byte goes.
  The host appends a chunk whose offset is exactly what it holds, and
  answers `204` with the new `Upload-Offset`. A chunk at any other offset is
  refused `409` with the current `Upload-Offset`, and nothing is written: the
  uploader reads the header and continues from there.
- `HEAD upload_url` answers `Upload-Offset` (what is there) and
  `Upload-Length` (what was promised). An uploader resumes with this after
  any failure; it needn't ask the host over DIDComm again, though it may
  (`upload` with the same hash).
- A chunk longer than `chunk_bytes`, or that would take the file past
  `byte_count`, is refused `413`. An address the host doesn't know, or whose
  upload has passed `upload_expires_time`, answers `404`; one whose file is
  already complete, `410`.
- A chunk the host has written stays written: a `PUT` that got no answer
  (the connection dropped) may or may not have landed, and `HEAD` says which.
  The uploader never has to re-put what the host has.
- Who may `PUT` is whoever has the address. `upload_url` is unguessable and
  is told to the uploader alone; an uploader that hands it out before
  `complete` has let someone else write its file.

### Finishing (`complete`)

- The host accepts `complete` only when it holds exactly `byte_count` bytes
  (`e.p.msg.incomplete` otherwise, with the offset as its first argument)
  whose hash is `hash` (`e.p.msg.hash-mismatch` otherwise; the bytes are
  discarded and the uploader starts again). From then on the file is served
  at `url` and `PUT` is refused.
- `completed` repeats what the file is (`name`, `media_type`, `byte_count`,
  `hash`) and when it goes (`expires_time`), so that the uploader can write
  the attachment that shares it from this one message.

### Fetching

- `GET url` serves the bytes with `Content-Type` as `media_type`,
  `Content-Length`, and a `Content-Disposition` naming `name`; it honours
  `Range` (one range) and answers `HEAD`. Its `ETag` is the hash, so a fetcher
  that holds the hash needn't fetch twice. A file that is gone answers `404`.
- Who may `GET` is whoever has the address, which is unguessable: the file is
  shared by sharing the link. There is no reader-side authentication, which
  keeps a link fetchable by any DIDComm agent, a browser, or `curl`. An
  uploader that wants a file readable only by some people encrypts it and
  sends them the key (below).
- A fetcher MUST check the bytes against the `hash` the attachment carries
  before treating them as the attachment, as DIDComm requires of any
  attachment by reference.

### Keeping and letting go

- A file goes when its `expires_time` passes, or on the uploader's `delete`.
  An upload that is never completed goes at `upload_expires_time`. The host
  frees the quota it held either way.
- `extend` moves `expires_time` later, to at most the host's maximum from
  now; `extended` says what it is. A host MAY refuse to extend a file past
  what it would grant a new one.
- `list` answers with every file the uploader has at the host, complete or
  not, with the quota and what is in use. There is no paging: a host that
  holds thousands of files for one uploader may cap the list and say so with
  `truncated: true`.

### Encrypting

- A host stores bytes and serves bytes; it has no part in what they are. An
  uploader that doesn't want the host (or anyone with the link but not the
  message) to read a file encrypts it first, with a key of its own per file,
  and carries the key in the message that shares the attachment: the
  `ciphering` object `chat-message/1.0` defines, in `media-sharing/1.0`'s
  shape (`algorithm` `aes-256-gcm`; `parameters` with `key`, `iv` and `tag`,
  hex-encoded). `hash` and `byte_count` are then of the ciphertext.
- Nothing in this protocol says whether a file is encrypted. A fetcher
  learns that from the message that shared it.

## Security

- **The host learns what it stores and who fetches it.** Sizes, names,
  media types, upload and download times and the addresses they come from.
  Encryption hides the content and nothing else; an uploader that minds
  pads, and names files blandly.
- **A link is a capability.** Whoever has `url` can fetch the file until it
  goes; whoever has `upload_url` can write it until it is complete. Both are
  unguessable (at least 128 bits of randomness) and sent only inside
  encrypted DIDComm messages. An uploader revokes by `delete`, which stops
  future fetches and nothing else: a file already fetched is already fetched.
- **The host's word on who an uploader is** is the authenticated sender DID,
  and nothing in a message body. A host MUST refuse an anonymous (anoncrypt)
  message and MUST NOT act on a `from` it didn't authenticate.
- **The host's own exposure** is bounded by its limits: a per-file maximum,
  a per-uploader quota, a chunk size that bounds any one request's body, and
  deadlines for uploads that never finish. A host SHOULD also bound how many
  uploads one uploader may have in progress.
- **A fetcher's exposure** is the hash check: bytes that don't hash to what
  the attachment says are not the attachment, whatever the host served.
  `byte_count` lets a fetcher refuse before fetching.
- **Nothing is executed.** A file is bytes. What a receiver does with a file
  named `update` is that receiver's protocol's business (`didcomm-rpc/1.0`,
  say), and that protocol has to say what it checks before acting on
  anything fetched.

## Composition

- **With DIDComm attachments.** The outcome of this protocol is an
  attachment by reference exactly as the DIDComm v2.1 specification has it:
  `data.links` (the file's `url`) and `data.hash`, with `byte_count`,
  `media_type` and `filename` beside them. Any message type that carries
  attachments can carry one.
- **With `chat-message/1.0`.** A chat message's media by reference is such
  an attachment, and that protocol's `ciphering` is how the key travels when
  the file was encrypted. A `files/1.0` host is one kind of "storage
  service" that protocol leaves open.
- **With `media-sharing/1.0`.** A `share-media` item's `attachment` can
  point at a file here. A `request-media` from someone who finds the link
  gone is answered by uploading again (a new `upload`: the old file is gone)
  and sharing the new link.
- **With `discover-features/2.0`.** A host discloses
  `https://wyvrn.app/files/1.0` with role `host`. An uploader needn't
  disclose anything.
- **With `report-problem/2.0`.** Refusals are
  `https://wyvrn.app/files/1.0/problem-report` with the codes below.

## Message Reference

Every message from the uploader MUST be sender-authenticated. Every answer
from the host carries `thid` set to the message it answers.

### `upload`

Message Type URI: `https://wyvrn.app/files/1.0/upload`

Sent by an `uploader`. Asks for room for one file.

| Field | Type | Description |
|---|---|---|
| `name` | string | REQUIRED. A file name, at most 255 bytes, no path separators. What `completed` and the download's `Content-Disposition` repeat. |
| `media_type` | string | REQUIRED. The bytes' media type, as the download will be served. |
| `byte_count` | integer | REQUIRED. How many bytes will be put, exactly. |
| `hash` | string | REQUIRED. A [multihash](https://multiformats.io/multihash/), base58btc-encoded, of the bytes exactly as they will be put; a host MUST support `sha2-256`. |
| `keep_seconds` | integer | OPTIONAL. How long to keep the file once complete, in seconds. The host grants at most its maximum, and its default when this is left out. |

Schema: [`schemas/upload.json`](schemas/upload.json).

### `upload-granted`

Message Type URI: `https://wyvrn.app/files/1.0/upload-granted`

Sent by the `host` in answer to an `upload` it accepts, or repeats.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The host's id for the file: what later messages name. |
| `upload_url` | string | REQUIRED. Where to `PUT` the bytes. Unguessable; for the uploader alone. |
| `chunk_bytes` | integer | REQUIRED. The most bytes one `PUT` may carry. |
| `offset` | integer | REQUIRED. How many bytes the host holds already: `0` for a new file. |
| `upload_expires_time` | integer | REQUIRED. UTC epoch seconds. When an upload not yet completed is dropped. |
| `expires_time` | integer | REQUIRED. UTC epoch seconds. When the file will go once complete, as granted. |

Schema: [`schemas/upload-granted.json`](schemas/upload-granted.json).

### `complete`

Message Type URI: `https://wyvrn.app/files/1.0/complete`

Sent by the `uploader` once every byte is put.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |

Schema: [`schemas/complete.json`](schemas/complete.json).

### `completed`

Message Type URI: `https://wyvrn.app/files/1.0/completed`

Sent by the `host` when the bytes are all there and hash to what was
promised. The file is fetchable from this moment.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |
| `url` | string | REQUIRED. Where the file is fetched from: what goes in an attachment's `data.links`. |
| `name` | string | REQUIRED. As given. |
| `media_type` | string | REQUIRED. As given. |
| `byte_count` | integer | REQUIRED. As given, and as held. |
| `hash` | string | REQUIRED. As given, and as checked: what goes in an attachment's `data.hash`. |
| `expires_time` | integer | REQUIRED. UTC epoch seconds. When the file goes. |

Schema: [`schemas/completed.json`](schemas/completed.json).

### `extend`

Message Type URI: `https://wyvrn.app/files/1.0/extend`

Sent by the `uploader`. Asks for a complete file to be kept longer.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |
| `keep_seconds` | integer | REQUIRED. How long from now, in seconds. The host grants at most its maximum. |

Schema: [`schemas/extend.json`](schemas/extend.json).

### `extended`

Message Type URI: `https://wyvrn.app/files/1.0/extended`

Sent by the `host`.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |
| `expires_time` | integer | REQUIRED. UTC epoch seconds. When the file now goes. |

Schema: [`schemas/extended.json`](schemas/extended.json).

### `delete`

Message Type URI: `https://wyvrn.app/files/1.0/delete`

Sent by the `uploader`. Removes a file, complete or not. Deleting a file
that is already gone is not an error: the answer is the same.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |

Schema: [`schemas/delete.json`](schemas/delete.json).

### `deleted`

Message Type URI: `https://wyvrn.app/files/1.0/deleted`

Sent by the `host`.

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The file's id. |

Schema: [`schemas/deleted.json`](schemas/deleted.json).

### `list`

Message Type URI: `https://wyvrn.app/files/1.0/list`

Sent by the `uploader`. Asks what it has at the host. The body is empty.

Schema: [`schemas/list.json`](schemas/list.json).

### `listing`

Message Type URI: `https://wyvrn.app/files/1.0/listing`

Sent by the `host`.

| Field | Type | Description |
|---|---|---|
| `quota_bytes` | integer | REQUIRED. What this uploader may keep in all. |
| `used_bytes` | integer | REQUIRED. What it keeps now, uploads in progress counted at their full `byte_count`. |
| `files` | array | REQUIRED. One object per file, newest first: `file`, `name`, `media_type`, `byte_count`, `hash`, `state` (`uploading` or `stored`), `expires_time`, and for a stored file `url`; for one uploading, `offset`, `upload_url` and `upload_expires_time`. |
| `truncated` | boolean | OPTIONAL. `true` if the host left some out. |

Schema: [`schemas/listing.json`](schemas/listing.json).

### `problem-report`

Message Type URI: `https://wyvrn.app/files/1.0/problem-report`

Sent by the `host` in place of any answer, as `report-problem/2.0` has it:
`body.code`, `body.comment` (with `{1}`-style placeholders), `body.args`.

| Code | Meaning |
|---|---|
| `e.p.msg.not-allowed` | The sender is not an uploader at this host. |
| `e.p.msg.quota` | The file would take the uploader over quota. `args`: bytes in use, bytes allowed. |
| `e.p.msg.too-large` | `byte_count` is over the host's per-file limit. `args`: the limit. |
| `e.p.msg.not-found` | No such file of this uploader's. |
| `e.p.msg.incomplete` | `complete` before every byte is there. `args`: the offset held. |
| `e.p.msg.hash-mismatch` | The bytes don't hash to `hash`. The upload is discarded. |
| `e.p.msg.invalid` | A field is missing or malformed. `args`: which. |

### The HTTP side

| Request | Answer |
|---|---|
| `PUT upload_url`, `Upload-Offset: n`, body of at most `chunk_bytes` | `204`, `Upload-Offset` (new total). `409` + `Upload-Offset` (wrong offset, nothing written). `413` (too long). `404` (unknown or past its deadline). `410` (already complete). |
| `HEAD upload_url` | `200`, `Upload-Offset`, `Upload-Length`. `404`, `410` as above. |
| `GET url` (`Range` honoured, one range) | `200` or `206`, `Content-Type`, `Content-Length`, `Content-Disposition: attachment; filename="…"`, `ETag: "<hash>"`, `Accept-Ranges: bytes`. `404` when gone. |
| `HEAD url` | The same headers, no body. |

The `PUT` body's `Content-Type` is `application/offset+octet-stream`, as tus
has it, which keeps a browser or proxy from treating it as a form.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-services`](https://github.com/wyvrn-cloud/services) | `services/files`: the `host` role, at `files.wyvrn.app`. Uploaders are a settings list with a quota each; bytes on disk, metadata in its database.
[`didcomm-rpc`](https://github.com/frostyfrog/didcomm-rpc) | The `uploader` role, in both its daemon and its CLI: how a build gets to a headset and a recording back.

## Endnotes

### Why the id is the capability

A separate token per file would be one more secret for both sides to keep,
and it would protect nothing the id doesn't: the id is sent only inside
encrypted messages, and is shared exactly when the file is meant to be
shared. Two secrets would matter if a reader could do something with the
download address that an uploader wouldn't want — but `PUT` is refused once
the file is complete, and `delete`/`extend` are DIDComm messages
authenticated by DID, not by address.

### Why offsets, not tus

[tus](https://tus.io) is the right idea and more than is needed: its
creation, termination, expiration and checksum extensions are what the
DIDComm half does here, with the host knowing who is asking. What is kept is
tus's one good primitive, `Upload-Offset`, and its header names, so that the
HTTP side is familiar.

### Future Considerations

- A host that lets an uploader hand out *write* access to someone else (a
  phone uploading a photo for a laptop's message).
- Per-chunk hashes, so that a fetcher can verify a gigabyte as it arrives
  rather than at the end, and decrypt as it goes. `chat-message/1.0`'s
  `ciphering` would need a chunked mode first.
- Storage that outlives a host (`swarm/1.0`), with this protocol as the way
  in.
