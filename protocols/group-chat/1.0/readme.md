---
title: Group Chat
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/group-chat/1.0
status: Proposed
summary: Lets a set of DIDComm peers hold a group conversation with no server or shared group state, by having each member's own agent keep a local copy of the membership list, synchronized by fan-out messages, and by fanning basicmessage/2.0 content out individually to every member.
tags:
  - messaging
  - group-chat
authors:
  - name: wyvrn
---

## Summary

Group Chat lets a set of DIDComm peers hold a many-to-many conversation
using only the pairwise mediated channels they already have with each
other — no group server, no shared/hosted group state, and no new
credential or key material beyond what each pairwise DIDComm relationship
already uses. Each member's own agent keeps its own local copy of the
group's membership list, kept in sync by the `invite` and `member-added`
messages defined here; actual message content reuses
[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0) unchanged, with
one added body field identifying which group a message belongs to.

## Motivation

DIDComm has no standard protocol for many-to-many group messaging as of
this writing. A P2P chat application built only on pairwise protocols
(`basicmessage/2.0`, `coordinate-mediation/3.0`, etc.) has no way to
represent "a conversation with more than one other party" at all. This
protocol fills that gap with the simplest design that has no
single-point-of-failure and no new trust assumptions: every member already
trusts every other member enough to have a pairwise DIDComm relationship
with them (having added them as a contact), and group membership is just
each member's own record of who else they've been told is in the group.

## Roles

There is exactly one role, `member`. Every member can send group content,
and every member can add a new member (there is no `admin`/`owner` role in
this version — see Design By Contract for the consequences of that
choice). A member learns about a group either by creating it or by
receiving an `invite`.

## Connectivity

Fully mesh, pairwise: every message defined here is sent point-to-point,
mediated, exactly like any other DIDComm v2 message between two DIDs — it
is never broadcast or routed through a third party beyond each recipient's
own mediator. A group of N members means an `invite`/`member-added` fan-out
is N-1 individual messages, and every group content message is N-1
individual pairwise sends (one to every member except the sender).

## States

| State | Meaning |
|---|---|
| `unknown` | This agent has no record of the group. |
| `member` | This agent has a local record of the group and its (locally-known) membership list. |

There is no `invited`-then-`accepted` handshake in this version: receiving
an `invite` transitions an agent directly from `unknown` to `member`, with
no consent step. See Endnotes for why, and for the future consideration of
adding one.

| Event | `unknown` | `member` |
|---|---|---|
| Create group | → `member` (as creator) | n/a (already a member) |
| Receive `invite` | → `member` | no-op (already known; see Design By Contract on stale invites) |
| Receive `member-added` | no-op (not yet a member, nothing to update) | stays `member`, local membership list updated |

## Basic Walkthrough

Alice and Bob already have a pairwise DIDComm relationship (they're
contacts). Alice creates a group and adds Bob:

1. Alice generates a `groupId` and creates a local `member` record with
   `members: [Alice, Bob]`.
2. Alice sends Bob an `invite`:
   ```json
   {
     "id": "8ba049e6-cc46-48fb-bfe0-463084d66324",
     "type": "https://wyvrn.app/group-chat/1.0/invite",
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "name": "Weekend Trip",
       "members": ["did:peer:2...alice", "did:peer:2...bob"],
       "invited_by": "did:peer:2...alice"
     }
   }
   ```
3. Bob receives it and creates a local `member` record for the group with
   the given membership list. Bob is now a member with no further action.
4. Either party sends group content by fanning a `basicmessage/2.0/message`
   out individually to every *other* member, setting the envelope-level
   `pthid` ("parent thread id") to the group's id:
   ```json
   {
     "id": "3c68cad6-00bd-496d-8cc6-4a188cb086b0",
     "type": "https://didcomm.org/basicmessage/2.0/message",
     "pthid": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
     "body": {
       "content": "anyone free saturday?"
     }
   }
   ```
   A recipient who sees `pthid` set to a group id it knows about routes the
   message into that group's conversation, with `from` as the sender,
   instead of treating it as a 1:1 message from that DID. This is a
   standard DIDComm v2 envelope field, not a custom body field --
   `basicmessage/2.0`'s own spec lists `content` as its only body attribute
   and explicitly puts both threading and group messaging out of scope for
   the protocol itself, so group membership belongs in the field the base
   spec already defines for exactly this kind of thing, not an
   unrecognized field a non-wyvrn implementation would have no way to
   interpret.
5. Later, Alice adds Carol:
   - Alice updates her own local membership to `[Alice, Bob, Carol]`.
   - Alice sends Carol an `invite` with the full 3-member list.
   - Alice sends Bob a `member-added`:
     ```json
     {
       "id": "7f960bac-42f4-4a95-9997-752f2e0ed65d",
       "type": "https://wyvrn.app/group-chat/1.0/member-added",
       "body": {
         "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
         "new_member": "did:peer:2...carol",
         "members": ["did:peer:2...alice", "did:peer:2...bob", "did:peer:2...carol"]
       }
     }
     ```
   - Bob updates his local membership list on receipt; future group
     content Bob sends now fans out to Carol too.

## Design By Contract

- **No distributed consensus.** If two members add different people at
  close to the same time, each adder's local membership list is briefly
  inconsistent with the other's until both `member-added` fan-outs have
  been delivered to everyone. This protocol does not attempt to detect or
  resolve that race — an implementation may choose to reconcile by always
  accepting the most recently received `members` list as current, but
  ordering isn't guaranteed either (see below).
- **No message ordering guarantee across the fan-out.** Because
  `invite`/`member-added`/content messages to different members are
  independent pairwise sends, there is no guarantee every member observes
  them in the same order, or that a `member-added` reaches every existing
  member before the new member's own first content message does.
- **No history for new members.** A member added after group creation
  cannot decrypt or otherwise receive messages sent before they joined —
  each `basicmessage/2.0` send in this protocol is encrypted individually
  to its recipients at send time; there is no shared group key or stored
  ciphertext a later-joining member could be given access to
  retroactively. A future "resend recent history to a new member" behavior
  is a reasonable extension but is not part of this version.
- **A stale/duplicate `invite`** (e.g. resent, or received after the
  member already knows about the group) should be treated as a no-op or,
  at most, a membership-list refresh — never as grounds to create a
  second, duplicate local record for the same `group_id`.
- **No removal.** There is no `member-removed` message in this version;
  leaving or removing a member is not yet defined.

## Security

- **No admin role, by design, means no single point of trust for
  membership changes** — but it also means any single member can add
  anyone they choose without the other members' consent, and there is no
  mechanism here to challenge or reverse that. This is an explicit,
  intentional trade-off for simplicity in this version; deployments that
  need tighter membership control should not use this protocol as-is.
- Message content confidentiality/authenticity is exactly what the
  underlying DIDComm v2 pairwise encryption between sender and each
  individual recipient already provides — this protocol adds no new
  cryptographic guarantees of its own. In particular, there is no
  group-wide shared secret; compromising one member's keys exposes only
  the messages sent to or from that one member, not the whole group's
  history.
- A malicious or compromised member can invite an unwanted party into the
  group; because every member independently fans content out to whatever
  membership list *they* currently believe is correct, there is no way for
  the rest of the group to prevent this once it's happened, short of
  manually noticing and no longer including that DID going forward (not
  itself part of this protocol).

## Message Reference

### `invite`

Sent to a DID that is being added to a group, whether at group creation or
later.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | Unique identifier for the group, stable for its lifetime. |
| `name` | string | Human-readable group name. |
| `members` | array of string | Every member's DID as of this invite, including the sender and the invitee. |
| `invited_by` | string | DID of the member who sent this invite. |

### `member-added`

Sent to every existing member (other than the new member and the sender)
whenever a member adds someone.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | The group this update applies to. |
| `new_member` | string | DID of the member who was just added. |
| `members` | array of string | The full, updated membership list. |

### Group content (`basicmessage/2.0/message`, extended)

No new message type and no new body field — the existing
[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0) `message` type,
unchanged, with the standard DIDComm v2 envelope-level `pthid` field used to
carry the group id:

| Field | Type | Description |
|---|---|---|
| `pthid` | string | The group this message belongs to. Its absence means the message is an ordinary 1:1 basic message. |

Sent individually (fanned out) to every member except the sender.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvern-cloud/wyvrn-chat) | Reference implementation — `src/handlers/groupChat/groupChatHandler.ts`.

## Endnotes

### Future Considerations

- An explicit accept/decline handshake for `invite`, instead of implicit
  auto-join on receipt.
- A `member-removed` message and a defined behavior for members leaving.
- Read receipts for group content (this version deliberately excludes
  groups from [`receipts/1.0`](https://didcomm.org/receipts/1.0) — "seen by
  whom, out of N members" needs its own design, e.g. per-member receipt
  aggregation, not just wiring the existing pairwise protocol through
  unchanged).
- Resending recent history to a newly added member.
- An optional admin/owner role for deployments that want tighter
  membership control than "any member can add anyone."
