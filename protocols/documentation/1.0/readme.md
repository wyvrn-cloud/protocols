---
title: Documentation
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/documentation/1.0
status: Proposed
summary: Lets an agent ask a documentation registry, over DIDComm, for the definition of a DIDComm protocol (metadata, prose sections, example messages and JSON Schemas per message type) or for a section of the DIDComm Messaging specification, so software and AI agents can learn a protocol at the moment they need it.
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

A registry is an ordinary DIDComm agent that indexes protocol definitions written in
the [didcomm.org](https://didcomm.org) registry's format: a `readme.md` with YAML
frontmatter, prose sections and example messages, plus JSON Schemas where it has them.
Requesters can:

- search what the registry knows (`query` → `catalog`)
- fetch one protocol's definition (`request` → `response`)
- fetch part of the DIDComm Messaging specification (`spec-request` → `spec-response`)

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
     "type": "https://wyvrn.app/documentation/1.0/request",
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
     "type": "https://wyvrn.app/documentation/1.0/response",
     "thid": "5c6f8e2a-7d43-4a8e-9b1e-0f4f2c3d1a10",
     "from": "did:example:registry",
     "to": ["did:example:requester"],
     "created_time": 1790889240,
     "body": {
       "piuri": "https://didcomm.org/coordinate-mediation/3.0",
       "title": "Coordinate Mediation",
       "status": "Production",
       "summary": "A protocol to coordinate mediation configuration between a mediating agent and the recipient.",
       "roles": ["mediator", "recipient"],
       "source": {
         "name": "didcomm.org",
         "path": "site/content/protocols/coordinate-mediation/3.0/readme.md",
         "revision": "4f1c2b9"
       },
       "available_sections": [
         {"id": "roles", "title": "Roles"},
         {"id": "basic-walkthrough", "title": "Basic Walkthrough"},
         {"id": "message-reference", "title": "Message Reference"}
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
           }
         }
       ]
     }
   }
   ```
3. If it doesn't yet know which protocol it needs, the requester can search first:
   ```json
   {
     "id": "a3f0c1d2-2b4e-4f6a-8c9d-0e1f2a3b4c5d",
     "type": "https://wyvrn.app/documentation/1.0/query",
     "from": "did:example:requester",
     "to": ["did:example:registry"],
     "return_route": "all",
     "body": {
       "match": "https://didcomm.org/*",
       "text": "mediat",
       "status": ["Production"]
     }
   }
   ```
   ```json
   {
     "id": "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f70",
     "type": "https://wyvrn.app/documentation/1.0/catalog",
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
           "has_schemas": true
         }
       ]
     }
   }
   ```
4. Spec sections work the same way. Without `section`, the registry returns the table
   of contents:
   ```json
   {
     "id": "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
     "type": "https://wyvrn.app/documentation/1.0/spec-request",
     "return_route": "all",
     "body": {"version": "2.1", "section": "message-headers"}
   }
   ```
   ```json
   {
     "id": "f6a7b8c9-d0e1-4f2a-9b3c-4d5e6f7a8b9c",
     "type": "https://wyvrn.app/documentation/1.0/spec-response",
     "thid": "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
     "body": {
       "version": "2.1",
       "title": "DIDComm Messaging Specification v2.1",
       "section": {
         "id": "message-headers",
         "title": "Message Headers",
         "markdown": "A DIDComm plaintext message conveys most of its application-level data ..."
       }
     }
   }
   ```

## Design By Contract

- **Protocols are identified by PIURI, never by file path.** A registry indexes each
  definition under the `piuri` in its frontmatter. Where a source's folder layout
  disagrees with that value, the frontmatter wins.
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
- **Section ids** are the section heading in lower kebab-case (`Basic Walkthrough` →
  `basic-walkthrough`). A heading that repeats gets `-2`, `-3`, … in document order.
  Every `response` lists `available_sections`, so a requester can always discover valid
  ids. The same rule applies to `spec-response` section ids.
- **Schemas** are [JSON Schema 2020-12](https://json-schema.org/draft/2020-12) documents
  that each validate one complete DIDComm v2 plaintext message (headers and `body`), not
  just its `body`. A message type with no known schema is still listed under `messages`
  with its examples and no `schema`. Schemas SHOULD NOT forbid unknown properties, since
  DIDComm requires recipients to ignore fields they do not understand.
- **Examples** are returned as the source wrote them, apart from being parsed as JSON.
  They are illustrative and MAY not validate against the schema. DIDComm v1-style
  examples (`@type` instead of `type`) are grouped under their `@type`.
- **Untrusted content.** Everything in a reply is text written by third parties, which
  the registry passes along. A requester MUST treat it as data, not instructions (see
  Security).

| Problem code | When |
|---|---|
| `e.p.not-found.protocol` | No definition is indexed for the requested `piuri` (or its major version). `args`: `[piuri]`. |
| `e.p.not-found.section` | A requested section id does not exist. `args`: `[section-id]`. |
| `e.p.not-found.spec-version` | The registry does not serve the requested spec `version`. `args`: `[version]`. |
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
  can send anoncrypted requests with `return_route: all`. The reply then comes back on
  the same connection without the requester revealing its DID.
- **Denial of service.** Full protocol definitions can be tens of kilobytes. Requesters
  SHOULD use `sections` to ask for only what they need. Registries MAY limit `query`
  page size and SHOULD cap `limit`.

## Message Reference

Every message's JSON Schema is in [`schemas/`](schemas/), one file per message type.

### query

`https://wyvrn.app/documentation/1.0/query`. Requester → registry. Searches the
registry's catalog. All body fields are optional; an empty body lists everything.

| Field | Type | Meaning |
|---|---|---|
| `match` | string | PIURI pattern, Discover Features 2.0 wildcard rules. |
| `text` | string | Case-insensitive substring searched in title, summary and tags. |
| `status` | string[] | Keep entries whose status is one of these (e.g. `Production`). |
| `tags` | string[] | Keep entries carrying at least one of these tags. |
| `limit` | integer ≥ 1 | Page size. The registry MAY cap it. |
| `offset` | integer ≥ 0 | Entries to skip. Default `0`. |

### catalog

`https://wyvrn.app/documentation/1.0/catalog`. Registry → requester, `thid` = the
query's id.

| Field | Type | Meaning |
|---|---|---|
| `entries` | object[] | REQUIRED. Each has `piuri`, `title`, `status` (REQUIRED) and `summary`, `tags`, `has_schemas`. |
| `total` | integer | REQUIRED. Number of matches across all pages. |
| `offset` | integer | REQUIRED. Offset of the first entry in this page. |

### request

`https://wyvrn.app/documentation/1.0/request`. Requester → registry.

| Field | Type | Meaning |
|---|---|---|
| `piuri` | string | REQUIRED. PIURI, or a message type URI. |
| `sections` | string[] | Section ids to include. Omitted = all sections; `[]` = none. |
| `messages` | boolean | Include `messages` (examples and schemas). Default `true`. |

### response

`https://wyvrn.app/documentation/1.0/response`. Registry → requester, `thid` = the
request's id.

| Field | Type | Meaning |
|---|---|---|
| `piuri` | string | REQUIRED. The PIURI actually returned (see minor versions). |
| `title`, `status` | string | REQUIRED. From frontmatter. |
| `summary`, `publisher`, `license` | string | From frontmatter. |
| `tags` | string[] | From frontmatter. |
| `authors` | object[] | From frontmatter (`name`, optional `email`). |
| `roles` | string[] | Role names, when the registry can determine them. |
| `source` | object | `name` (REQUIRED), `path`, `revision`, `url`: where the definition came from. |
| `available_sections` | object[] | REQUIRED. Every section's `id` and `title`, in document order. |
| `sections` | object[] | The requested sections: `id`, `title`, `markdown`. |
| `messages` | object[] | Present unless `messages: false` was requested. Each has `type` (REQUIRED), `examples` (array of objects), and `schema` (a JSON Schema, when known). |

### spec-request

`https://wyvrn.app/documentation/1.0/spec-request`. Requester → registry.

| Field | Type | Meaning |
|---|---|---|
| `version` | string | Spec version, e.g. `2.0`, `2.1`, or `editors-draft`. Omitted = the registry's latest published version. |
| `section` | string | Section id. Omitted = return the table of contents. |

### spec-response

`https://wyvrn.app/documentation/1.0/spec-response`. Registry → requester, `thid` =
the request's id. Has `version` and `title` (REQUIRED), optional `source` (as in
`response`), and either `toc` (array of `id`, `title`, `level`) or `section` (`id`,
`title`, `markdown`, including any subsections).

## L10n

Documentation is returned in the language its source is written in, which for
didcomm.org and the DIDComm specification is English. No localization is defined in
this version.

## Implementations

| Name / Link | Implementation Notes |
|---|---|
| [wyvrn-cloud/documentation-server](https://github.com/wyvrn-cloud/documentation-server) | `registry`. Indexes didcomm.org and the DIDComm Messaging spec, plus configurable extra sources. |
| [wyvrn-cloud/mcp](https://github.com/wyvrn-cloud/mcp) | `requester`. Exposes this protocol to AI agents as MCP tools. |

## Endnotes

### Future Considerations

- **Schemas as a registry requirement.** didcomm.org protocol definitions don't
  include machine-readable schemas today, so registries have to supply their own. If
  the registry adopted a convention like this repo's (`schemas/<message>.json` next to
  each `readme.md`), every registry would serve the same, author-owned schemas.
- **Change notification.** A future version could let requesters subscribe to updates
  for the protocols they use.
- **Signed documentation.** Registries could sign responses (or relay authors'
  signatures), so documentation can be passed on and still verified.
