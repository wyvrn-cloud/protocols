# wyvrn-protocols

A staging ground for DIDComm protocols authored by the `wyvrn` ecosystem
(see the sibling [`wyvrn-didcomm`](../wyvrn-didcomm),
[`wyvrn-mediator`](../wyvrn-mediator), [`wyvrn-chat`](../wyvrn-chat) repos)
that aren't covered by an existing protocol in the real
[didcomm.org](https://didcomm.org) registry.

## Why this repo exists

Before writing a custom protocol for something a `wyvrn-*` app needs, check
the real registry first — a local clone lives at
`~/dev/work/didcomm.org/didcomm.org`, with every published protocol's
definition under `site/content/protocols/<name>/<version>/readme.md`. Often
one already exists (`wyvrn-chat`'s read-receipt feature, for example, uses
the real, already-published
[`receipts/1.0`](https://didcomm.org/receipts/1.0) protocol directly — no
new protocol was needed there at all).

When one genuinely doesn't exist, this repo is where wyvrn documents its own
— in the *exact same format* that registry itself uses
(`docs/protocol-example.md` and `docs/pr-guide.md` in that clone define the
real authoring conventions), so that a protocol which matures enough could
be proposed to didcomm.org later by copying its `readme.md` over more or
less as-is.

## Layout

```
protocols/
  <protocol-name>/       lower-kebab-case slug
    <version>/            <major>.<minor>, no patch component
      readme.md            frontmatter + body, same schema as didcomm.org's own
      schemas/             optional: one JSON Schema per message type
        <message-name>.json
```

### Schemas

A protocol may ship machine-readable schemas next to its `readme.md`, one file per
message type, named after the last segment of the message type URI (so
`https://wyvrn.app/documentation/1.0/request` → `schemas/request.json`). Each one is a
[JSON Schema 2020-12](https://json-schema.org/draft/2020-12) document that validates the
**complete DIDComm v2 plaintext message** (headers and `body`, with `type` pinned by
`const`), not just the body, so headers a message needs (`thid` on a reply, `from` on an
invitation, `created_time` on a basicmessage) are checked too. Schemas should not set
`additionalProperties: false`: DIDComm requires recipients to ignore fields they don't
understand.

`scripts/check_schemas.py` (`pip install jsonschema json5`) checks every shipped schema
is valid JSON Schema 2020-12 that names its message type, and that every example of
that type in the protocol's `readme.md` validates against it. CI runs it on every pull
request.

Documentation registries implementing
[`documentation/1.0`](protocols/documentation/1.0/readme.md) serve these schemas with
the protocol's definition. didcomm.org has no equivalent convention yet; this layout is
what we intend to propose there.

## PIURI namespace

A real `https://didcomm.org/<name>/<version>` PIURI is only legitimate once
a PR to that repo is actually merged — claiming it in real wire messages
before that would be presumptuous and could collide with an unrelated
protocol someone else registers there first. Every protocol documented
here uses `https://wyvrn.app/<name>/<version>` instead, until (if ever) it's
proposed and accepted upstream, at which point both this doc and the code
implementing it would move to the real `didcomm.org` PIURI.

## Protocols

| Protocol | Version | Status | Used by |
|---|---|---|---|
| [`group-chat`](protocols/group-chat/1.0/readme.md) | 1.0 | Proposed | [`wyvrn-chat`](../wyvrn-chat) |
| [`multi-device`](protocols/multi-device/1.0/readme.md) | 1.0 | Proposed | none yet — design proposal |
| [`history-sync`](protocols/history-sync/1.0/readme.md) | 1.0 | Proposed | none yet — design proposal |
| [`push-notifications`](protocols/push-notifications/1.0/readme.md) | 1.0 | Proposed | none yet — design proposal |
| [`documentation`](protocols/documentation/1.0/readme.md) | 1.0 | Proposed | [`documentation-server`](https://github.com/wyvrn-cloud/documentation-server) (registry), [`mcp`](https://github.com/wyvrn-cloud/mcp) (requester) |

`multi-device` and `history-sync` are companion protocols for the same
problem (one person, several devices, no central account server) and are
meant to be read together: `multi-device` covers device identity/enrollment
and the device roster; `history-sync` covers reconciling message history
and other local state between devices it references, including catching up
a newly enrolled device.
