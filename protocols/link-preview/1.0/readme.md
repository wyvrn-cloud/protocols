---
title: Link Preview
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/link-preview/1.0
status: Proposed
summary: Lets one of a person's own devices build the preview of a link (title, description, site name, thumbnail) for another of their devices that cannot read the page itself — a web build, kept from other sites' HTML by CORS — so that the preview travels in the chat message as chat-message/1.0 defines, without any third party ever seeing the link. Runs over multi-device/1.0's Device DID channel, never between contacts.
tags:
  - messaging
  - chat
  - multi-device
authors:
  - name: wyvrn
---

## Summary

A chat message that contains a link can carry a preview of the page —
[`chat-message/1.0`](../../chat-message/1.0/readme.md)'s `embeds`, built by
the sender so that no receiver has to touch the site. A sender running in a
browser cannot build one: a web page may not read another site's HTML. A
sender running natively (desktop, Android) can.

This protocol lets the web build ask one of the *same person's* other
devices, if one that can is running, to fetch the page and hand back the
preview. If none can, the link goes out without a preview. No relay, no
third-party preview service, and no contact's device is ever involved; the
only parties are a person's own enrolled devices, talking over the channel
[`multi-device/1.0`](../../multi-device/1.0/readme.md) already gives them.

## Motivation

Link previews are built by the sender for a reason `chat-message/1.0`'s
Security section spells out: a link can be sent precisely to learn who
opens it, so a receiver must never have to fetch it. That puts the fetch on
the sender's device, and a web build's device cannot do it. A `fetch()` of
another origin's page from a browser is blocked by CORS unless that site
allows it, and the sites people link to do not.

The usual answer is a preview service: a server the app operator runs that
fetches pages on the client's behalf. That hands every link a person is
about to send, before they have sent it, to a third party — the one thing
this family of protocols is built not to do. The answer here is to notice
that the person usually owns a device that *can* fetch the page, and that
`multi-device/1.0` already gives their devices an authenticated channel to
each other. The web build asks its sibling; the sibling fetches the page
the same way the native build would have for its own message.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `requester` | A device composing a message that cannot read the linked page itself, and asks for a preview. |
| `builder` | A device that can read the page, and builds the preview. |

Both roles are played by enrolled devices of **one identity**, per
`multi-device/1.0`'s roster. A device says it can play `builder` with the
value `"link-preview"` in its `device-announce.capabilities`; a `requester`
asks only a sibling that has said so. A device may play both roles at
different times (a native build asks nobody, since it can fetch for itself,
but may answer).

## Connectivity

Device-to-device over the Device DID channel, mediated exactly as
`multi-device/1.0` and [`history-sync/1.0`](../../history-sync/1.0/readme.md)
messages are: addressed to a specific sibling's Device DID, through the
mediator both are registered with. Never broadcast, and never addressed to
an Identity DID or a contact.

The exchange is a request and one response. Both are time-critical — a
preview is wanted while the message is being typed — so the builder has to
be running, unlocked, and connected: a closed phone cannot help, and a
response that arrives after the requester has given up is discarded.

## States

| Role | State | Enters on | Leaves on |
|---|---|---|---|
| `requester` | `requested` | sending `preview-request` | `preview-response` from the device asked; the link removed from the draft; or a timeout (see Design By Contract) |
| `builder` | — | | |

The builder is stateless: it answers each request as it comes. The
requester keeps, per link in the draft, at most one outstanding request.

## Basic Walkthrough

Alice has link previews turned on. Her laptop is a native build and has
announced `"link-preview"` in its capabilities; she is typing in the web
build on her tablet, which cannot fetch other sites.

1. Alice pastes `https://example.com/articles/42` into the message box.
   The tablet's agent, seeing a link that looks finished, sends its laptop:

   ```json
   {
     "id": "9f1c6b2e-3a4d-4e5f-8b7c-1d2e3f4a5b6c",
     "type": "https://wyvrn.app/link-preview/1.0/preview-request",
     "from": "did:peer:4zQmTabletDeviceDid...",
     "to": ["did:peer:4zQmLaptopDeviceDid..."],
     "created_time": 1791400000,
     "expires_time": 1791400015,
     "body": {
       "url": "https://example.com/articles/42"
     }
   }
   ```

2. The laptop checks the request is from a device in its roster, fetches
   the page, reads its Open Graph tags, downloads the `og:image`, shrinks
   it to a thumbnail, and answers:

   ```json
   {
     "id": "2b7d8e9f-0a1b-4c2d-9e3f-4a5b6c7d8e9f",
     "type": "https://wyvrn.app/link-preview/1.0/preview-response",
     "from": "did:peer:4zQmLaptopDeviceDid...",
     "to": ["did:peer:4zQmTabletDeviceDid..."],
     "thid": "9f1c6b2e-3a4d-4e5f-8b7c-1d2e3f4a5b6c",
     "created_time": 1791400002,
     "body": {
       "url": "https://example.com/articles/42",
       "title": "Forty-two things about example domains",
       "description": "A short history of the reserved names, and why there are three of them.",
       "site_name": "Example",
       "image": "thumb"
     },
     "attachments": [
       {
         "id": "thumb",
         "media_type": "image/jpeg",
         "byte_count": 21840,
         "data": { "base64": "/9j/4AAQSkZJRg..." }
       }
     ]
   }
   ```

3. The tablet shows the preview above the message box, with a control to
   dismiss it. Alice finishes typing and sends. The `chat-message/1.0`
   message carries the preview in `embeds` and the thumbnail as its own
   inline attachment; Bob's agent shows it without ever contacting
   `example.com`.

Had the page been unreadable, the laptop would have answered with an
`error` instead:

```json
{
  "id": "7c3e4f5a-6b7c-4d8e-9f0a-1b2c3d4e5f6a",
  "type": "https://wyvrn.app/link-preview/1.0/preview-response",
  "from": "did:peer:4zQmLaptopDeviceDid...",
  "to": ["did:peer:4zQmTabletDeviceDid..."],
  "thid": "9f1c6b2e-3a4d-4e5f-8b7c-1d2e3f4a5b6c",
  "created_time": 1791400003,
  "body": {
    "url": "https://example.com/articles/42",
    "error": { "code": "unreachable", "comment": "connection refused" }
  }
}
```

Had the laptop been closed, nothing would have come back, and Alice's
message would have gone out without a preview — exactly as it would from a
device of hers with no sibling at all.

## Design By Contract

### Choosing a builder

- A requester asks only a sibling whose latest `device-announce` listed
  `"link-preview"` in `capabilities`. A device MUST NOT announce it unless
  it can fetch arbitrary pages (a native build), and SHOULD withdraw it (a
  new `device-announce` without it) if that changes.
- A requester sends a `preview-request` to one builder. It MAY send the
  same request — same `id`, same `url` — to more than one and take the
  first response; it MUST discard a response from any device it did not
  send that request to, even a sibling.
- A requester that is itself able to fetch the page (a native build) does
  not use this protocol; it builds the preview itself.
- Which builder to prefer is the requester's choice: a device that has
  recently answered, or a desktop over a phone (a phone's app is more
  often suspended). This protocol defines no preference.

### When to ask

- A requester asks as soon as a link in the message being composed looks
  finished — after a paste, after a space or line break following it, or
  after a short pause in typing — not when the message is sent. Asking
  late is the same as not asking: the person is about to press Send.
- A requester asks only if the person has link previews turned on. The
  setting is the requester's; a builder has no say in whether a preview is
  built for a sibling, only in whether it announces the capability.
- A requester keeps the result per link for the session and does not ask
  again for a link it already holds a result for, including an `error`. A
  link removed from the draft cancels its request: there is no cancel
  message, the requester just discards what comes back.
- A request carries an `expires_time` of about 15 seconds after
  `created_time`, on the message and (as `typing-indicators/1.0`'s
  Composition sets out) on every `routing/2.0/forward` it is wrapped in, so
  that a mediator with nowhere live to deliver it drops it rather than
  queue it and push a closed phone awake for a request it is already too
  late to answer. A builder MUST NOT answer a request whose `expires_time`
  has passed.

### Building

- The builder MUST act only on a request sender-authenticated by a Device
  DID that is in its current roster and has not been revoked, and MUST
  silently ignore any other — `history-sync/1.0`'s Security section states
  the rule for the Device DID channel, and it applies here unchanged. An
  ignored request is not answered, not even with an `error`.
- The builder fetches `url` as a browser would a page: `GET`, following at
  most 5 redirects, with no cookies, no credentials, and no stored state
  from any earlier fetch. It SHOULD send an ordinary browser `User-Agent`
  for the platform it runs on and an `Accept` for HTML, and SHOULD send the
  `Accept-Language` the person uses. The limits in Security apply at every
  hop.
- From the page it takes, in order of preference for each field:
  [Open Graph](https://ogp.me) (`og:title`, `og:description`,
  `og:site_name`, `og:image`), then Twitter card tags (`twitter:title`,
  `twitter:description`, `twitter:image`), then the document's `<title>`
  and `<meta name="description">`. A relative `og:image` (or
  `twitter:image`) is resolved against the final page URL after redirects.
  Any field it cannot find is left out.
- The builder downloads the image itself, decodes it, and shrinks it to a
  thumbnail: at most 400 pixels on its longest side, re-encoded as JPEG or
  WebP (PNG if it has transparency), and at most **64 KiB** encoded. An
  image it cannot decode, or cannot bring under the limit, is left out
  rather than sent as is. The limit is small on purpose: the thumbnail
  goes inside the chat message, so it travels in every copy — one per
  group member, one per device of each of them through `history-sync/1.0`,
  and every re-send — and `chat-message/1.0`'s inline attachment budget is
  shared with whatever media the message carries. A preview that costs
  more than a message is a bad trade.
- The builder SHOULD bound the text it returns — a title to a few hundred
  characters, a description to about a thousand — and MUST strip control
  characters, since a page can put anything in a tag.
- A page the builder read but that has nothing to show (no title at all)
  is answered with a response carrying only `url`; a page it could not
  read is answered with `error`. Both tell the requester to stop waiting.
- The builder never shows the person anything about a request it answers.
  A request is their own composing, on their own other device.

### Using the result

- A response is matched to its request by `thid`, and accepted only from
  the device the request went to (see Choosing a builder). Its `url` MUST
  equal the request's; a response whose `url` differs is discarded.
- The requester shows the preview above the message box, where the person
  can dismiss it; a dismissed preview is not sent. A response with `error`
  or with no fields is shown as nothing.
- When the message is sent, a preview the requester holds goes in its
  `embeds` with the thumbnail copied in as an inline attachment of the
  chat message, as `chat-message/1.0` defines. If the response has not
  arrived yet, the message goes at once, without waiting, and the preview
  follows as a `chat-message/1.0/message-edit` carrying `embeds` — that
  protocol's Design By Contract already provides for a preview ready after
  the message went out, and says a sender SHOULD give up after about 10
  seconds. The requester gives up on the request then, too.
- The requester MUST treat the text as untrusted (it renders as text, never
  as markup) and the thumbnail as untrusted bytes (see Security).

## Security

- **The builder's address is what the site sees.** The fetch comes from one
  of the person's own devices, as it would from a native build composing
  the same message; no third party learns the link, and no contact does
  until the message is sent. The person chose the link, and the fetch is
  the consequence of having link previews on, which is their setting.
- **The fetched page is hostile input.** A builder is fetching an arbitrary
  URL that was pasted into a message box, possibly by a person who was
  sent it by someone with intent. A builder MUST:
  - refuse any scheme other than `http` and `https`;
  - resolve the host and refuse an address that is private, link-local,
    loopback, or otherwise not publicly routable (`10/8`, `172.16/12`,
    `192.168/16`, `127/8`, `169.254/16`, `fc00::/7`, `fe80::/10`, `::1`,
    and `localhost`), connect only to the address it checked, and check
    again at every redirect — a page on a public host may redirect to the
    builder's own network;
  - follow a bounded number of redirects (5) and refuse a redirect to a
    refused scheme or address;
  - cap what it downloads (a page at 2 MiB, an image at 10 MiB) and how
    long it spends (10 seconds for the whole job);
  - parse the HTML only to read tags, never run scripts, load subresources,
    or render it; and decode the image in a decoder it would trust with
    bytes from a stranger, since that is what they are.
- **The thumbnail is untrusted bytes** to the requester as well: it was
  decoded and re-encoded by a sibling, which makes it well-formed if the
  sibling is honest, and the sibling is trusted exactly as far as
  `multi-device/1.0` trusts an enrolled device. A requester decodes it as it
  would any attachment, and a receiver of the chat message it ends up in is
  told nothing about where it came from, as with any `embeds` thumbnail.
- **Only roster devices are heard.** A request from anything but an
  enrolled, unrevoked Device DID is ignored, which keeps a builder from
  being a fetch proxy for whoever can reach its Device DID (which is not a
  secret, see `multi-device/1.0`). A revoked device goes on sending
  requests, since nobody tells it; the rule is what stops them being
  answered. A response is accepted only from the device asked, which keeps
  a sibling from injecting a preview for a link it was not asked about.
- **A preview reveals the draft.** A request tells the builder device what
  link the person is about to send, before they send it. Both devices are
  the person's own, so nothing leaves their control; but a requester
  SHOULD NOT send a request for a link the person has not finished typing,
  which is also why it waits for the link to look finished.
- **Building for a contact is not allowed.** The same request and response
  could let a native device build previews for a *contact's* web device.
  It MUST NOT: that device would learn every link the contact is about to
  send, which is the leak this protocol exists to avoid, only moved to
  someone the person knows. A builder MUST ignore a request from any DID
  that is not in its own roster, and a device MUST NOT disclose this
  protocol to contacts through `discover-features/2.0`.

## Composition

- **With `multi-device/1.0`.** Runs over its Device DID channel, between
  devices in its roster. A builder announces itself with `"link-preview"`
  in `device-announce.capabilities`, which is how a requester finds one;
  `discover-features/2.0` is not used, since the parties are one person's
  devices and the roster already says what each can do.
- **With `history-sync/1.0`.** Takes its trust rule for the Device DID
  channel unchanged. Nothing here is synchronized: a request and its
  response are transient, and the preview that results lives in the chat
  message, which is synchronized as a message.
- **With `chat-message/1.0`.** The response's `title`, `description`,
  `site_name` and `image` are exactly the fields of that protocol's link
  preview, so the requester copies them into `embeds`, with the thumbnail
  re-attached inline on the chat message. A preview ready after the
  message was sent follows as a `message-edit` carrying `embeds`, within
  about 10 seconds, as that protocol says. A requester MUST NOT put an
  embed in a message for a URL that is not in its `content`.
- **With `routing/2.0`** and the mediator. A request carries a short
  `expires_time`, on the message and its `forward`s, for the reason
  `typing-indicators/1.0`'s Composition gives: a request a mediator cannot
  deliver live is better dropped than queued and pushed. A builder that
  receives a stale one anyway ignores it.
- **With `discover-features/2.0`.** Not disclosed. A query from a contact is
  answered without this protocol.

## Message Reference

### `preview-request`

Message Type URI: `https://wyvrn.app/link-preview/1.0/preview-request`

Sent by a `requester` to a `builder` in its roster. Asks for a preview of
one link.

Headers: `created_time` REQUIRED; `expires_time` SHOULD be set, about 15
seconds after `created_time`, and copied onto every `forward`.

| Field | Type | Description |
|---|---|---|
| `url` | string | REQUIRED. The link, an `http` or `https` URL, exactly as it will appear in the message's `content`. |

Schema: [`schemas/preview-request.json`](schemas/preview-request.json).

### `preview-response`

Message Type URI: `https://wyvrn.app/link-preview/1.0/preview-response`

Sent by the `builder` to the `requester`, once per request. Carries the
preview, or says why there is none.

Headers: `thid` REQUIRED, the request's `id`; `created_time` REQUIRED.

| Field | Type | Description |
|---|---|---|
| `url` | string | REQUIRED. The request's `url`, unchanged (not the URL after redirects). |
| `title` | string | OPTIONAL. The page's title. |
| `description` | string | OPTIONAL. The page's description. |
| `site_name` | string | OPTIONAL. The site's name. |
| `image` | string | OPTIONAL. The `id` of an entry in `attachments[]` holding the thumbnail inline: `media_type` an image type, `data.base64` at most 64 KiB decoded. |
| `error` | object | OPTIONAL. Present, and the four fields above absent, when the page could not be read: `code` (string, below) and an optional `comment` (string, for diagnostics; never shown as the page's words). |

`error.code` is one of:

| Code | Meaning |
|---|---|
| `refused` | The builder would not fetch it: a scheme, address or redirect its rules forbid. |
| `unreachable` | No usable answer from the host: DNS, connection, TLS, or an HTTP error status. |
| `timeout` | The job ran out of time. |
| `too-large` | The page or image exceeded the builder's size cap. |
| `unsupported` | The response was not HTML, or the builder could not make sense of it. |

A response with `url` alone means the page was read and has nothing to
show. Any other field in the body is ignored by this version.

Schema: [`schemas/preview-response.json`](schemas/preview-response.json).

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. A handler at `src/handlers/linkPreview/` registered in `src/services/didcomm/messageRouter.ts` (receiving, both roles) and a preview service under `src/services/linkEmbed/` (today it holds only `detectEmbedKind.ts`, which classifies a bare image or video URL by its `Content-Type`, not a page preview) are the starting points; the native builds would fetch through `lib/network.ts`'s `httpFetch` seam, and `src/handlers/multiDevice/multiDeviceHandler.ts` is where the `"link-preview"` capability gets announced.

## Endnotes

### Why not a preview service

A preview service is the standard answer and it works; it is also a server
that sees every link before it is sent, operated by someone who is not a
party to the conversation. `chat-message/1.0` puts the fetch on the sender
so that receivers never have to touch a link; moving it to a server would
put it somewhere worse. A person's own device is the only place that is no
worse than the sender's.

### Why the builder shrinks the image

The requester is a web build that could, in principle, resize an image on
a canvas — but it cannot fetch the image in the first place, for the same
reason it cannot fetch the page. The builder has the bytes, so the builder
makes the thumbnail, and the requester never handles a full-size image from
a stranger's site.

### Why the request is not queued

A request answered after the message went out and its 10-second window
closed is wasted work, and one answered after a phone woke for it is worse
than wasted. The short `expires_time` says so to the mediator in the one
way `routing/2.0` provides; `typing-indicators/1.0` is where that
mechanism is laid out, because it depends on it entirely.

### Future Considerations

- Previews of things that are not pages — a video's embed, an article's
  reading time — if `chat-message/1.0`'s link preview grows fields for
  them.
- Remembering previews across sessions, on the requester or by asking the
  builder for one it built recently.
- Letting a builder fetch bytes-by-reference media for a sibling that
  cannot, in the same shape; the trust rule and the limits here would
  carry over.
