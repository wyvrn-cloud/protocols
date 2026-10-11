---
title: DID Hosting
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/did-hosting/1.0
status: Proposed
summary: A host publishes a short, stable did:webvh (and its parallel did:web) for an agent under a name the agent picks. The agent writes and signs every version of its DID log; the host checks it, stores it and serves it, and cannot change it. Names are first come, first served, apart from ones the host's admins have set aside for a holder.
tags:
  - did
  - did-webvh
  - did-web
  - identity
  - naming
authors:
  - name: wyvrn
---

## Summary

An agent whose DID is a `did:peer:4` has an address that is hundreds of
characters long and changes whenever its keys do. That is a poor thing to put
in a profile, say aloud, or send in a text message. DID Hosting gives such an
agent a second, public DID that is short and does not change:

```
did:webvh:QmfGEUAcMpzo25kF2Rhn8L5FAXysfGnkzjwdKoNPi615XQ:id.example:alice
did:web:id.example:alice
```

The **holder** writes its own `did:webvh` log and signs every entry. The
**host** checks each entry, stores it, and serves it over HTTPS, together
with the parallel `did:web` the `did:webvh` specification derives from it. The
host holds no key of the holder's. It cannot change where the DID points or
read what is sent to it; the worst it can do is stop serving it, or go on
serving an old version.

A hosted DID is an address, not an invitation. Anyone given it can resolve it
and write to the agent behind it.

This protocol is authored by wyvrn and uses the `https://wyvrn.app/`
namespace. It may be proposed to didcomm.org once it has matured.

## Motivation

Two existing things come close and neither is this.

- [`shorten-url/1.0`](https://didcomm.org/shorten-url/1.0) has an agent ask
  another to shorten a URL, typically an out-of-band invitation. The short URL
  is a redirect the shortener controls: nothing about it can be verified, and
  whoever runs it can send it anywhere. It shortens one link; it does not
  give an agent an identifier.
- [`did:webvh`](https://identity.foundation/didwebvh/v1.0/) is exactly the
  identifier wanted: readable, resolvable over HTTPS, with a signed history
  the web server cannot forge. But it needs a web server, at a stable name,
  that the agent can write to. A phone has none.

So: let an agent that cannot host a file have one hosted, without giving the
host any say over what the file says.

Who this is for is people and services that are public on purpose: someone
with an audience, a community's server, an announcement channel. What they
publish here is what they would post on their own page anyway. It is equally
for a service that is reached through a mediator and so has no public
endpoint of its own to put a `did:web` at.

## Roles

- **host**: the agent that keeps the names, checks and stores DID logs, and
  serves them over HTTPS at its own domain. It discloses this protocol to
  `discover-features/2.0` with the role `host`.
- **holder**: an agent that has, or wants, a DID hosted. It is the DID's
  controller in every sense `did:webvh` means: it alone holds the keys that
  can sign the log.
- **admin**: a DID the host is configured to take naming decisions from. An
  admin decides who may claim a name that has been set aside. It never
  writes, signs or uploads anybody's DID log.

## Connectivity

Every message is between one agent and the host. The host MUST act only on
messages whose sender is authenticated (authcrypt), and answers the sender.

Reading a hosted DID is not part of this protocol: that is DID resolution,
over HTTPS, by anyone.

## Names

A hosted DID is `did:webvh:<SCID>:<host>:<name>`, where `<name>` is one or
more **labels** joined by `:`. The same name as a URL path, labels joined by
`/`, is where the host serves it.

| | |
|---|---|
| The DID | `did:webvh:<SCID>:id.example:alice` |
| Its log | `https://id.example/alice/did.jsonl` |
| Its parallel `did:web` | `did:web:id.example:alice`, at `https://id.example/alice/did.json` |
| Its whois | `https://id.example/alice/whois.vp` |

A label is 3 to 32 characters of `a`-`z`, `0`-`9` and `-`, not starting or
ending with `-` and with no `--`. Nothing else: no capitals, no other
scripts. Two names that look alike to a person are then two names that are
alike, which leaves no room for a look-alike of somebody else's.

A host decides how many labels a name may have. A first label can be a
**namespace** the host sets aside whole: `official:announcements`,
`official:support`.

### Free and reserved names

A name nobody holds is **free**: the first agent to publish a valid log under
it has it. That is the rule for every name, except:

- A host has a list of names, and of namespaces, that are **reserved**. A
  reserved name can be claimed only by the holder an admin has assigned it to
  (`assign`). Until then it can be claimed by nobody.
- A host SHOULD also refuse names that are unfit to be anyone's (the names of
  its own routes, slurs). To an agent these are simply reserved, and never
  assigned.

Reserving changes one thing: who may make the *first* publication under a
name. Once a DID is published there, it is its holder's like any other, and
is updated the same way by the same keys. An admin cannot edit it. An admin
can only `free` the name, which ends that DID's hosting, and assign the name
afresh.

### One name per holder

A host MUST refuse to publish a document any of whose keys is in a document
it hosts under another name. This is what "one DID per holder" comes to: a
holder is known by its keys. It does not stop someone making new keys to take
a second name. It does make each name cost a new identity, and it stops one
identity from collecting names.

## States

A name is in one of these states:

| State | Meaning |
|---|---|
| `free` | Nobody holds it. Anyone may claim it. |
| `reserved` | Set aside. Claimable only by the holder it is assigned to, if any. |
| `held` | An agent has asked for it and has a short time to publish. |
| `published` | A DID is hosted under it. |
| `stale` | Published, but its holder has not answered the host in the time the host allows. Still served. An admin may free it. |
| `deactivated` | Its holder has ended the DID (a `did:webvh` log entry with `deactivated`). Still served, as `did:webvh` requires, and not claimable until the host frees it. |

```
free ──reserve──▶ held ──publish──▶ published ──(no answer)──▶ stale
  ▲                 │                  │  ▲                      │
  └────(expires)────┘                  │  └──────(answers)───────┘
reserved ──assign + reserve──▶ held    └──publish (deactivated)──▶ deactivated
published / stale / deactivated ──free (admin)──▶ free or reserved
```

## Basic Walkthrough

Alice's app has an identity, `did:peer:4zQm…`, with one device.

1. **She picks a name.** The app sends `reserve` with `alice`. The host
   answers `reservation`: the name is `held` for her, and the DIDs it will
   become are `did:webvh:{SCID}:id.example:alice` and
   `did:web:id.example:alice`. Holding it first matters because of step 2.

2. **Her identity learns its public name.** The app adds
   `did:web:id.example:alice` to her `did:peer:4`'s `alsoKnownAs`. A
   `did:peer:4` is a hash of its own document, so this gives her a new
   `did:peer:4`: an ordinary DID rotation, which her contacts are told of the
   usual way. The `did:web` is used for this, not the `did:webvh`, because it
   is the one name that is known before the log exists; the `did:webvh`
   contains a hash of the log's first entry, which will in turn name the
   `did:peer:4`.

3. **She writes the log.** The app creates the first `did:webvh` log entry.
   Its document carries the same keys and service endpoints as her
   `did:peer:4`, and `alsoKnownAs` both the `did:web` and the `did:peer:4`.
   Its `updateKeys` are one key per trusted device.

4. **She publishes it.** The app sends `publish` with the entry attached and
   signed. The host checks it (see [Design By Contract](#design-by-contract))
   and answers `published`. The log is now at
   `https://id.example/alice/did.jsonl`, and the host has derived
   `did.json` beside it.

5. **Later, she adds a tablet.** Either device appends a log entry adding the
   tablet's keys to the document and its update key to `updateKeys`, updating
   `alsoKnownAs` for the new `did:peer:4`, and sends `publish` again. The
   `did:webvh` and the `did:web` have not changed. Nobody she gave them to
   needs to be told anything.

6. **She publishes who she is.** The app sends `publish-whois` with a signed
   presentation holding her profile credential
   ([below](#the-whois-profile)). It is served at
   `https://id.example/alice/whois.vp`.

Bob is given `did:web:id.example:alice`.

7. His app resolves it, finds a `did:webvh` in its `alsoKnownAs`, resolves
   and verifies that instead, and from then on knows Alice by the
   `did:webvh` (see [Resolving a hosted DID](#resolving-a-hosted-did)). It
   fetches her whois and shows her name and picture. Bob has not sent Alice
   anything yet.

## Design By Contract

### What a host checks before publishing

A `publish` is accepted only if all of this holds. The host MUST check it
again for every `publish`, against the whole log as it would then stand.

1. **The log is valid `did:webvh` 1.0.** The SCID, the entry hashes, and each
   entry's proof by a key the entry before it authorised, all verify.
2. **It continues what is hosted.** For a name already `published`, the
   entries sent follow the last hosted entry (`after`), and the log's SCID is
   the hosted one. A host never replaces a log, only extends it.
3. **The DID is the name.** The document's `id` is
   `did:webvh:<SCID>:<host>:<name>` for the name asked for.
4. **It names its other self.** The document's `alsoKnownAs` includes
   `did:web:<host>:<name>`.
5. **The sender holds its keys.** The key the message was authenticated with
   is a `keyAgreement` key of the resulting document, and the attachment
   carrying the log is signed (`jws`) by one of its `authentication` keys.
   For a name already `published` both keys MUST also be in the document as
   it stood before, or be an active update key of it: a stranger cannot
   append, even an entry that would be valid.
6. **Its keys are nobody else's.** No key of the resulting document is in a
   document hosted under another name.
7. **The name may be claimed by this sender.** For a first publication: the
   name is `held` for this sender. For a reserved name, that hold is given
   only to the assigned holder.

A host SHOULD require `portable: true` in the first entry, so that a holder
can later move the DID to another host and keep its history.

A host MAY refuse a log, or a whois, over a size it states in its
`problem-report`.

### Who a sender is

A hold, and an assignment, are to a DID. A holder's `did:peer:4` changes
between reserving and publishing (step 2 above), and again with every device
it adds. So a host matches a sender to a hold or an assignment **by key**:
the sender is that party if the key it authenticated with is a
`keyAgreement` key of the DID the hold or assignment names.

### Two devices at once

Two of a holder's devices can each append an entry to the same log at the
same moment. The host accepts the first. The second's `after` is no longer
the last entry, so it is refused with `conflict`, which says what the last
entry now is. That device fetches the log, rebuilds its change on top, and
publishes again.

### Staleness

A holder that never adds or removes a device never publishes again, so
silence in this protocol means nothing by itself. A host that wants to
know a name is still wanted asks: it sends a `trust-ping/2.0` to the hosted
DID, and any authenticated message from the holder afterwards (the ping's
response, or anything in this protocol) answers it.

A host states its own periods. wyvrn's host asks after a year without
hearing from a holder, and marks the name `stale` after a week without an
answer. `stale` changes nothing for anyone resolving the DID. It only makes
the name one an admin may `free`.

### Ending a DID

A holder ends its DID as `did:webvh` says to: a log entry with
`deactivated: true`, sent with `publish`. The host keeps serving the log, so
that the end is itself verifiable, and the name stays unclaimable until the
host frees it.

## Security

- **The host cannot forge.** Every entry is signed by a key the holder's
  earlier entries authorised, and the DID contains a hash of the first one.
  A host that served a different log would be serving a different DID.
- **The host can withhold.** It can stop serving a DID, or serve it as it
  was before the last few entries, and a resolver that has not seen the newer
  ones cannot tell. `did:webvh`'s witnesses and watchers are the answer to
  that; this protocol does not require them.
- **The `did:web` is only as good as the host.** A `did:web` has no history
  and no signature: it is whatever the host's HTTPS server says today. That
  is why a resolver moves from it to the `did:webvh` at once, and why the
  name being reassigned (below) is something a resolver has to notice.
- **A reassigned name is a different party under the same `did:web`.** If a
  name is freed and claimed afresh, `did:web:<host>:<name>` now resolves to
  a document whose `did:webvh` has a different SCID. An app that remembered
  the old `did:webvh` MUST treat the new one as someone else, and say so; it
  MUST NOT carry the old contact over. A host SHOULD leave a freed name
  unclaimable for long enough that links to its old holder have gone cold.
- **A name proves nothing about who holds it.** `alice` is whoever asked
  first. What an app may conclude about a holder comes from elsewhere: see
  [Marks of authenticity](#marks-of-authenticity).
- **Admins decide names, not contents.** Nothing an admin can send puts a
  key, an endpoint or a profile into anyone's DID.
- **Everything published is public**, to everyone, including the fact that
  these keys and this `did:peer:4` are the same party as this name. An agent
  SHOULD make sure the person knows that before publishing.
- **The host learns who resolves.** Fetching a log or a whois tells the host
  the fetcher's IP address. An app MAY resolve through a proxy.

## Resolving a hosted DID

Given a `did:web`:

1. Resolve it. If its `alsoKnownAs` names a `did:webvh` at the same host and
   path, resolve that, verifying its log.
2. Accept the pair only if the `did:webvh` document's `alsoKnownAs` names the
   `did:web` back. If it does not, or the log does not verify, the `did:web`
   stands alone and is trusted no further than any `did:web`.
3. From then on, know the party by the `did:webvh`. Keep it. If the `did:web`
   is later seen to lead to a `did:webvh` with another SCID, that is another
   party.

Given a `did:webvh`, resolve it. Its `alsoKnownAs` MAY name a `did:peer:4`.
A message whose sender is that `did:peer:4` is from the holder if the
`did:peer:4`'s own document (which it carries) lists the `did:web` in its
`alsoKnownAs` and shares a `keyAgreement` key with the `did:webvh` document.
That closes the circle: `did:peer:4` → `did:web` → `did:webvh` →
`did:peer:4`.

A hosted DID is shared as itself, or in a link an app opens:
`https://<app>/dl/<did>`.

## The whois profile

A holder says who it is the way `did:webvh` provides for: a file,
`whois.vp`, served beside the log, which is a
[Linked Verifiable Presentation](https://identity.foundation/linked-vp/). It
is the `#whois` service of the DID, implicitly for the `did:webvh`; the host
adds the same service explicitly to the parallel `did:web`, as the
`did:webvh` specification says to.

The presentation's `holder` is the hosted DID and it is signed by one of the
DID's `authentication` keys. An app MUST verify that, and MUST ignore any
credential in it whose `credentialSubject.id` is not the hosted DID.

### The profile credential

One credential in the presentation is the profile: issued by the hosted DID
about itself. Nothing in it is anything but the holder's own word.

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://wyvrn.app/ns/profile/v1"
  ],
  "type": ["VerifiableCredential", "ProfileCredential"],
  "issuer": "did:webvh:QmfGEU…:id.example:alice",
  "validFrom": "2026-10-11T00:00:00Z",
  "credentialSubject": {
    "id": "did:webvh:QmfGEU…:id.example:alice",
    "type": "Person",
    "name": "Alice",
    "description": "Writes about gardens.",
    "image": {
      "type": "ImageObject",
      "contentUrl": "data:image/webp;base64,UklGR…",
      "encodingFormat": "image/webp",
      "width": 256,
      "height": 256
    },
    "brand": {
      "type": "Brand",
      "image": {
        "type": "ImageObject",
        "contentUrl": "https://alice.example/banner.webp",
        "encodingFormat": "image/webp",
        "width": 1500,
        "height": 500,
        "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
      }
    },
    "wyvrn": {
      "background": {
        "type": "ImageObject",
        "contentUrl": "https://alice.example/background.webp",
        "encodingFormat": "image/webp",
        "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
      }
    }
  },
  "proof": { "…": "…" }
}
```

| Field | Vocabulary | Meaning |
|---|---|---|
| `type` | schema.org `Person` or `Organization` | What kind of party this is. |
| `name` | schema.org `name` | The display name. |
| `description` | schema.org `description` | A line or two about them. |
| `image` | schema.org `image`, an `ImageObject` | The profile picture: small and square. |
| `brand.logo` | schema.org `Brand` → `logo` | Optional, for an `Organization`: its logo, where that differs from `image`. |
| `brand.image` | schema.org `Brand` → `image` | The banner: wide, shown across the top of a profile. |
| `wyvrn.background` | `https://wyvrn.app/ns/profile/v1#background` | The background: shown behind a profile or a conversation. |

`name`, `description` and `image` are all an app needs to show someone in a
list. All of it is optional.

**Images.** Each is a schema.org `ImageObject`, whose `contentUrl` is where
the picture is.

- The profile picture SHOULD be a `data:` URL, so that showing it fetches
  nothing more. A host MAY limit its size; wyvrn's allows 64 KB.
- A larger picture MAY be an `https:` URL instead. It then MUST carry
  `sha256`, the hex SHA-256 of the file, and an app MUST discard a file that
  does not match. An app SHOULD NOT fetch such a picture before the person
  has asked to see the profile: fetching tells the picture's host who is
  looking.

**The one term that is wyvrn's.** schema.org has nothing that means "the
picture behind a profile". Rather than bend a term that means something else,
there is one new one, kept apart under `wyvrn` so that it is plain which part
of a profile is not schema.org. `wyvrn` is a JSON-LD `@nest`: a grouping in
the JSON, not a thing in the data. To a JSON-LD processor `background` is a
property of the subject like the rest.

The context is at <https://wyvrn.app/ns/profile/v1>, and in this repository at
[`contexts/profile/v1.jsonld`](../../../contexts/profile/v1.jsonld). It does
not change once published: a change is a `v2`. An app MUST use its own copy
and MUST NOT fetch it to verify a credential, as with any JSON-LD context a
signature depends on.

### Marks of authenticity

A profile is self-asserted. An app SHOULD show the DID's host and name
beside it, always. More than that needs one of:

- **A linked domain.** The holder's document has a `LinkedDomains` service
  naming an origin, and that origin serves a
  [DID Configuration](https://identity.foundation/well-known-did-configuration/)
  naming the DID back. An app that has checked both MAY show the domain as
  the holder's. Checking contacts the domain, so an app SHOULD do it when
  asked rather than unasked; it SHOULD remember the result, with when it was
  checked, and check again when the DID's document changes or after a period
  of its choosing.
- **A namespace the app knows.** An app MAY treat a namespace at a host it
  knows as a mark by itself: wyvrn's apps mark names under
  `id.wyvrn.app:official`, which that host reserves whole. A DID marked this
  way SHOULD have a linked domain as well, so that the mark does not rest on
  one check.

## Message Reference

All messages use the type prefix `https://wyvrn.app/did-hosting/1.0/`. Each has
a JSON Schema under [`schemas/`](schemas), which the examples here are checked
against.

### `reserve`

Holder to host. Asks for a name to be held.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name wanted, labels joined by `:`. |

The host answers with `reservation`, or a `problem-report`. A sender has at
most one hold; a new `reserve` replaces it.

```json
{
  "id": "7c1f0a52-0d2e-4a3b-9a57-5a8d4f1c2e10",
  "type": "https://wyvrn.app/did-hosting/1.0/reserve",
  "body": {
    "name": "alice"
  }
}
```

### `reservation`

Host to holder.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. |
| `host` | string | The host part of the DIDs, as it appears in them (`id.example`, or `id.example%3A8443`). |
| `did_web` | string | The parallel `did:web` this name will have: `did:web:<host>:<name>`. |
| `expires_time` | integer | When the hold lapses, in seconds since the epoch. |

The `did:webvh` is not here: it does not exist until the holder has written
the log.

```json
{
  "id": "b0a6f6b1-34c7-4d0e-8f43-0d7a1f0e9c11",
  "type": "https://wyvrn.app/did-hosting/1.0/reservation",
  "thid": "7c1f0a52-0d2e-4a3b-9a57-5a8d4f1c2e10",
  "body": {
    "name": "alice",
    "host": "id.example",
    "did_web": "did:web:id.example:alice",
    "expires_time": 1791727200
  }
}
```

### `publish`

Holder to host. Publishes a DID under a held name, or appends to one already
published.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. |
| `after` | string | Optional. The `versionId` of the hosted entry that the attached entries follow. Absent for a first publication. |

One attachment, `id` `log`, `media_type` `text/jsonl`: the log entries being
added, one per line, oldest first. For a first publication that is the whole
log. Its `data` has `base64` and `jws`: a detached signature over the
attachment's bytes by an `authentication` key of the document the newest
entry gives.

```json
{
  "id": "2f9d7a43-6f1b-4a8e-b0b3-91f3f6f0a212",
  "type": "https://wyvrn.app/did-hosting/1.0/publish",
  "body": {
    "name": "alice"
  },
  "attachments": [
    {
      "id": "log",
      "media_type": "text/jsonl",
      "data": {
        "base64": "eyJ2ZXJzaW9uSWQiOiIxLVFtLi4uIn0K",
        "jws": {
          "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6IiNrZXktMSJ9",
          "signature": "c2lnbmF0dXJl"
        }
      }
    }
  ]
}
```

### `published`

Host to holder.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. |
| `did` | string | The hosted `did:webvh`. |
| `did_web` | string | Its parallel `did:web`. |
| `version_id` | string | The `versionId` of the last entry now hosted. |

```json
{
  "id": "5d0c8e7a-93b2-4a70-8f0e-63a0f4d2b313",
  "type": "https://wyvrn.app/did-hosting/1.0/published",
  "thid": "2f9d7a43-6f1b-4a8e-b0b3-91f3f6f0a212",
  "body": {
    "name": "alice",
    "did": "did:webvh:QmfGEUAcMpzo25kF2Rhn8L5FAXysfGnkzjwdKoNPi615XQ:id.example:alice",
    "did_web": "did:web:id.example:alice",
    "version_id": "1-QmQq6Kg4ZZ1p49znzxnWmes4LkkWgMWLrnrfPre8UD56bz"
  }
}
```

### `publish-whois`

Holder to host. Sets, or with no attachment removes, the DID's `whois.vp`.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. |

One attachment, `id` `whois`, `media_type` `application/vp`, `data.base64`.
The host MUST check that the presentation's `holder` is the hosted DID, that
its proof verifies against the hosted document, and that every credential in
it is about the hosted DID. It answers `status`.

```json
{
  "id": "a8e3c1d9-0b5f-4c2a-9d6e-7b1f2c3d4e14",
  "type": "https://wyvrn.app/did-hosting/1.0/publish-whois",
  "body": {
    "name": "alice"
  },
  "attachments": [
    {
      "id": "whois",
      "media_type": "application/vp",
      "data": {
        "base64": "eyJAY29udGV4dCI6Wy4uLl19"
      }
    }
  ]
}
```

### `status-request`

Anyone to host.

| Field | Type | Description |
|---|---|---|
| `name` | string | Optional. Absent, the host answers for the name the sender holds, if any. |

```json
{
  "id": "c4b7a2e1-5d6f-4e3b-8a9c-0d1e2f3a4b15",
  "type": "https://wyvrn.app/did-hosting/1.0/status-request",
  "body": {
    "name": "alice"
  }
}
```

### `status`

Host to anyone.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. Absent if none was asked for and the sender holds none. |
| `state` | string | `free`, `reserved`, `held`, `published`, `stale` or `deactivated`. |
| `did` | string | The hosted `did:webvh`, when there is one. |
| `version_id` | string | The last hosted entry's `versionId`, when there is one. |
| `whois` | boolean | Whether a whois is published. |
| `yours` | boolean | Whether the sender is the holder (or the one it is held for or assigned to). |

A host MUST NOT say to anyone but an admin who a reserved name is assigned
to, or who holds a hold.

```json
{
  "id": "e6d5c4b3-a291-4807-b6c5-d4e3f2a1b016",
  "type": "https://wyvrn.app/did-hosting/1.0/status",
  "thid": "c4b7a2e1-5d6f-4e3b-8a9c-0d1e2f3a4b15",
  "body": {
    "name": "alice",
    "state": "published",
    "did": "did:webvh:QmfGEUAcMpzo25kF2Rhn8L5FAXysfGnkzjwdKoNPi615XQ:id.example:alice",
    "version_id": "1-QmQq6Kg4ZZ1p49znzxnWmes4LkkWgMWLrnrfPre8UD56bz",
    "whois": true,
    "yours": false
  }
}
```

### `assign`

Admin to host. Says who may claim a reserved name, or reserves a free one.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name, or a namespace followed by `:*`. |
| `holder` | string or null | The DID that may claim it. `null` reserves it for nobody. Not allowed with a namespace. |

Refused for a name that is `published`, `stale` or `deactivated`: `free` it
first. The host answers `status`.

```json
{
  "id": "f1e2d3c4-b5a6-4978-8695-a4b3c2d1e017",
  "type": "https://wyvrn.app/did-hosting/1.0/assign",
  "body": {
    "name": "official:announcements",
    "holder": "did:peer:4zQmd8CpeFPci817KDsbSAKWcXAE2mjvCQSasRewvbSF54Bd"
  }
}
```

### `free`

Admin to host. Ends the hosting of whatever DID is under a name, and makes
the name claimable again: `free`, or `reserved` if it is on the host's list.

| Field | Type | Description |
|---|---|---|
| `name` | string | The name. |
| `comment` | string | Optional. Why, for the host's own record. |

The host stops serving the log, the `did.json` and the whois. It answers
`status`.

```json
{
  "id": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c18",
  "type": "https://wyvrn.app/did-hosting/1.0/free",
  "body": {
    "name": "alice",
    "comment": "Holder unreachable since 2025-10."
  }
}
```

### `problem-report`

A standard [`report-problem/2.0`](https://didcomm.org/report-problem/2.0)
message, its `pthid` the id of the message it refuses.

| Code | Meaning |
|---|---|
| `e.p.msg.name-invalid` | The name is not well formed, or has more labels than the host allows. |
| `e.p.msg.name-taken` | The name is published, or held for someone else. |
| `e.p.msg.name-reserved` | The name is reserved and the sender is not who it is assigned to. |
| `e.p.msg.not-held` | A first `publish` under a name not held for the sender. |
| `e.p.msg.not-holder` | A `publish` or `publish-whois` for a DID the sender does not hold. |
| `e.p.msg.log-invalid` | The log, or the document it gives, fails a check in "What a host checks before publishing". `comment` says which. |
| `e.p.msg.conflict` | `after` is not the last hosted entry. `args` carries its `versionId`. |
| `e.p.msg.key-in-use` | A key of the document is in a document hosted under another name. |
| `e.p.msg.whois-invalid` | The presentation fails a check. |
| `e.p.msg.too-large` | Over a limit. `args` carries the limit, in bytes. |
| `e.p.msg.not-admin` | `assign` or `free` from a DID that is not an admin. |

## Implementations

| Name / Link | Implementation Notes |
|---|---|
| | None yet. |

## Endnotes

### Future Considerations

- **Hosting the larger pictures.** A banner or a background has to live
  somewhere, and the natural place is beside the log, where `did:webvh`'s
  `#files` service would make each a DID URL (`<did>/banner.webp`). That is
  file hosting, with its own limits and abuse, and is left to a protocol for
  files.
- **Witnesses and watchers**, so that a host withholding entries is caught.
- **Moving to another host.** `portable` makes it possible in `did:webvh`;
  what the old host then serves (a pointer to the new location), and for how
  long, is not said here.
- **Recovery.** A holder that loses every trusted device can never update
  its DID again. Today that ends as `stale` and an admin's `free`. A recovery
  key kept offline, listed in `updateKeys`, would be a way back that needs
  nothing from the host.
