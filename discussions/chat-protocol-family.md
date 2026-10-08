# The chat protocol family: what goes where

A map from the features and decisions in the Wyvrn messaging-features
document to the protocols in this repo that realise them, written when the
family was first drafted (October 2026). The protocols themselves are the
specification; this is the index, with the dependencies on other repos and the
things deliberately left open.

## The family

One core, companions grouped by behaviour, and the group protocol they all sit
in. Every companion refers to messages and conversations the way the core
defines (the *message reference* `{ id, author, snippet? }`, and the
conversation model: a pair has no `pthid`, a group's id travels in `pthid`, a
thread's root id in `thid`), so an agent discloses through
`discover-features/2.0` exactly the behaviours it has, and a sender gives each
recipient the richest form it supports.

| Protocol | Messages | What it carries |
|---|---|---|
| [`chat-message/1.0`](../protocols/chat-message/1.0/readme.md) | `message`, `message-edit`, `message-delete` | Markdown text; `reply_to`; `mentions`; `media` (pictures, files, GIFs, stickers as attachments, inline or by reference); sender-built link `embeds`; `forwarded`; edits and deletes by the author |
| [`message-reactions/1.0`](../protocols/message-reactions/1.0/readme.md) | `reactions` | a reactor's full current set of emoji on a message |
| [`chat-threads/1.0`](../protocols/chat-threads/1.0/readme.md) | `thread-create` | a reply chain made a named thread; thread messages carry `thid` |
| [`typing-indicators/1.0`](../protocols/typing-indicators/1.0/readme.md) | `typing` | live-only, self-expiring "is typing" |
| [`chat-pins/1.0`](../protocols/chat-pins/1.0/readme.md) | `pin`, `unpin` | shared pins per conversation |
| [`disappearing-messages/1.0`](../protocols/disappearing-messages/1.0/readme.md) | `timer` | a per-conversation timer, realised as `expires_time` on each new message |
| [`group-chat/2.0`](../protocols/group-chat/2.0/readme.md) | `invite`, `member-added`, `member-removed`, `leave`, `admin-transfer`, `update` | an admin (the creator), removal, leaving, succession, name/picture, settings |
| [`link-preview/1.0`](../protocols/link-preview/1.0/readme.md) | `preview-request`, `preview-response` | a web device asks its own native sibling to build a link preview (Device DID channel) |
| [`history-sync/1.1`](../protocols/history-sync/1.1/readme.md) | 1.0's, plus `search-request`, `search-response` | messages that change after receipt; follows, bookmarks, mutes, blocks, sticker packs synced; search across a person's devices |
| [`chat-services.md`](chat-services.md) | (HTTP, not DIDComm) | the storage, sticker and GIF-relay services the above lean on |

Already published protocols the family composes with rather than replacing:
`basicmessage/2.0` (the plain form every message degrades to),
`receipts/1.0` (read receipts, now pairwise-to-author in groups too),
`media-sharing/1.0` (its `ciphering` shape and `request-media`),
`user-profile/1.0`, `discover-features/2.0`, `multi-device/1.0`.

The two drafts on the `chat-message-and-reactions` branch are superseded by
`chat-message/1.0` and `message-reactions/1.0` here; the reactions design was
kept, the message grew into the core.

## Where each decision landed

| Area | Decision | Where |
|---|---|---|
| Scope | Registry-style, publish later; all platforms together | every spec's frontmatter and Motivation; `https://wyvrn.app/` PIURIs |
| Replies | id + ~100-char snippet; same conversation only; a reply to you alerts like a mention | chat-message: message reference, `reply_to`, Receiving |
| Replies | Deleted/edited originals still referable; snippet is as sent; label for text-less messages | chat-message: message reference, "The label of a message with no text" |
| Threads | Chain → named thread, shared, by someone who wrote in it; earlier messages stay, later ones only in thread; one level; no closing; writers and followers notified; follow synced | chat-threads; history-sync/1.1 `threadFollows` |
| Reactions | Full set per reactor; ≤20 distinct per message; visible; no notification/unread; quick bar of six | message-reactions |
| Emoji | Built-in picker, shortcodes, bundled set | app-side (`chat` repo); nothing on the wire |
| Custom emoji | Person-owned, sticker-pack format; as reactions later | chat-services (pack format); message-reactions Future Considerations |
| Mentions | Group members only; `@everyone`; break through mute | chat-message: Mentions (`[@Alice](did:…)` + `mentions` list) |
| Embeds | Sender-built, only with previews on; receiver may load live; web build asks a sibling; 10-second follow-up | chat-message: Link previews, `message-edit` with `embeds`; link-preview |
| Formatting | Spoilers, syntax-coloured code, tables; 8,000-character limit | chat-message: Sending a message (the dialect) |
| Editing / deleting | No limit, marked edited; delete leaves "Message deleted"; admin cannot delete others' | chat-message: Editing, Deleting; group-chat/2.0 Security |
| Typing | Pairs and groups; live only, never queued or pushed | typing-indicators (and its requirement on the mediator) |
| Files | Inline ≤256 KiB, encrypted on a storage service above; shrink by default; service sets the maximum; retention until fetched or operator limit | chat-message: Media; chat-services: storage |
| GIFs | Link to the provider through a relay you run; autoplay with a setting | chat-message `media[].kind: gif`; chat-services: GIF relay |
| Stickers | User-made packs from a sticker service; shareable flag; static and animated | chat-message `media[].kind: sticker`; chat-services: sticker service and pack document |
| Older apps | A version per recipient; plain text for what has one; nothing for reactions/typing/pins/timer; edits as "Edited:" messages; deletes not sent | chat-message Composition; each companion's Composition |
| Forwarding | Sender chooses whether to name the author | chat-message `forwarded` |
| Pins | Shared pins (members, admin-restrictable) and private bookmarks | chat-pins; history-sync/1.1 `bookmarks` |
| Disappearing | Per-conversation timer, stamped per message at send time; anyone / admin-only with an admin | disappearing-messages |
| Group receipts | Up to five avatars then a count | group-chat/2.0 Composition with `receipts/1.0` |
| Group admin | Creator; remove / transfer / name / picture / who may add / who may pin; longest-standing successor; 1.0 groups stay admin-less; warn past 50 | group-chat/2.0 |
| Mute and block | Both local; blocked messages dropped (default) or hidden; synced between devices | history-sync/1.1 `mutes`, `blocks` |
| Search | One conversation; this device first, then other online devices | history-sync/1.1 `search-request`/`search-response` |
| Sync | Reactions, edits, deletes, threads all reach every own device | history-sync/1.1 (messages are no longer append-only) |
| Notifications | Preview image or short description; a thread reply opens the thread | app-side; chat-message's label; chat-threads Following |
| Calls | Audio-only mesh first | not in this round (the registry's `webrtc/1.0` is the obvious starting point) |
| Servers | Private vs open channels | not in this round; chat-message's endnotes and group-chat/2.0's endnote on a DID-addressed group leave the door open |

## What the family needs from other repos

- **`wyvrn-didcomm`**: copy an inner message's `expires_time` onto every
  `routing/2.0/forward` it wraps it in (`create_forward_message` sets
  `created_time` only today). Needed by typing-indicators and link-preview;
  harmless for everything else.
- **`wyvrn-mediator`**: for a `forward` carrying an `expires_time`, deliver
  live or drop once expired rather than queue, purge from the queue at expiry,
  and never push for one about to expire (typing-indicators, Composition).
  Optionally drop queued messages past their `expires_time` in general
  (disappearing-messages).
- **`chat`**: one handler folder per protocol, per its `CLAUDE.md`; the
  message record gains edit state, a deleted flag, reactions, pins, thread
  membership and an expiry; `discover-features` runs against every group
  member; link-preview needs the `"link-preview"` capability announced by
  native builds.
- **New services** (beside the mediator, separate programs): storage, sticker,
  GIF relay — sketched in `chat-services.md`, each still to be designed in
  full.

## Still open

- Whether an edited message keeps its earlier versions anywhere (the wire
  carries only the new text; a receiver may keep history).
- The sticker service's registration, ids and takedown; exact sticker limits.
- Authentication to the storage and sticker services (two options sketched,
  neither chosen).
- Telling a late-joining group member about existing threads, pins and the
  timer without every author re-sending (each spec lists it as future).
- Community servers: a relay role, author-signed messages
  (`anoncrypt(sign(...))`), channel ids, and history for private channels.
- Voice calls.
