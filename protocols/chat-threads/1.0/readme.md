---
title: Chat Threads
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/chat-threads/1.0
status: Proposed
summary: Turns a reply chain in a conversation into a thread — a named side conversation with its own view — by a shared creation message that everyone in the conversation receives, and places later messages in the thread with the standard DIDComm `thid` header.
tags:
  - messaging
  - chat
authors:
  - name: wyvrn
---

## Summary

A thread is a reply chain given a name and its own view. Someone who wrote in
the chain creates the thread; everyone in the conversation receives that
creation, so they all see the same thread with the same messages in it. From
then on, a message sent in the thread carries the thread's id in the standard
DIDComm `thid` header and is shown in the thread instead of the main
conversation.

The thread's id is the `id` of the message at the root of the chain. The
messages are the ones [`chat-message/1.0`](../../chat-message/1.0/readme.md)
defines; this protocol adds one message type, `thread-create`, and gives the
`thid` header its meaning for the chat family.

## Motivation

A long reply chain in a busy conversation is hard to follow and drowns out
everything else. Messaging apps answer that with threads: the chain gets a
name and a view of its own, and people who care about it follow it there.

`chat-message/1.0` deliberately leaves threads out of the message itself, so
that an agent can disclose thread support separately through
[`discover-features/2.0`](https://didcomm.org/discover-features/2.0), and
reserves the `thid` header for this protocol. Nothing in the didcomm.org
registry covers chat threads.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `creator` | Turns a reply chain it wrote in into a thread. |
| `participant` | Receives the creation and places later messages carrying the thread's `thid` in the thread. |

Every party in a conversation may play both roles. The creator is also a
participant in the thread it created.

## Connectivity

The same as the conversation the chain belongs to: two parties, or, in a
group ([`group-chat/2.0`](../../group-chat/2.0/readme.md), or
[`1.0`](../../group-chat/1.0/readme.md)), the creator sends `thread-create`
separately, with the same `id`, to every other member. Messages sent in the
thread travel exactly as they would outside it.

## States

Nothing here waits for a reply. What a participant keeps is, per
conversation, the set of threads it knows of: each one's root, name, the
messages the creation listed, and the messages received with its `thid`.

| Event | Effect on the participant |
|---|---|
| `thread-create` received, root has no thread yet | the thread is created and shown; a line in the main conversation marks where |
| `thread-create` received, root already has a thread | the one with the earlier `created_time` stands (see Design By Contract); the other is ignored |
| `thread-create` received, sender did not write in the chain | ignored |
| `thread-create` received, root is itself in a thread | ignored |
| a message received with a `thid` naming a known thread | shown in the thread, not the main conversation |
| a message received with a `thid` naming no known thread | shown in the main conversation, as `chat-message/1.0` says; moved into the thread if its `thread-create` arrives |

## Basic Walkthrough

Alice, Bob and Carol are in a group whose id is `g1`, and each has learned
through `discover-features/2.0` that the others support this protocol.

1. Alice asks, in the group:

   ```json
   {
     "id": "m1",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "pthid": "g1",
     "created_time": 1791400000,
     "lang": "en",
     "body": { "content": "Who's bringing what to the picnic?" }
   }
   ```

   (sent to Bob and, separately, to Carol). Bob replies to it (`m2`, "I'll
   bring drinks"), and Carol replies to Bob (`m3`, "And I've got cups").
   Each reply names what it answers with `reply_to`, so the three form a
   chain whose root is `m1`.

2. The chain is getting long and the group is talking about other things
   too, so Bob makes it a thread. He wrote in the chain (`m2`), so he may.
   His agent sends every other member:

   ```json
   {
     "id": "t1",
     "type": "https://wyvrn.app/chat-threads/1.0/thread-create",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "pthid": "g1",
     "thid": "m1",
     "created_time": 1791400300,
     "body": {
       "root": { "id": "m1", "author": "did:example:alice", "snippet": "Who's bringing what to the picnic?" },
       "messages": [
         { "id": "m2", "author": "did:example:bob", "snippet": "I'll bring drinks" },
         { "id": "m3", "author": "did:example:carol", "snippet": "And I've got cups" }
       ],
       "name": "Picnic supplies"
     }
   }
   ```

   Alice's and Carol's agents check that Bob wrote one of the messages
   named (he did: `m2`), create the thread "Picnic supplies", and show a
   line in the main conversation, where `m3` was, saying Bob started it.
   `m1`, `m2` and `m3` stay where they were in the main conversation; the
   thread's view opens with them. Alice, Bob and Carol all follow the thread
   from now on, having written in it.

3. Carol posts in the thread. It is an ordinary `chat-message/1.0` message
   carrying the thread's id in `thid`:

   ```json
   {
     "id": "m4",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:carol",
     "to": ["did:example:alice"],
     "pthid": "g1",
     "thid": "m1",
     "created_time": 1791400400,
     "lang": "en",
     "body": {
       "content": "Plates too, if someone brings food",
       "reply_to": { "id": "m3", "author": "did:example:carol", "snippet": "And I've got cups" }
     }
   }
   ```

   Alice's and Bob's agents show `m4` in the thread only. Both are told of
   it, as followers; a member who had never written in the thread and had
   not chosen to follow it would see only that the thread had new messages.

Had Carol's agent not supported this protocol, Bob's agent would have sent
her nothing in step 2 — `thread-create` has no plain form — and Alice's
agent would have sent her `m4` unchanged in step 3, which she would see in
the main conversation, as `chat-message/1.0` says a receiver without threads
does.

## Design By Contract

### What a thread is

- A **thread** is identified by the `id` of its **root**, the message at the
  start of the reply chain it was made from. There is no separate thread id:
  a message is in a thread when its `thid` header is the root's `id`
  (compared as DIDComm compares message ids, case-insensitively), and
  `thread-create` itself carries that `thid`. This is the standard meaning of
  `thid`: the root began the thread, as DIDComm Messaging says a message with
  no `thid` of its own does, and every later message in it names that root.
- A thread lives inside one conversation, and a thread message carries the
  conversation's `pthid` (the group id) exactly as it would outside the
  thread. In a pair a thread message carries `thid` alone.
- A thread has **one level**. A message carrying a `thid` MUST NOT be the
  root of a thread, and a `thread-create` whose root carries a `thid`, or
  that lists a message carrying one, MUST be ignored.
- The messages **before** the creation — the root and the ones the creation
  lists — stay in the main conversation, where they were. The thread's view
  opens with them. A participant MUST NOT remove a listed message from the
  main conversation.
- The messages **after** the creation — those carrying the thread's `thid`
  — appear only in the thread. A participant shows, in the main
  conversation, a line where the thread was created that names it and opens
  it, and MAY show on that line how many messages the thread has since had.
- There is no closing, archiving or renaming in this version.

### Creating a thread

- Only someone who wrote in the chain may create a thread from it: the
  creator MUST be the author of the root or of at least one of the messages
  it lists.
- `root` and each entry of `messages` are message references as
  `chat-message/1.0` defines them. All MUST refer to messages in the
  conversation the creation is sent in. `root` SHOULD carry a `snippet`, and
  each listed message SHOULD too: a participant may not hold every message
  named, and the thread's view has to open with something.
- `messages` is the ordered list of the chain's messages that belong to the
  thread, other than the root, oldest first. Every listed message MUST reply,
  directly or through other listed messages, to the root. The list is
  explicit so that every participant agrees which messages are in the
  thread, rather than each recomputing the chain from whatever replies it
  happens to hold. It MAY be empty: a thread may be opened on a message no
  one has replied to yet, by its author.
- `name` is the thread's name, plain text, at most 100 characters. When it
  is absent, the thread is named after the root: its *label* as
  `chat-message/1.0` defines it (the opening words of its text, or `Photo`
  and the like for a message with no text), as the creator's agent sees it.
- `created_time` MUST be set. `thid` MUST be the root's `id`; a participant
  MUST ignore a `thread-create` whose `thid` and `root.id` differ.

### Receiving a creation

- A participant verifies that the sender wrote in the chain by comparing
  the authenticated sender with the senders of the named messages *it
  holds*, allowing for DID rotation as `chat-message/1.0` does for
  references. The `author` of a reference is the creator's claim, not
  proof. If the sender wrote none of the named messages the participant
  holds, and there are named messages it does not hold, it MUST keep the
  creation and decide when they arrive; if it holds every named message and
  the sender wrote none of them, it MUST ignore the creation. A creation
  kept for messages that never arrive is discarded after a reasonable time.
- A participant MAY leave out of the thread's view a listed message it
  holds that does not reply, directly or through other listed messages, to
  the root; it MUST NOT remove the message from the main conversation.
- One thread per root. If a participant receives two creations with the
  same root — two members made a thread from the same chain at about the
  same time — the one with the earlier `created_time` stands, whichever
  arrived first, and on equal `created_time` the one with the lower message
  `id`, compared case-insensitively. The other's name and list are
  discarded; messages received with the thread's `thid` are unaffected,
  since both creations named the same thread.
- A redelivered creation, or a sibling device's copy of one already held
  under the same `id`, is ignored.

### Sending in a thread

- A message in a thread is an ordinary message of its protocol — a
  `chat-message/1.0` `message`, `message-edit` or `message-delete`, a
  [`message-reactions/1.0`](../../message-reactions/1.0/readme.md)
  statement, a [`chat-pins/1.0`](../../chat-pins/1.0/readme.md) pin — with
  the thread's `thid`. An edit, delete, reaction or pin carries the `thid` of
  the message it is about, as those protocols say.
- A reply inside a thread uses `reply_to` as usual. It is the `thid` header,
  not `reply_to`, that puts a message in the thread; a reply to a message in
  a thread SHOULD be sent in the thread, and a message in a thread MAY reply
  to any message of its conversation.
- In a group, a thread message goes to every member, as any group message
  does, whether or not that member's agent implements this protocol: a
  member whose agent doesn't shows it in the main conversation, as
  `chat-message/1.0` says. Nothing is sent in place of `thread-create` to
  such a member (see Composition).

### Receiving in a thread

- A message whose `thid` names a thread the participant knows is placed in
  that thread.
- A message whose `thid` names no thread the participant knows — its
  `thread-create` has not arrived, was never sent, or was ignored — is shown
  in the main conversation, as `chat-message/1.0` requires of a receiver
  without threads. A participant MAY hold such a message briefly in case the
  creation is about to arrive, and MUST move it into the thread if the
  creation arrives later.
- A `thread-create` is not a message in the conversation: a participant
  SHOULD NOT count it as unread. It MAY tell the authors of the root and
  listed messages that a thread was made from them.

### Following

Who is told of a new message in a thread is the participant's own business,
not the wire's; this section describes the behaviour the protocol is designed
for.

- Each person **follows** some threads. Writing in a thread — as its creator,
  as the author of a message the creation named, or by posting in it —
  follows it; a follow control on the thread turns following on or off.
  Following is local, per person, and synced between a person's own devices
  by [`history-sync/1.1`](../../history-sync/1.1/readme.md), not by this
  protocol.
- A new message in a followed thread is notified and counted like any
  message of the conversation, and its notification opens the thread. A new
  message in a thread the person does not follow is not notified and does
  not mark the conversation unread; the line that opens the thread MAY show
  that it has new messages. A mention, or a reply to one of the person's own
  messages, breaks through regardless, as `chat-message/1.0` says.

## Security

- **The sender is the DID the encryption authenticates.** `thread-create`
  MUST be sent `authcrypt`, and a participant MUST ignore one that is not.
  No DID named inside it — `root.author`, a listed `author` — is
  authenticated by it.
- **Only someone who wrote in the chain creates the thread.** The rule is
  enforced by comparing the authenticated sender with the senders of the
  messages the participant holds. A creator could list a message that does
  not exist, claiming to have written it; a participant that cannot check
  waits rather than trusts (see Receiving a creation), and a participant
  that holds the whole chain is not fooled.
- **A creation reveals** that its root and listed messages exist, and their
  snippets reveal part of what they said, to everyone it is sent to — in a
  group, members who joined after those messages were sent.
- **A snippet can misquote**, as `chat-message/1.0` says of every snippet; a
  participant that holds the message shows its own text. A thread's `name`
  is untrusted text and MUST be shown as text, never rendered.
- **A thread cannot be undone** in this version. Anyone who wrote once in a
  chain can make it a thread and name it; the name stands for every
  participant that accepts the creation.
- **Non-repudiation is not offered.** Messages are sent `authcrypt`, which
  the recipient can verify but not prove to a third party.

## Composition

- **With `chat-message/1.0`.** Uses its message reference for `root` and
  `messages`, its label for a thread's default name, and its `reply_to` for
  replies inside a thread. `chat-message/1.0` reserves `thid` for this
  protocol and says what a receiver without it does with a message carrying
  one.
- **With `message-reactions/1.0`, `chat-pins/1.0` and
  [`disappearing-messages/1.0`](../../disappearing-messages/1.0/readme.md).**
  A reaction, pin or unpin carries the `thid` of its target. A thread in a
  conversation with a disappearing timer is subject to it like any message.
- **With `discover-features/2.0`.** A creator sends `thread-create` only to
  parties that disclose this protocol. It has no plain form, so nothing is
  sent in its place to a party that doesn't. A member who joins a group
  after a thread was created, or whose agent did not disclose this protocol
  at the time, does not learn of the thread unless a creation is sent again.
- **With `basicmessage/2.0`.** A message sent in a thread to a party that
  discloses neither this protocol nor `chat-message/1.0` is sent in its
  plain form as `chat-message/1.0` defines, which has no `thid`.
- **With `group-chat/2.0` and `1.0`.** A thread message carries the group id
  in `pthid`. A thread is not affected by a member joining or leaving.
- **With `history-sync/1.1`.** Which threads a person follows is synced
  between their devices as that protocol's `threadFollows` collection.
- **With DIDComm threading.** `thid` is used as DIDComm Messaging defines
  it: the root message began the thread, and every message in it carries the
  root's `id` in `thid`. `pthid` is the group id, as the whole chat family
  uses it; a thread is not a child protocol of the group in the spec's
  sense, and this protocol does not use `pthid` to name a parent thread.

## Message Reference

### `thread-create`

Message Type URI: `https://wyvrn.app/chat-threads/1.0/thread-create`

Headers: `created_time` REQUIRED; `thid` REQUIRED, the root's `id`; `pthid`
in a group.

| Field | Type | Description |
|---|---|---|
| `root` | message reference | REQUIRED. The message at the root of the chain; its `id` is the thread's id. SHOULD carry a `snippet`. |
| `messages` | array of message reference | REQUIRED. The chain's messages that belong to the thread, other than the root, oldest first. MAY be empty. Each SHOULD carry a `snippet`. |
| `name` | string | OPTIONAL. The thread's name, plain text, at most 100 characters. Absent: the root's label. |

Schema: [`schemas/thread-create.json`](schemas/thread-create.json) validates
the whole message, headers included.

### Messages in a thread

No new type. Any message of the chat family sent in a thread carries the
thread's id in `thid`:

| Header | Description |
|---|---|
| `thid` | The root's `id`. Its absence means the message is in the main conversation. |
| `pthid` | The group id, in a group, as outside a thread. |

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. The starting point is a new `src/handlers/chatThreads/chatThreadsHandler.ts` registered in `src/services/didcomm/messageRouter.ts`, with the thread's `thid` carried through `src/handlers/basicMessage/basicMessageHandler.ts` (the chat-message handler) and the conversation view in `src/components/chat/Conversation.tsx`.

## Endnotes

### Why creation is shared

A thread could have been a purely local view — each person folding a reply
chain up on their own screen. Then two people would see different threads
with different contents and different names, and "the thread" could not be
talked about, followed, or linked to. Making the creation a message everyone
receives gives everyone the same thread; making its contents an explicit
list, rather than "the chain as you see it", keeps them the same even when
one member is missing a reply.

### Why the thread id is the root's id

DIDComm Messaging already says a message with no `thid` is the start of a
thread whose id is its own `id`. Reusing that means a thread needs no id of
its own, a thread message needs no field of its own, and two members who
make a thread from the same chain at once collide on purpose, so that one
creation wins instead of two threads existing for one chain.

### Future Considerations

- Renaming a thread, by anyone who may create one.
- Closing a thread, after which messages carrying its `thid` are shown in
  the main conversation again.
- Nested threads, by lifting the one-level rule.
- Telling a member who joined later, or whose agent was updated, about the
  threads a conversation already has.
