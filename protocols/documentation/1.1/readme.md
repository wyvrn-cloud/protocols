---
title: Documentation
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/documentation/1.1
status: Proposed
summary: Lets an agent ask a documentation registry, over DIDComm, for the definition of a DIDComm v1 or v2 protocol (metadata, prose sections, example messages and JSON Schemas per message type) or for a section of the DIDComm Messaging specification or one of its extensions, so software and AI agents can learn a protocol at the moment they need it.
tags:
  - documentation
  - discovery
  - schemas
authors:
  - name: wyvrn
---

## Summary

Documentation lets a `requester` fetch a protocol's definition, or a section of the
DIDComm Messaging specification, from a `registry` agent at the moment it needs it.

A registry is an ordinary DIDComm agent that indexes protocol definitions: those in
the [didcomm.org](https://didcomm.org) registry's format (a `readme.md` with YAML
frontmatter, prose sections and example messages), and any other source it knows how to
read, such as the [Aries RFCs](https://github.com/hyperledger/aries-rfcs) that define
most DIDComm v1 protocols. It adds JSON Schemas where it has them. Requesters can:

- search what the registry knows (`query` → `catalog`)
- fetch one protocol's definition (`request` → `response`)
- fetch part of a document: the DIDComm Messaging specification, in any version the
  registry serves, or one of its extensions (`spec-request` → `spec-response`)

### Changes from 1.0

All additive; a 1.1 registry SHOULD keep answering 1.0 requests as 1.0 did.

- **DIDComm versions.** Catalog entries, responses, message types and documents say
  which DIDComm Messaging versions they apply to (`didcomm_versions`, as semantic-version
  requirements like `^1.0` or `^2.0`), and `query` can filter on it.
- **One schema per envelope style.** A message type used with both DIDComm v1 and v2
  (they shape plaintext differently) can have a schema for each, in `schemas`.
- **Aliases.** Responses list the other PIURIs a protocol is known by, and requests
  accept them.
- **Documents.** `spec-request` takes a `document` (default: the specification), and
  the table of contents lists every document the registry serves.
- **Attachment formats.** For a protocol whose messages carry attachments in registered
  formats (issue-credential and present-proof carry credentials, requests and proofs
  this way), a response can list those formats in `attachment_formats`, with a JSON
  Schema for each attachment's content in each message that carries it.

## Motivation

[Discover Features 2.0](https://didcomm.org/discover-features/2.0) tells an agent
*which* protocols a peer supports. It doesn't say what those protocols' messages look
like. An agent that meets a protocol it wasn't built for, most notably an AI agent
deciding at runtime how to talk to a peer, has no standard way to find out. It can't
learn the message types, the required fields, or the order the messages go in.

The didcomm.org website answers that for humans. This protocol makes the same
information available to software, over the same secure channel the agent already
uses, and in a structured form. Requesters get a protocol's message types, examples and
schemas, and only the prose sections they ask for, without scraping HTML. Keeping the
response small matters most for AI agents, whose context windows are limited.

## Roles

- `requester`: asks for documentation.
- `registry`: answers with documentation from the sources it indexes.

An agent advertising the `registry` role through Discover Features 2.0 SHOULD answer
all three request messages defined here.

## Connectivity

Every interaction is a single request and reply between the two parties. A requester
with no inbound endpoint of its own (for example a local AI tool, or an agent whose
mediator it does not want to involve) SHOULD set the
[`return_route`](https://github.com/decentralized-identity/didcomm-messaging/blob/main/extensions/return_route/main.md)
header to `all` so the reply comes back on the same connection. A registry SHOULD
support `return_route`.

## States

Each exchange follows the predefined request~response state machines, with no state
that outlives the exchange.

| Role | States |
|---|---|
| `requester` | `start` → `awaiting-reply` → `done` (on the reply or a `problem-report`) |
| `registry` | `start` → `done` (after sending the reply or a `problem-report`) |

## Basic Walkthrough

An AI agent has learned via Discover Features that Bob supports
`https://didcomm.org/coordinate-mediation/3.0`, and wants to know how to use it.

1. It asks the registry for that protocol's message types and the one prose section it
   needs, with schemas:
   ```json
   {
     "id": "5c6f8e2a-7d43-4a8e-9b1e-0f4f2c3d1a10",
     "type": "https://wyvrn.app/documentation/1.1/request",
     "from": "did:example:requester",
     "to": ["did:example:registry"],
     "created_time": 1790889239,
     "return_route": "all",
     "body": {
       "piuri": "https://didcomm.org/coordinate-mediation/3.0",
       "sections": ["basic-walkthrough"]
     }
   }
   ```
2. The registry replies with metadata, the one requested section, and every message
   type it found, each with its examples and JSON Schema (trimmed here):
   ```json
   {
     "id": "0b6d4f0e-1e2a-4c55-8f7d-6a7c9e3b2d11",
     "type": "https://wyvrn.app/documentation/1.1/response",
     "thid": "5c6f8e2a-7d43-4a8e-9b1e-0f4f2c3d1a10",
     "from": "did:example:registry",
     "to": ["did:example:requester"],
     "created_time": 1790889240,
     "body": {
       "piuri": "https://didcomm.org/coordinate-mediation/3.0",
       "title": "Coordinate Mediation",
       "status": "Production",
       "didcomm_versions": ["^2.0"],
       "summary": "A protocol to coordinate mediation configuration between a mediating agent and the recipient.",
       "roles": ["mediator", "recipient"],
       "source": {
         "name": "didcomm.org",
         "path": "site/content/protocols/coordinate-mediation/3.0/readme.md",
         "revision": "4f1c2b9"
       },
       "available_sections": [
         {"id": "roles", "title": "Roles", "level": 2},
         {"id": "basic-walkthrough", "title": "Basic Walkthrough", "level": 2},
         {"id": "message-reference", "title": "Message Reference", "level": 2}
       ],
       "sections": [
         {
           "id": "basic-walkthrough",
           "title": "Basic Walkthrough",
           "markdown": "A `recipient` may discover an agent capable of routing ..."
         }
       ],
       "messages": [
         {
           "type": "https://didcomm.org/coordinate-mediation/3.0/mediate-request",
           "didcomm_versions": ["^2.0"],
           "examples": [
             {"id": "123456780", "type": "https://didcomm.org/coordinate-mediation/3.0/mediate-request"}
           ],
           "schema": {
             "$schema": "https://json-schema.org/draft/2020-12/schema",
             "title": "coordinate-mediation/3.0 mediate-request",
             "type": "object",
             "required": ["id", "type"],
             "properties": {
               "id": {"type": "string"},
               "type": {"const": "https://didcomm.org/coordinate-mediation/3.0/mediate-request"}
             }
           },
           "schemas": [
             {"didcomm_versions": ["^2.0"], "schema": {"title": "coordinate-mediation/3.0 mediate-request", "...": "as above"}}
           ]
         }
       ]
     }
   }
   ```
3. If it doesn't yet know which protocol it needs, the requester can search first:
   ```json
   {
     "id": "a3f0c1d2-2b4e-4f6a-8c9d-0e1f2a3b4c5d",
     "type": "https://wyvrn.app/documentation/1.1/query",
     "from": "did:example:requester",
     "to": ["did:example:registry"],
     "return_route": "all",
     "body": {
       "match": "https://didcomm.org/*",
       "text": "mediat",
       "status": ["Production"],
       "didcomm_version": "2.1"
     }
   }
   ```
   ```json
   {
     "id": "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f70",
     "type": "https://wyvrn.app/documentation/1.1/catalog",
     "thid": "a3f0c1d2-2b4e-4f6a-8c9d-0e1f2a3b4c5d",
     "body": {
       "total": 1,
       "offset": 0,
       "entries": [
         {
           "piuri": "https://didcomm.org/coordinate-mediation/3.0",
           "title": "Coordinate Mediation",
           "status": "Production",
           "summary": "A protocol to coordinate mediation configuration between a mediating agent and the recipient.",
           "tags": [],
           "has_schemas": true,
           "didcomm_versions": ["^2.0"]
         }
       ]
     }
   }
   ```
4. Documents work the same way. The default document is the DIDComm Messaging
   specification; without `section`, the registry returns the table of contents and
   the list of documents it serves:
   ```json
   {
     "id": "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f",
     "type": "https://wyvrn.app/documentation/1.1/spec-request",
     "return_route": "all",
     "body": {"version": "2.1"}
   }
   ```
   ```json
   {
     "id": "b7c8d9e0-f1a2-4b3c-8d4e-5f6a7b8c9d0e",
     "type": "https://wyvrn.app/documentation/1.1/spec-response",
     "thid": "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f",
     "body": {
       "document": "spec",
       "version": "2.1",
       "title": "DIDComm Messaging Specification v2.1",
       "didcomm_versions": ["~2.1"],
       "toc": [
         {"id": "message-headers", "title": "Message Headers", "level": 3}
       ],
       "documents": [
         {"id": "spec", "title": "DIDComm Messaging Specification", "versions": ["2.1", "2.0", "1.0", "editors-draft"]},
         {"id": "extension/l10n", "title": "DIDComm L10n Extension", "versions": ["current"], "didcomm_versions": ["^2.0"]}
       ]
     }
   }
   ```
   Then one section of one document:
   ```json
   {
     "id": "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
     "type": "https://wyvrn.app/documentation/1.1/spec-request",
     "return_route": "all",
     "body": {"document": "extension/l10n", "section": "scope"}
   }
   ```
   ```json
   {
     "id": "f6a7b8c9-d0e1-4f2a-9b3c-4d5e6f7a8b9c",
     "type": "https://wyvrn.app/documentation/1.1/spec-response",
     "thid": "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
     "body": {
       "document": "extension/l10n",
       "version": "current",
       "title": "DIDComm L10n Extension",
       "didcomm_versions": ["^2.0"],
       "section": {
         "id": "scope",
         "title": "Scope",
         "markdown": "DIDComm's `lang` and `accept-lang` headers cover most localization needs. ..."
       }
     }
   }
   ```

## Design By Contract

- **Protocols are identified by PIURI, never by file path.** A registry indexes each
  definition under the `piuri` in its frontmatter. Where a source's folder layout
  disagrees with that value, the frontmatter wins. For sources without frontmatter
  (Aries RFCs), the registry maintains the mapping from document to PIURI.
- **Aliases.** A protocol can be known by more than one PIURI: DIDComm v1 message types
  began with `did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/`, now equivalent to
  `https://didcomm.org/` ([Aries RFC 0348](https://github.com/hyperledger/aries-rfcs/tree/main/features/0348-transition-msg-type-to-https)),
  and some protocols were published under an underscore spelling (`trust_ping/1.0`).
  A registry MUST accept any alias it lists wherever a PIURI is accepted, and MUST answer
  with the PIURI it indexes the protocol under.
- **Duplicates.** When two sources define the same PIURI (didcomm.org's page that only
  links to an Aries RFC, and the RFC itself), the registry returns the more complete
  definition and names it in `source`.
- **Message type URIs are accepted wherever a PIURI is.** A registry receiving
  `https://didcomm.org/basicmessage/2.0/message` as a `piuri` MUST treat it as
  `https://didcomm.org/basicmessage/2.0`.
- **Minor versions.** If the exact version requested is unknown, a registry MAY answer
  with the highest minor version it has under the same major version, in keeping with
  DIDComm's semver rules. The `piuri` in the `response` is always the version actually
  returned, so requesters MUST check it. A registry MUST NOT substitute a different
  major version.
- **Matching** in `query.match` follows Discover Features 2.0: `*` matches any run of
  characters, and a `match` of just `*` matches everything. `text` is a
  case-insensitive substring match against title, summary and tags. All filters given
  must match.
- **Section ids** are the section heading in lower kebab-case, keeping only ASCII
  letters and digits (`Basic Walkthrough` → `basic-walkthrough`, `` `query` Message
  Type `` → `query-message-type`). A section includes its subsections. A heading that repeats gets `-2`, `-3`, … in document order.
  Every `response` lists `available_sections`, so a requester can always discover valid
  ids. The same rule applies to `spec-response` section ids.
- **DIDComm versions.** `didcomm_versions` is a list of
  [semantic-version requirements](https://docs.rs/semver/latest/semver/struct.VersionReq.html)
  in Cargo/npm syntax (`^1.0` = any 1.x, `^2.0` = any 2.x, `~2.1` = 2.1 only,
  `>=2.0, <3.0`), satisfied if any item is. DIDComm v1 is version `1.0`; v2 is `2.0` and
  `2.1`. A protocol's list is the union of its message types' lists. A registry that
  can't tell which envelope style a message type is used with omits the field rather than
  guessing. `query.didcomm_version` is a version, not a requirement: it keeps entries
  whose `didcomm_versions` it satisfies, and drops entries without the field.
- **Schemas** are [JSON Schema 2020-12](https://json-schema.org/draft/2020-12) documents
  that each validate one complete plaintext message (headers and body), not just its
  body. A DIDComm v2 schema pins `type` with `const` and covers `body`; a DIDComm v1
  schema pins `@type` (with `enum` when it accepts aliases) and covers the top-level
  fields and decorators (`~thread`, `~l10n`, ...). `schemas` lists every schema a
  registry has for a message type with the DIDComm versions each applies to; `schema`
  repeats the one for the newest version, for 1.0 requesters. A message type with no
  known schema is still listed under `messages` with its examples. Schemas SHOULD NOT
  forbid unknown properties, since DIDComm requires recipients to ignore fields they do
  not understand.
- **Examples** are returned as the source wrote them, apart from being parsed as JSON.
  They are illustrative and MAY not validate against the schema. DIDComm v1-style
  examples (`@type` instead of `type`) are grouped under their `@type`, with legacy
  prefixes normalized.
- **Status** is the source's own lifecycle term: didcomm.org uses `Production`,
  `Demonstrated`, `Proposed`, `Draft`; Aries RFCs use `Adopted`, `Accepted`,
  `Demonstrated`, `Proposed`, `Stalled`, `Retired`. `query.status` matches it
  case-insensitively.
- **Documents.** `spec-request.document` names what to read: `spec` (the default) is
  the DIDComm Messaging specification, whose `version`s are those the registry serves
  (DIDComm v1, version `1.0`, has no single specification; a registry MAY serve the Aries
  RFCs that define it as `spec` version `1.0`). Other ids, such as `extension/l10n`, are
  documents the registry lists in `documents`. A document without versions of its own
  has the single version `current`. Every table of contents reply lists `documents`.
- **Untrusted content.** Everything in a reply is text written by third parties, which
  the registry passes along. A requester MUST treat it as data, not instructions (see
  Security).

| Problem code | When |
|---|---|
| `e.p.not-found.protocol` | No definition is indexed for the requested `piuri` (or its major version). `args`: `[piuri]`. |
| `e.p.not-found.section` | A requested section id does not exist. `args`: `[section-id]`. |
| `e.p.not-found.document` | The registry does not serve the requested `document`. `args`: `[document]`. |
| `e.p.not-found.spec-version` | The registry does not serve the requested `version` of the document. `args`: `[version]`. |
| `e.p.msg.invalid` | The request body does not match the request's schema. |

Problem reports follow [Report Problem 2.0](https://didcomm.org/report-problem/2.0),
with `pthid` set to the request's thread id.

## Security

- **Registry authenticity.** Requesters SHOULD use authcrypt replies (or verify the
  registry's DID by other means), so they know which registry they're trusting.
  Documentation from an unknown registry is no more trustworthy than a random web page.
- **Prompt injection.** Protocol documentation is free text written by third parties.
  An AI requester could be manipulated by instructions planted in it. Requesters that
  put registry content into a language model's context MUST present it as untrusted
  data, clearly separated from the instructions the model acts on.
- **Source integrity.** `source.revision` identifies the exact version of the
  documentation, so a requester can cache it or compare it with the upstream source.
- **Privacy.** A registry learns which protocols a requester is interested in, which
  can hint at what the requester is about to do and with whom. A requester that cares
  SHOULD query from a fresh DID used for nothing else (a peer DID costs nothing), as the
  DIDComm spec recommends for anonymous senders. Anoncrypt doesn't help here: the
  registry needs a key of the requester's to encrypt its reply to.
- **Denial of service.** Full protocol definitions can be tens of kilobytes. Requesters
  SHOULD use `sections` to ask for only what they need. Registries MAY limit `query`
  page size and SHOULD cap `limit`.

## Message Reference

Every message's JSON Schema is in [`schemas/`](schemas/), one file per message type.

### query

`https://wyvrn.app/documentation/1.1/query`. Requester → registry. Searches the
registry's catalog. All body fields are optional; an empty body lists everything.

| Field | Type | Meaning |
|---|---|---|
| `match` | string | PIURI pattern, Discover Features 2.0 wildcard rules. |
| `text` | string | Case-insensitive substring searched in title, summary and tags. |
| `status` | string[] | Keep entries whose status is one of these (e.g. `Production`). |
| `tags` | string[] | Keep entries carrying at least one of these tags. |
| `didcomm_version` | string | Keep entries usable with this DIDComm version (e.g. `1.0`, `2.1`). |
| `limit` | integer ≥ 1 | Page size. The registry MAY cap it. |
| `offset` | integer ≥ 0 | Entries to skip. Default `0`. |

### catalog

`https://wyvrn.app/documentation/1.1/catalog`. Registry → requester, `thid` = the
query's id.

| Field | Type | Meaning |
|---|---|---|
| `entries` | object[] | REQUIRED. Each has `piuri`, `title`, `status` (REQUIRED) and `summary`, `tags`, `has_schemas`, `didcomm_versions`, `aliases`. |
| `total` | integer | REQUIRED. Number of matches across all pages. |
| `offset` | integer | REQUIRED. Offset of the first entry in this page. |

### request

`https://wyvrn.app/documentation/1.1/request`. Requester → registry.

| Field | Type | Meaning |
|---|---|---|
| `piuri` | string | REQUIRED. PIURI, an alias, or a message type URI. |
| `sections` | string[] | Section ids to include. Omitted = all sections; `[]` = none. |
| `messages` | boolean | Include `messages` (examples and schemas). Default `true`. |

### response

`https://wyvrn.app/documentation/1.1/response`. Registry → requester, `thid` = the
request's id.

| Field | Type | Meaning |
|---|---|---|
| `piuri` | string | REQUIRED. The PIURI actually returned (see minor versions). |
| `title`, `status` | string | REQUIRED. From frontmatter. |
| `didcomm_versions` | string[] | DIDComm versions the protocol is used with. |
| `aliases` | string[] | Other PIURIs it is known by. |
| `summary`, `publisher`, `license` | string | From frontmatter. |
| `tags` | string[] | From frontmatter. |
| `authors` | object[] | From frontmatter (`name`, optional `email`). |
| `roles` | string[] | Role names, when the registry can determine them. |
| `source` | object | `name` (REQUIRED), `path`, `revision`, `url`: where the definition came from. |
| `available_sections` | object[] | REQUIRED. Every section's `id`, `title` and heading `level` (1-6), in document order. |
| `sections` | object[] | The requested sections: `id`, `title`, `markdown`. |
| `messages` | object[] | Present unless `messages: false` was requested. Each has `type` (REQUIRED), `didcomm_versions`, `examples` (array of objects), `schemas` (every known JSON Schema, each with its `didcomm_versions`), and `schema` (the newest of those). |
| `attachment_formats` | object[] | OPTIONAL; only with `messages`. The attachment formats the registry knows this protocol's messages to carry. Each has `format` (REQUIRED: the identifier a message names it by, in `formats[].format` for DIDComm v1 or an attachment's `format` for v2, e.g. `anoncreds/credential-offer@v1.0`), `title`, `documentation` (`document` and `section`, to read with `spec-request`), and `uses` (REQUIRED): per message type that carries it, `message` (REQUIRED, the type URI), `attachment` (DIDComm v1: the decorator it goes in, e.g. `offers~attach`), and `schema`: a JSON Schema 2020-12 for the attachment's content -- the JSON in `data.json`, or decoded from `data.base64`. One format can have different content in different messages. |

A response for issue-credential 2.0 (DIDComm v1) listing one of its attachment formats
(sections and most messages left out):

```json
{
  "type": "https://wyvrn.app/documentation/1.1/response",
  "id": "5c0d1e8a-2b9f-4c51-9a07-3e4f1b2c6d80",
  "thid": "0f8e7d6c-5b4a-4392-8170-6e5d4c3b2a19",
  "body": {
    "piuri": "https://didcomm.org/issue-credential/2.0",
    "title": "Issue Credential Protocol 2.0",
    "status": "Adopted",
    "didcomm_versions": ["^1.0"],
    "available_sections": [{"id": "summary", "title": "Summary", "level": 2}],
    "sections": [],
    "messages": [{"type": "https://didcomm.org/issue-credential/2.0/offer-credential", "didcomm_versions": ["^1.0"], "examples": []}],
    "attachment_formats": [{
      "format": "anoncreds/credential-offer@v1.0",
      "title": "AnonCreds credential offer",
      "documentation": {"document": "aries/attachment-formats", "section": "rfc0771"},
      "uses": [{
        "message": "https://didcomm.org/issue-credential/2.0/offer-credential",
        "attachment": "offers~attach",
        "schema": {
          "$schema": "https://json-schema.org/draft/2020-12/schema",
          "type": "object",
          "required": ["schema_id", "cred_def_id", "nonce", "key_correctness_proof"]
        }
      }]
    }]
  }
}
```

### spec-request

`https://wyvrn.app/documentation/1.1/spec-request`. Requester → registry.

| Field | Type | Meaning |
|---|---|---|
| `document` | string | Document id, from a table of contents' `documents`. Omitted = `spec`. |
| `version` | string | The document's version, e.g. `1.0`, `2.0`, `2.1` or `editors-draft` for `spec`. Omitted = its latest published version. |
| `section` | string | Section id. Omitted = return the table of contents. |

### spec-response

`https://wyvrn.app/documentation/1.1/spec-response`. Registry → requester, `thid` =
the request's id.

| Field | Type | Meaning |
|---|---|---|
| `document`, `version`, `title` | string | REQUIRED. What was returned. |
| `didcomm_versions` | string[] | DIDComm versions the document applies to. |
| `source` | object | As in `response`. |
| `toc` | object[] | Without `section`: every heading's `id`, `title` and `level`. |
| `documents` | object[] | With `toc`: every document the registry serves, each with `id`, `title`, `versions` (REQUIRED) and `didcomm_versions`. |
| `section` | object | With `section`: its `id`, `title` and `markdown`, including any subsections. |

Exactly one of `toc` and `section` is present.

## L10n

Documentation is returned in the language its source is written in, which for
didcomm.org and the DIDComm specification is English. No localization is defined in
this version.

## Implementations

| Name / Link | Implementation Notes |
|---|---|
| [wyvrn-cloud/documentation-server](https://github.com/wyvrn-cloud/documentation-server) | `registry`. Indexes didcomm.org, the Aries RFCs, the DIDComm Messaging spec and its extensions, plus configurable extra sources. |
| [wyvrn-cloud/mcp](https://github.com/wyvrn-cloud/mcp) | `requester`. Exposes this protocol to AI agents as MCP tools. |

## Endnotes

### Future Considerations

- **Schemas as a registry requirement.** didcomm.org protocol definitions don't
  include machine-readable schemas today, so registries have to supply their own. If
  the registry adopted a convention like this repo's (`schemas/<message>.json` next to
  each `readme.md`), every registry would serve the same, author-owned schemas.
- **Range filters.** `query.didcomm_version` takes a single version. A requester that
  speaks several sends one query per version, or none and filters `didcomm_versions`
  itself.
- **Change notification.** A future version could let requesters subscribe to updates
  for the protocols they use.
- **Signed documentation.** Registries could sign responses (or relay authors'
  signatures), so documentation can be passed on and still verified.
