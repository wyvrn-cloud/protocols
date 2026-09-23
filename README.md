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
```

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

`multi-device` and `history-sync` are companion protocols for the same
problem (one person, several devices, no central account server) and are
meant to be read together: `multi-device` covers device identity/enrollment
and the device roster; `history-sync` covers reconciling message history
and other local state between devices it references, including catching up
a newly enrolled device.
