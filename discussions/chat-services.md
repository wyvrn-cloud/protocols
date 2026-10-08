# The three HTTP services the chat feature set depends on

[`chat-message/1.0`](../protocols/chat-message/1.0/readme.md) and its companions
are DIDComm protocols: everything they say travels end-to-end encrypted between
agents, through a mediator that sees ciphertext. Three things a modern chat does
don't fit in a DIDComm message, though, and each needs a small HTTP service
beside the mediator:

| Service | Why DIDComm alone doesn't do it |
|---|---|
| **Storage** | A picture or file over 256 KiB is too big to inline in a message that goes to every member of a group, through a mediator queue, separately per recipient. `chat-message/1.0` sends it *by reference* — a link — and something has to be at the other end of the link. |
| **Stickers** | A sticker pack is one set of images many people use. Sending the pack along with every sticker would be absurd; a pack is fetched once, by id, from wherever it was published. |
| **GIFs** | GIF search is a third-party API (Klipy, to start with) with an API key, and a chat app can't ship the key to every client. |

This is a design sketch of the three, not a protocol: what each is for, who runs
it, the HTTP interface the chat protocols actually depend on (kept to the
endpoints they need), what it stores and for how long, what it can see, how a
client might be authenticated, and what's still open. None of it is built yet.
Where the sketch says a client does something, it means the chat app's agent;
where it says the service does, it means a separate program an operator runs.

Common to all three:

- **Who runs it.** Whoever runs the mediator, deployed beside it, as a separate
  program with its own configuration. A chat identity doesn't have an account
  anywhere; what it has is a mediator it registered with, so the mediator's
  operator is the natural party to offer the rest. Nothing requires that,
  though: the chat message carries a full URL for every link, so a storage
  service, a sticker service and a GIF relay can each be anyone's.
- **Authentication is set by whoever runs the service.** Each service has
  some endpoints that cost the operator something (an upload, a pack
  registration, a GIF search that costs a provider call), and the operator
  will want to limit those to people it has agreed to serve, which in practice
  means people its mediator serves. Two obvious ways to do that, neither chosen
  here:
  - *A bearer token issued at onboarding.* When an agent completes its
    `mediate-request` with the mediator, the mediator hands it a token (or the
    agent fetches one from a mediator endpoint while authenticated as a mediated
    DID), and the agent sends it as `Authorization: Bearer …` to each service.
    Simple, standard, and the services only need to validate a token the
    mediator can mint; the token ties the request to a mediated identity, so
    the operator can revoke it when the mediation ends.
  - *A DIDComm-signed challenge.* The service answers an unauthenticated
    request with a nonce; the agent signs it with a key of its DID and sends the
    signature back; the service resolves the DID (a `did:peer:4` carries its own
    document) and checks the key. No shared secret, no token to leak, no
    dependence on the mediator; but one more round trip per session, and the
    service needs a DID resolver.
  Either way, *fetching* is a different question from *uploading* — see each
  service.
- **The app learns a service's address from configuration**, the way it learns
  the mediator's (`VITE_MEDIATOR_HTTP_URL` and friends in `wyvrn-chat`). Where a
  service's address needs to reach other people, it travels inside the chat
  message: the storage link in `attachments[].data.links`, the sticker
  service in `media[].sticker.service`, the GIF's provider URL. A recipient
  never needs to know the sender's services by any other route.
- **Every service is reachable from a browser**, which means CORS headers on
  every response, for the same reason `wyvrn-mediator` sends them: the chat
  app's client is a web page.

## 1. Storage service

### Purpose

Holds the bytes of an attachment too large to inline — `chat-message/1.0` puts
the line at 256 KiB — between the sender's upload and the recipients' fetches,
for a bounded time. It is a drop box, not a library: it keeps nothing it can
read, and nothing for long.

### What the chat protocol expects

From `chat-message/1.0` ("Media"): the sender encrypts the bytes with
`aes-256-gcm` under a fresh key, uploads the ciphertext, and puts the URL in
`attachments[].data.links`, the multihash of the *ciphertext* in `data.hash`,
and the key, IV and tag in the media item's `ciphering` — the shape
[`media-sharing/1.0`](https://didcomm.org/media-sharing/1.0) defines
(`algorithm`, `parameters.key`/`iv`/`tag`, hex). Every recipient fetches the
URL, checks the hash, decrypts, checks the tag. If the link is gone, a
recipient may ask the sender for the item again with `media-sharing/1.0`'s
`request-media`, and the sender uploads it afresh.

### Interface

Four endpoints. Paths are illustrative; what matters is the shape.

**`GET /limits`** — what the service will take. The app asks this before
offering to send a file, and shows the person the limit rather than failing
after the upload.

```json
{
  "max_bytes": 104857600,
  "retention_seconds": 2592000,
  "upload_auth": "bearer"
}
```

`max_bytes` is the largest single upload; `retention_seconds` the operator's
time limit (see Retention); `upload_auth` says which authentication an upload
needs (`"bearer"`, `"did-challenge"`, or `"none"`), so a client knows what to
do without a failed attempt.

**`POST /uploads`** — the ciphertext, as the request body (`Content-Type:
application/octet-stream`), with headers saying how many recipients will fetch
it and, optionally, the uploader's own hash of the body so the service can
reject a corrupted upload:

```
POST /uploads
Authorization: Bearer …
Content-Type: application/octet-stream
Content-Length: 4194304
X-Recipient-Count: 3
X-Content-Hash: z…   (multihash, base58btc, same value the message will carry)
```

Response:

```json
{
  "url": "https://storage.example/o/7f3c…",
  "expires": 1794000000,
  "fetch_tokens": ["t1…", "t2…", "t3…"]
}
```

`url` goes into `data.links`. `expires` is the time limit the service applied.
`fetch_tokens` is present only in the per-recipient-token model (see
Retention); the sender then gives each recipient one, inside the message.

**`GET /o/<id>`** — the bytes. Unauthenticated in the simplest model (the URL
is unguessable and the bytes are ciphertext; a key in a message is a key for
everyone who has the message, and so is the link), or with a fetch token
(`?t=…`) in the per-recipient model. `Range` requests, so a video can be
played before it has arrived. `404` once the object is gone, which is a
condition the chat protocol already handles.

**`DELETE /o/<id>`** — the uploader withdrawing it (a deleted message). Only
the uploader can; the service remembers who uploaded what. A recipient who
already fetched has it; this is a courtesy, as `message-delete` is.

### Retention

"Until every recipient has fetched it, or the operator's time limit, whichever
comes first." The time limit is the easy half. The hard half is that the
service must not learn who the recipients are — it sees an upload from one
authenticated identity and fetches from addresses, nothing more — and yet it
has to know when *all* of them have fetched. Three ways, from simplest to most
exact:

1. **The uploader states a count; fetches are counted.** `X-Recipient-Count:
   3`, and the object is deleted after the third completed fetch (a fetch is a
   full read of the body, or the last `Range`). The service learns a number,
   not identities. The flaw: a recipient's two devices each fetch (so a count
   of members undercounts), a recipient fetches twice (a reinstall), or a
   recipient on tap-to-load never fetches at all (the time limit then does
   the job). The uploader can't state the right number, because it doesn't
   know how many devices its recipients have, and shouldn't. A sender that
   wants to be safe states a generous count and leaves the rest to the time
   limit. Simple, and probably good enough.
2. **Per-recipient fetch tokens.** The upload asks for *n* tokens; the sender
   gives one to each recipient inside the encrypted message (a field in the
   media item, next to `ciphering`); a fetch presents its token; the object is
   deleted once every token has been used at least once. The service learns
   that *n* distinct parties exist and which token fetched, not who any of
   them is. A recipient's several devices share one token, so a count of
   members is the right count. Better than (1) at the cost of a field in the
   message that `chat-message/1.0` doesn't define yet, and the same
   never-fetching recipient problem.
3. **The recipients tell the sender, and the sender tells the service.** A
   recipient's agent acks the fetch to the sender over DIDComm (a
   `media-sharing/1.0` ack, or a receipt), and the sender issues the `DELETE`
   when it has heard from everyone. Most exact, and the service learns
   nothing at all about recipients; but a sender offline for a week keeps the
   object alive for a week, which is what the time limit is for anyway.

Start with (1), with the time limit as the backstop it is in every model; (2)
is the upgrade if (1)'s over- and under-counting turns out to matter. In all
three, the operator's time limit (`retention_seconds`) is a hard ceiling: an
object is deleted when it is reached regardless. Thirty days is a reasonable
default; a sender knows the limit from `/limits` and can warn a recipient who
was away ("this picture is no longer available, ask Alice to send it again",
which is `request-media`).

### What it stores

Per object: the ciphertext, its size, the upload time, the expiry, the
uploader's identity (as the authentication gave it: a token's subject or a
DID), the recipient count or the tokens, and a fetch counter. No filename, no
media type, no message id, no conversation: none of that is sent to it, and it
has no use for it. Access logs are the operator's choice and should be short.

### What it can see

Ciphertext, and its size. Sizes and timing say something — a 4 MB object
uploaded by one identity and fetched three times in the next minute is a
picture sent to a group of three — but not what, or to whom, beyond the fetch
addresses. The service never has the key; the key is in a message it never
sees. A compromised storage service hands an attacker ciphertext and traffic
patterns, nothing more. That is the whole reason the client encrypts before
uploading rather than trusting the operator.

### Authentication

Uploads and deletes: set by the operator, one of the two options above. A
mediator operator who already knows its mediated DIDs will likely issue
tokens. Fetches: open, or by fetch token, as in Retention; requiring an
*identity* to fetch would tell the service who the recipients are, which is
exactly what it must not learn, so a fetch is never authenticated by DID.

### Open questions

- **Quota.** Per identity, per day or in total? `/limits` could report the
  uploader's remaining quota when authenticated.
- **Fetch counting and tap-to-load.** A recipient who never fetches keeps an
  object alive until the time limit. Fine, but it means the time limit, not
  the fetch count, is what usually deletes things, and the operator should
  size storage for that.
- **A browser's `Range` requests and "completed fetch".** A video played
  halfway counts as fetched or not? Probably yes once any byte was read: the
  recipient's agent can fetch the whole object into its own storage, as the
  chat protocol encourages (bytes fetched by reference are stored locally).
- **The `fetch_tokens` field in the message**, if model (2) is adopted: a
  minor-version addition to `chat-message/1.0`'s media item.
- **Content the operator is obliged to remove.** It cannot see it, which is a
  feature, but it can act on a URL it is given. Out of scope here, noted.

## 2. Sticker service

### Purpose

Publishes sticker packs so that a sticker in a message is a small reference —
`pack_id`, `sticker_id`, and the service it lives on — and a receiver that
wants the pack (to use it themselves, or to see the rest) fetches it once by
id. Packs are made by people, in the app, from their own images; there is no
catalogue the operator curates.

Custom emoji — small images a person uses inline in text, which
`chat-message/1.0` lists as a future consideration — are the same thing at a
different size, so a pack document has a `kind`, and an emoji pack is
published, fetched and installed exactly like a sticker pack.

### What the chat protocol expects

From `chat-message/1.0`: a `media` item with `kind: "sticker"` carries
`sticker: { pack_id, sticker_id, service }`, and the sticker's image is *also*
attached, inline or by reference, so that the message shows without the
service. The service is for "add this pack", not for showing a received
sticker. `history-sync/1.1`'s `stickerPacks` collection syncs the person's
installed and own packs between their devices by `(id, service)`.

### Interface

**`GET /packs/<pack_id>`** — the pack document (below). This is what
`media[].sticker.service` points at: the message says `service:
"https://stickers.example"` and the receiver fetches
`https://stickers.example/packs/<pack_id>`. Open to anyone with the id, in the
same spirit as a storage link: an id is a capability. A pack with
`shareable: false` is served all the same (see the flag below); the flag tells
the app not to offer "add this pack" to a receiver, it does not hide the
pack.

**`GET /packs/<pack_id>/stickers/<sticker_id>`** — one sticker's bytes, when
the document carries a `url` rather than inline bytes. Immutable: a changed
sticker is a new sticker id.

**`PUT /packs/<pack_id>`** — publish or update a pack. Authenticated as the
author; the service records the author on first publication and refuses a
later `PUT` from anyone else. The body is the pack document, with each
sticker's bytes inline (base64) or uploaded first by a `POST
/packs/<pack_id>/stickers` that answers with the sticker's `url`. Updating
means replacing the document; a receiver that installed the pack re-fetches
it when it sees a sticker id it doesn't have.

**`DELETE /packs/<pack_id>`** — the author withdrawing it. Devices that have
the pack keep it; a receiver fetching it afterwards gets `404` and shows the
sticker from the message's own attachment.

**`GET /limits`** — the limits the operator fixed (below), so the app can
refuse an image before trying.

### The pack document

What `GET /packs/<pack_id>` returns, and what `PUT` sends:

```json
{
  "id": "0b1a7c2e-5d4f-4e3a-9c8b-7a6d5e4f3c2b",
  "kind": "stickers",
  "name": "Office dog",
  "author": "did:peer:2...alice",
  "shareable": true,
  "created": 1791400000,
  "updated": 1791500000,
  "stickers": [
    {
      "id": "sit",
      "media_type": "image/webp",
      "width": 512,
      "height": 512,
      "url": "https://stickers.example/packs/0b1a7c2e-5d4f-4e3a-9c8b-7a6d5e4f3c2b/stickers/sit",
      "hash": "zQm…",
      "emoji": ["🐶", "🪑"]
    },
    {
      "id": "zoom",
      "media_type": "image/webp",
      "animated": true,
      "width": 512,
      "height": 512,
      "data": "UklGRi…",
      "hash": "zQm…",
      "emoji": ["🐶", "💨"]
    }
  ]
}
```

| Field | Description |
|---|---|
| `id` | A UUID the maker chose when the pack was created, so that the same pack keeps its id if it is ever published on a second service. |
| `kind` | `"stickers"` or `"emoji"`. The same document either way; an emoji pack's images are expected small (see Limits) and shown inline in text. |
| `name` | Shown in the picker. |
| `author` | The DID of the person who made it, as the service authenticated them. A receiver shows it as the author's name if the author is a contact, otherwise as a DID. |
| `shareable` | Whether the maker allows others to add the pack. A courtesy flag, not access control: anyone who received a sticker has its image and its pack id, and the service serves the pack to anyone who asks. An app honours it by not offering "add this pack" on a sticker from a non-shareable pack. |
| `created`, `updated` | Epoch seconds. |
| `stickers[].id` | Unique within the pack; what `media[].sticker.sticker_id` carries. |
| `stickers[].media_type` | `image/webp` or `image/png` for a still image; `image/webp` (animated), `image/gif` or `image/apng` for an animated one, with `animated: true`. |
| `stickers[].width`, `height` | Pixels. |
| `stickers[].url` *or* `stickers[].data` | Where the bytes are, or the bytes inline (base64). A service may serve either; inline is simplest for a small pack and costs one request for the whole pack. |
| `stickers[].hash` | Multihash of the bytes, base58btc, so a receiver can check what it fetched and so that the same sticker is recognised across packs. |
| `stickers[].emoji` | Optional keywords, as emoji, for finding the sticker by typing an emoji or its shortcode in the picker. |

### Limits

To be fixed when built; the numbers here are the kind of thing, and
`GET /limits` reports what the operator chose:

| | Stickers | Emoji |
|---|---|---|
| Image size | up to 512 × 512 | up to 128 × 128 |
| Bytes per image | 500 KB (animated included) | 64 KB |
| Images per pack | 120 | 200 |
| Packs per author | operator's choice | operator's choice |

The app resizes and converts the person's images to fit before uploading; the
service rejects what doesn't.

### What it stores

Pack documents and their images, for as long as the author leaves them
published; the author's identity per pack. Nothing about who fetched what
beyond ordinary access logs, which should be short. A pack is public content
by design, so there is nothing to encrypt.

### What it can see

Everything in a pack: it is published, unencrypted, under the author's DID.
And which addresses fetch which pack, which says who received a sticker from
it (within the receiver's privacy setting; see the GIF relay for the same
concern) — a reason a receiver should fetch a pack only when the person asks
to add it, never automatically on seeing a sticker, which the message's own
attachment makes unnecessary.

### Authentication

Publishing and deleting: as the operator sets, one of the two options above,
and the service binds each pack to the identity that first published it.
Fetching: open.

### Open questions

- **Takedown.** Undecided. A sticker pack is user-published content under an
  operator's domain; the operator will have obligations, and the service has
  the `DELETE` to meet them, but who may invoke it beyond the author, and
  whether a receiver is told why a pack went away, is not designed.
- **Republishing.** A received shareable pack can be re-uploaded by its
  receiver to their own service under their own DID; is that a copy with a
  new `author`, or should the document carry an `origin` (the first service
  and author)? The `id` is kept, which is a start.
- **A pack's id across services.** `history-sync/1.1`'s `stickerPacks` keys on
  the pack id and carries the service; a pack present on two services is two
  items or one? One, if ids are UUIDs chosen by the maker; the item then
  records the service the person fetched it from.
- **Animated formats.** Animated WebP is the practical choice (Android, every
  browser), but Lottie/TGS stickers are much smaller for the same animation
  and are what Telegram and Signal use. Add `application/x-lottie+json` when
  the app can render it.

## 3. GIF relay

### Purpose

Stands between the app and a GIF provider (Klipy first; the interface is
provider-neutral) so that the provider's API key never leaves the operator's
server and the users' addresses never reach the provider's *search* API. The
chosen GIF is then fetched from the provider directly by every receiver, which
the provider does see; the relay hides the search, not the result.

### What the chat protocol expects

From `chat-message/1.0`: a GIF is a `media` item with `kind: "gif"`, whose
attachment's `data.links` points at the provider's URL for the GIF (not the
relay's), sent without `ciphering` — the bytes are at a host the sender does
not control, and are public anyway. `width`, `height` and ideally a `preview`
thumbnail or a `blurhash` let the receiver lay it out before fetching. A
receiver loads it automatically by default, with a tap-to-load privacy
setting, which `chat-message/1.0`'s Security section asks every implementation
to offer ("a link is a fetch").

### Interface

Two endpoints, both returning the same item shape:

**`GET /gifs/search?q=<terms>&limit=<n>&cursor=<c>&lang=<tag>`**

**`GET /gifs/trending?limit=<n>&cursor=<c>&lang=<tag>`**

```json
{
  "items": [
    {
      "id": "klipy:abc123",
      "title": "excited dog",
      "width": 480,
      "height": 270,
      "gif": "https://cdn.klipy.example/abc123.gif",
      "mp4": "https://cdn.klipy.example/abc123.mp4",
      "webp": "https://cdn.klipy.example/abc123.webp",
      "preview": "https://cdn.klipy.example/abc123-s.webp",
      "preview_width": 160,
      "preview_height": 90
    }
  ],
  "next": "c2"
}
```

`gif` is what goes into `data.links`; `mp4` and `webp` are alternates the app
may prefer for playback or size (and may send as additional links, since
`data.links` is an array); `preview` is the small still or animated thumbnail
the picker shows and the app may download and attach inline as the message's
`preview`. `next` pages. The relay translates the provider's response into
this shape, so swapping providers changes the relay, not the app.

The relay may also need whatever the provider requires on selection (some
providers ask for a "share" or "register" call for their analytics); if so,
**`POST /gifs/<id>/selected`**, fire-and-forget from the app, made by the relay
to the provider without the user's address.

### What it stores

Nothing, beyond a short response cache (the same trending list for everyone,
for a few minutes) and whatever rate-limiting needs. No search history: a
search term is a user's, and the relay should forget it as soon as it has
answered.

### What it can see

The relay sees every search term and the address and identity (if
authenticated) of who searched. The provider sees the search terms too — the
relay forwards them — but from the relay's address, not the user's, and
without the user's identity. The provider then sees a fetch of the chosen GIF
from every receiver that loads it, with each receiver's address: that is the
"a link is a fetch" concern, and the tap-to-load setting is the answer for a
receiver who minds. A sender who minds can send the GIF as an ordinary
attachment instead (download it, attach it, by reference through the storage
service if large), at which point it is a picture like any other and the
provider sees only the sender's one fetch.

### Authentication

Set by the operator, one of the two options above, because every search costs
a provider call against the operator's key and quota. The operator will want
at least rate limiting per identity. An operator could leave search open to
anyone, which is easier for the app and worse for the operator.

### Open questions

- **Content rating.** Providers filter by rating (`g`, `pg`, …); who sets it,
  the operator in the relay's configuration or the user per request? Probably
  the operator sets a ceiling and the app may ask for less.
- **Attribution.** Provider terms usually require a "powered by" mark in the
  picker. The relay should tell the app which provider it fronts
  (`GET /gifs/about`) so the app can show the right mark.
- **Proxying the bytes too.** The relay could also proxy the GIF itself, so
  that receivers' addresses never reach the provider either. Then
  `data.links` would point at the relay, every receiver's fetch would go
  through the operator (bandwidth), and the operator would see who fetched
  what — the storage service's position, without its encryption. Not for the
  first version; the tap-to-load setting covers the receiver who minds.
- **Provider URLs that expire.** Some providers' CDN links are not permanent.
  A GIF in a message a year old may be a dead link; the app shows the inline
  `preview` and a "GIF no longer available" note, which it needs for storage
  links anyway.
