---
title: Group Chat
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/group-chat/2.0
status: Proposed
summary: Lets a set of DIDComm peers hold a group conversation with no server or shared group state, each member's own agent keeping a copy of the membership list that fan-out messages keep in sync. Adds to 1.0 an admin (the group's creator) who can remove members, hand the role on, and change the group's name, picture and settings; members who leave; and a defined way for every member to arrive at the same membership from the same messages.
tags:
  - messaging
  - group-chat
authors:
  - name: wyvrn
---

## Summary

Group Chat lets a set of DIDComm peers hold a many-to-many conversation using
only the pairwise mediated channels they already have — no group server, no
hosted group state, no group key. Each member's agent keeps its own record of
the group: its name and picture, its admin, its settings, and an ordered list
of who is in it. The messages defined here (`invite`, `member-added`,
`member-removed`, `leave`, `admin-transfer`, `update`) are fanned out pairwise
to keep those records the same. Group content is an ordinary
[`chat-message/1.0`](../../chat-message/1.0/readme.md) `message` (or
[`basicmessage/2.0`](https://didcomm.org/basicmessage/2.0)) carrying the
group's id in `pthid`, exactly as in [`1.0`](../1.0/readme.md).

What 2.0 adds to 1.0 is an **admin**. The creator of a group is its admin;
there is exactly one. The admin can remove members, hand the role to another
member, change the group's name and picture, and set who may add members and
who may pin messages. Anyone may leave. If the admin leaves without handing
over, the longest-standing member becomes admin — a rule every member can
apply to the state it already holds, so no election is needed. 1.0 had none of
this, and a group created under 1.0 stays a 1.0 group; see "Groups created
under 1.0" below.

## Motivation

1.0 was the simplest thing that worked: any member could add anyone, nobody
could be removed, nobody could leave, and two members who disagreed about the
membership had no rule for settling it. That is enough for a handful of
friends and not enough for anything else. The requests that followed were the
obvious ones — "remove this person", "I want to leave", "rename the group",
"only I should be adding people" — and every one of them needs somebody whose
word on the matter counts. This version gives the group that somebody, keeps
the power small (the admin cannot read anything a member couldn't, and cannot
delete another member's messages), and says exactly what a receiver does with
each message so that every member ends up holding the same group.

Still no server: a group is a thing each member's agent knows about, and
nothing else does. The admin is just a member whose membership messages the
others accept where they would ignore anyone else's. See Endnotes for why the
group's id is an opaque UUID and not a DID.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Roles

| Role | Description |
|---|---|
| `member` | Is in the group. Sends and receives group content; adds members where the settings allow; may leave. |
| `admin` | A member with more: removes members, transfers the role, changes name, picture and settings. Exactly one per group. |

The creator of a group is its first admin. An agent that implements this
protocol implements both roles, since any member may become admin through a
transfer or succession.

## Connectivity

Fully meshed, pairwise and mediated: every message here is sent point-to-point
to one DID, like any other DIDComm v2 message, and never routed through a
third party beyond each recipient's own mediator. A membership message to a
group of N is N-1 (or, for an `invite`, 1) individual sends; a group content
message is N-1 individual sends with the same message `id`. Group members need
not be each other's contacts — a member accepts group content from any DID on
its own member list — so a sender that wants to know what a member supports
asks that member directly with `discover-features/2.0` (see Composition).

There is no cap on a group's size. An implementation SHOULD warn the person
adding members once a group passes 50, because every message is sent that many
times.

## States

A group is, at each agent, in one of these states:

| State | Meaning |
|---|---|
| `unknown` | No record of the group. |
| `member` | Holds a record of the group and is on its member list. |
| `admin` | As `member`, and is the DID the record names as admin. |
| `removed` | Was removed by the admin. Keeps the record and the history; cannot send. Only the admin can readmit it. |
| `left` | Left of its own accord. Keeps the record and the history; cannot send. Anyone allowed to add may readmit it. |

"From the admin" below means from the DID this agent holds as the group's
admin; "reconcile" means apply the message's membership as "Reconciling
membership" under Design By Contract says. Every message named here is first
checked for authority (also under Design By Contract); one that fails is
ignored without changing state.

| Event | `unknown` | `member` | `admin` | `removed` | `left` |
|---|---|---|---|---|---|
| Create a group | → `admin` | n/a | n/a | n/a | n/a |
| Receive `invite` | → `member`; record taken from the message | reconcile (a resend or a sibling's copy; never a second record) | reconcile | from the admin: → `member`, record taken from the message; otherwise ignored | from a member allowed to add: → `member`, record taken from the message; otherwise ignored |
| Receive `member-added` | ignored (MAY be kept briefly in case the `invite` is about to arrive) | reconcile | reconcile | ignored | ignored |
| Receive `member-removed` naming this agent, from the admin | ignored | → `removed` | n/a (the admin cannot be removed) | no-op | ignored |
| Receive `member-removed` naming another, from the admin | ignored | reconcile | reconcile | ignored | ignored |
| Receive `leave` from the admin | ignored | reconcile; → `admin` if this agent is now the longest-standing member, else stays `member` | n/a | ignored | ignored |
| Receive `leave` from another member | ignored | reconcile | reconcile | ignored | ignored |
| Receive `admin-transfer` from the admin, naming this agent | ignored | → `admin` | n/a | ignored | ignored |
| Receive `admin-transfer` from the admin, naming another | ignored | reconcile; admin changed | n/a | ignored | ignored |
| Receive `update` from the admin | ignored | name, picture or settings changed | n/a | ignored | ignored |
| Receive group content from a member on the list | ignored (MAY be kept briefly) | shown | shown | MAY be shown, marked as arriving after the removal | ignored |
| Receive group content from anyone else | ignored | ignored | ignored | ignored | ignored |
| Send `leave` | n/a | → `left` | → `left`, after an `admin-transfer` or leaving succession to decide | n/a | n/a |
| Send `admin-transfer` | n/a | n/a | → `member` | n/a | n/a |

A message from the agent's own DID — a sibling device's copy under
[`multi-device/1.0`](../../multi-device/1.0/readme.md) — is applied like any
other, so that every device of one identity holds the same group.

## Basic Walkthrough

Alice and Bob are contacts, and each has learned through
`discover-features/2.0` that the other supports this protocol. Times are UTC
epoch seconds.

1. Alice creates a group. Her agent mints a group id, records itself as admin
   and as the first member, and sends Bob an `invite` carrying the whole
   record: name, admin, the ordered member list with the time each was added,
   and the settings (here the defaults, written out):

   ```json
   {
     "id": "8ba049e6-cc46-48fb-bfe0-463084d66324",
     "type": "https://wyvrn.app/group-chat/2.0/invite",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791400000,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "name": "Weekend Trip",
       "admin": "did:example:alice",
       "members": [
         { "did": "did:example:alice", "added_time": 1791399990 },
         { "did": "did:example:bob", "added_time": 1791400000, "added_by": "did:example:alice" }
       ],
       "settings": { "who_may_add": "members", "who_may_pin": "members" },
       "invited_by": "did:example:alice"
     }
   }
   ```

   Bob's agent creates its record from the message. Bob is a member with no
   further action (see Endnotes on the absence of an accept step).

2. Either of them sends group content: a `chat-message/1.0/message` sent
   separately to every other member, with the same `id` and the group's id in
   `pthid`:

   ```json
   {
     "id": "3c68cad6-00bd-496d-8cc6-4a188cb086b0",
     "type": "https://wyvrn.app/chat-message/1.0/message",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "pthid": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
     "created_time": 1791400300,
     "lang": "en",
     "body": { "content": "anyone free saturday?" }
   }
   ```

   A receiver that knows the group in `pthid` and holds the sender on its
   member list places the message in that group's conversation. To a member
   that has disclosed only `basicmessage/2.0`, the same message goes as a
   `basicmessage/2.0/message` with the same `id` and `pthid`
   (`chat-message/1.0`, Composition).

3. Bob adds Carol. The settings allow any member to. Bob's agent appends her
   to its list with the time of the add, sends Carol an `invite` with the full
   three-member list, and sends Alice a `member-added`:

   ```json
   {
     "id": "7f960bac-42f4-4a95-9997-752f2e0ed65d",
     "type": "https://wyvrn.app/group-chat/2.0/member-added",
     "from": "did:example:bob",
     "to": ["did:example:alice"],
     "created_time": 1791401000,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "new_member": "did:example:carol",
       "members": [
         { "did": "did:example:alice", "added_time": 1791399990 },
         { "did": "did:example:bob", "added_time": 1791400000, "added_by": "did:example:alice" },
         { "did": "did:example:carol", "added_time": 1791401000, "added_by": "did:example:bob" }
       ]
     }
   }
   ```

   Alice's agent adds Carol to its list. Content either of them sends now
   goes to Carol too. Carol, whose agent has never heard of Alice, asks her
   for her profile with `user-profile/1.0` (Composition).

4. Alice decides Carol should not be in the group. Only the admin can do
   this. Her agent drops Carol from its list, remembers that Carol was
   removed, and sends the same `member-removed` to Bob *and to Carol*:

   ```json
   {
     "id": "1d2c4a17-5d0e-4e6a-9d1d-3b2b4c5d6e7f",
     "type": "https://wyvrn.app/group-chat/2.0/member-removed",
     "from": "did:example:alice",
     "to": ["did:example:carol"],
     "created_time": 1791402000,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "removed_member": "did:example:carol",
       "members": [
         { "did": "did:example:alice", "added_time": 1791399990 },
         { "did": "did:example:bob", "added_time": 1791400000, "added_by": "did:example:alice" }
       ]
     }
   }
   ```

   Bob's agent drops Carol and sends her nothing further. Carol's agent keeps
   the conversation and everything in it, shows that she was removed, and
   turns off sending. Were Bob to try to add Carol back, his `member-added`
   would be ignored by Alice's agent: the admin's removal stands until the
   admin re-adds her.

5. Alice renames the group and decides that from now on only she adds
   members. An `update` carries only what changed:

   ```json
   {
     "id": "6b8e0f3a-9c2d-4f1e-8a7b-5c4d3e2f1a0b",
     "type": "https://wyvrn.app/group-chat/2.0/update",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791403000,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "name": "Weekend Trip (Sat)",
       "settings": { "who_may_add": "admin" }
     }
   }
   ```

6. Alice is going to leave the group, so first she makes Bob the admin:

   ```json
   {
     "id": "9e1f2a3b-4c5d-4e6f-8a9b-0c1d2e3f4a5b",
     "type": "https://wyvrn.app/group-chat/2.0/admin-transfer",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791404000,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "new_admin": "did:example:bob",
       "members": [
         { "did": "did:example:alice", "added_time": 1791399990 },
         { "did": "did:example:bob", "added_time": 1791400000, "added_by": "did:example:alice" }
       ]
     }
   }
   ```

   Bob's agent now holds Bob as admin; a `member-removed` or `update` from
   Alice would from here on be ignored.

7. Then she leaves, sending every other member a `leave` whose list no longer
   has her in it:

   ```json
   {
     "id": "2f3a4b5c-6d7e-4f8a-9b0c-1d2e3f4a5b6c",
     "type": "https://wyvrn.app/group-chat/2.0/leave",
     "from": "did:example:alice",
     "to": ["did:example:bob"],
     "created_time": 1791404100,
     "body": {
       "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
       "members": [
         { "did": "did:example:bob", "added_time": 1791400000, "added_by": "did:example:alice" }
       ]
     }
   }
   ```

   Alice's own agent keeps the conversation, read-only. Had she left without
   step 6, Bob's agent — and every other member's — would have made the
   longest-standing remaining member the admin on receiving the `leave`,
   with no message exchanged to decide it.

## Design By Contract

### The group record

Every member holds, for each group:

| Part | What it is | Who changes it |
|---|---|---|
| `group_id` | An opaque id, a UUID, minted by the creator; stable for the group's lifetime. | nobody |
| `name`, `picture` | Shown for the group. | the admin (`update`) |
| `admin` | The DID whose membership messages carry authority. | the admin (`admin-transfer`); succession when the admin leaves |
| `members` | Every member, with the time each was added (`added_time`) and optionally by whom. Ordered by `added_time`, earliest first; between equal times by DID, compared as strings. | adds by whoever `who_may_add` allows; removals by the admin; leaves by the member |
| `settings` | `who_may_add` and `who_may_pin`, each `members` (the default) or `admin`. | the admin (`update`) |
| removed set | DIDs removed by the admin or departed by `leave`, each with the time of that message and which of the two it was. Never sent; used to reconcile. | this agent, on applying removals and leaves |

The admin is always on the member list. A member's own DID is on its own list,
so a list has at least one entry.

### Authority

A receiver checks the authenticated sender (the DID the encryption
authenticates, allowing for rotation by a verified `from_prior`, as
`chat-message/1.0` does for its references) before applying anything:

| Message | Accepted from |
|---|---|
| `invite` | any DID, when the receiver has no record of the group; the admin, when the receiver is `removed`; a member allowed to add, when it is `left` or already a member. An `invite` whose `settings.who_may_add` is `admin` and whose sender is not its `admin` is ignored even by a receiver with no record. |
| `member-added` | any member when `who_may_add` is `members`; the admin when it is `admin`. |
| `member-removed` | the admin. A `member-removed` naming the admin is ignored. |
| `leave` | the member leaving: `from` is the DID removed. |
| `admin-transfer` | the admin. `new_admin` MUST be a member (after the message's own list is reconciled); otherwise the message is ignored. |
| `update` | the admin. |

An implementation MAY additionally refuse an `invite` from a DID the person
has no relationship with, or hold it for the person to accept (see Security).
Beyond that there is no accept step: receiving an `invite` is joining.

A receiver that has no record of a group cannot check authority for anything
but an `invite`; it ignores every other message for that group (and MAY keep
it briefly in case the `invite` is about to arrive).

### Reconciling membership

The members of a group are whoever each agent believes they are, and two
agents' beliefs can differ while messages are in flight. These rules make them
converge on the same list once the same messages have reached them, whatever
order they arrived in. Every message but `update` carries the sender's full
`members` list; the receiver never replaces its own list with it, but merges:

- **A list adds, never removes.** For each entry in the received `members`
  that the receiver doesn't hold and that is not in its removed set, the
  receiver adds it. A DID the receiver holds but the list lacks is *not*
  removed by its absence; only a `member-removed` or `leave` removes. So two
  members who each add someone at the same time both end up with both, and a
  member that missed a `member-added` learns of the addition from the next
  message that carries a list.
- **The earliest `added_time` wins.** For an entry the receiver already holds,
  it keeps the earlier of the two `added_time`s (and the `added_by` that came
  with it). Two agents that have seen the same adds therefore hold the same
  times, whichever they saw first. An `added_time` earlier than the group's
  creation — the admin's own `added_time` in the `invite` that created the
  receiver's record — is clamped to it.
- **A `member-removed` from the admin** removes `removed_member` and puts it in
  the removed set with the message's `created_time`, marked as removed by the
  admin. A `leave` removes `from` and puts it in the removed set, marked as
  having left. A removal whose `created_time` is earlier than the receiver's
  `added_time` for that DID is a stale message about an earlier membership
  (the DID has since been re-added) and is ignored.
- **The removed set wins over lists.** A DID in the removed set is not re-added
  by appearing in a `members` list — except in a list sent by the admin, whose
  entry for it has an `added_time` later than the removal. It is re-added by an
  explicit `member-added` naming it as `new_member`, or an `invite` to it, with
  `created_time` later than the removal, from a sender allowed to: the admin,
  if the admin removed it; anyone `who_may_add` allows, if it left. On
  re-adding, the DID leaves the removed set and takes the new `added_time`.
  This is what makes an admin's removal stand against a member who, not having
  seen it, keeps sending lists that still include the removed DID.
- **Admin-only changes are ordered by `created_time`, per thing changed.** For
  each of `name`, `picture`, each settings key, and `admin`, the receiver
  remembers the `created_time` of the change it applied last and ignores a
  change to that thing with an earlier one. An admin's changes MUST carry
  strictly increasing `created_time`.
- **Succession.** On a `leave` from the admin, after reconciling and removing
  the leaver, the new admin is the first entry of the receiver's list in its
  order: the earliest `added_time`, ties broken by the smaller DID as a
  string. Every member computes this from a list the admin's own `leave`
  carried, so members that have the same list choose the same admin. (An
  admin that cares who follows sends an `admin-transfer` first.) If the list
  is empty, the group has no members and the record is only history.

Equal `created_time` on two changes by the same admin to the same thing cannot
happen under the rule above; between a removal and an add of the same DID
with equal times, the removal wins.

### Groups created under 1.0

A group's protocol version is fixed when it is created: it is the version of
the `invite` that created it, and it never changes. A group created with a
`group-chat/1.0/invite` is a 1.0 group forever: no admin, any member adds, no
removal, no leaving, no settings, with 1.0's reconciliation (none). An agent
that implements this protocol and still holds 1.0 groups:

- keeps using `group-chat/1.0` messages, and 1.0's rules, for them;
- MUST NOT send a 2.0 message for a 1.0 group's id, and ignores a 2.0 message
  naming a 1.0 group (and a 1.0 message naming a 2.0 group);
- still discloses `group-chat/1.0` through `discover-features/2.0` while it
  holds any 1.0 group, so that their other members know they can still be
  reached in it;
- SHOULD create every new group under 2.0.

Group content is the same in both — `pthid` carries the group id, whichever
version the group is. A person who wants an admin for a 1.0 group creates a
new group.

### Sending

- A `group_id` SHOULD be a version 4 UUID. It is compared case-insensitively,
  like a message id.
- The `members` list a sender puts in a message is its own list after applying
  the change the message makes, in the order defined above. A receiver MUST
  NOT rely on the order it receives: it merges, and sorts.
- The `added_time` of the member a `member-added` adds SHOULD equal the
  message's `created_time`; a receiver MAY replace a later value with it.
- An `invite` MUST be sent to the new member and a `member-added` to every
  other member; a `member-removed` to every remaining member *and* to the
  removed member; a `leave`, `admin-transfer` or `update` to every other
  member. A sender that could not deliver one of these SHOULD retry it.
- A member SHOULD only add a DID that has disclosed support for this protocol
  (`discover-features/2.0`, Composition); a DID that supports only
  `group-chat/1.0` would never learn of a removal or a leave, and would add
  members in defiance of `who_may_add`. An implementation tells the person
  rather than adding such a DID.
- The group picture travels as a DIDComm attachment: `body.picture` is `#`
  followed by the `id` of an entry in `attachments[]` whose `media_type` is an
  `image/*` type and whose bytes are inline (`data.base64`), at most 256 KiB
  (the same inline limit as `chat-message/1.0`; a sender SHOULD shrink the
  picture well below it, since every `invite` carries it). `null` in an
  `update` clears the picture. The bytes are never sent by reference: an
  `invite` is a message to someone who may not yet trust anyone in the group,
  and must not make them fetch anything.
- A member that is `removed` or `left` MUST NOT send group content or
  membership messages for the group.
- Unknown body fields, unknown settings keys, and unknown member-entry fields
  MUST be ignored and, for settings, kept: an `invite` a member later sends
  carries every settings key it holds, including ones it does not understand,
  so that a companion protocol's setting reaches new members through agents
  that don't implement it.

### Accepted inconsistencies

This protocol has no consensus step, and these are the gaps it knowingly
leaves:

- A member that is offline when a removal happens keeps sending to the removed
  DID until the `member-removed` reaches it. Nothing stops the removed DID's
  agent from reading what still arrives.
- A removed member running an old or altered agent may keep sending. Every
  other member ignores group content from a DID not on its list, so it is
  heard by nobody.
- A change the old admin made just before an `admin-transfer`, arriving at a
  member after the transfer has, is ignored there: the sender is no longer the
  admin that member holds. The old admin's agent SHOULD send pending changes
  before the transfer and not after it.
- A member that never receives the admin's `leave` keeps the old admin and
  ignores the successor's admin-only messages until something — a resend of
  the `leave`, or an `invite` readmitting it — corrects its record.
- `created_time` is set by the sender, and ordering trusts it. A sender whose
  clock is wrong has its changes ordered wrongly; a sender that lies about it
  is a member that lies, which the admin's answer to is removal.

## Security

- **The sender is the DID the encryption authenticates.** Every message here
  MUST be sent sender-authenticated (`authcrypt`), and a receiver MUST ignore
  one that is not. No DID in a body — `admin`, `invited_by`, `added_by`,
  `new_member`, `new_admin`, a member entry — is authenticated by it; a
  receiver acts on `from`.
- **The admin is trusted for membership and nothing else.** The protocol's
  guarantees rest on each member's record of who the admin is, taken from the
  `invite` that admitted it. The admin can remove anyone, add anyone, and give
  the role away; it cannot read a message not sent to it, cannot send as
  another member, and cannot delete or edit another member's messages
  (`chat-message/1.0` only lets an author do that). A compromised admin can
  empty a group or fill it; members' recourse is to leave.
- **Membership is a claim an inviter makes.** As in 1.0, a member accepts
  group content from DIDs it has no relationship with, because another member
  listed them. A malicious member (where `who_may_add` is `members`) can add
  an unwanted party, and that party then receives everything sent from then
  on; the admin can remove them, and only then do messages stop. Whether an
  inviter is trusted at all is up to the receiver: an implementation MAY
  decline invites from strangers or ask the person first.
- **Removal is forward-only.** A removed member keeps every message it was
  sent, and this protocol does not pretend otherwise; no key is rotated,
  because there is no group key. It is told it was removed so that its agent
  stops, not so that it can object; it is not necessarily told why.
- **A removal says who was removed, to everyone.** Members learn that the
  admin removed a DID, and when. A `leave` likewise tells every member who
  left.
- **The removed set is why a removal holds.** Without it, any stale list from
  a member who missed the removal would reinstate the removed DID. It is local
  state and must be kept as long as the group record is.
- **Times are claims.** An `added_time` decides who succeeds a departing
  admin, and a member allowed to add could set an early one to put its own
  choice first in line. The clamp to the group's creation time bounds it; it
  does not remove it. Where that matters, the admin should restrict adding to
  itself, and should transfer the role rather than leave it to succession.
- **A group picture is untrusted bytes** sent by whoever sent the `invite` or
  `update`: treat `media_type` as a claim, decode defensively, bound the size.
- **Content confidentiality is pairwise**, exactly as 1.0: each send is
  encrypted to one recipient, there is no group secret, and compromising one
  member exposes what was sent to or from that member, not the group's whole
  history.
- **Non-repudiation is not offered.** `authcrypt` lets a recipient verify the
  sender and not prove it to anyone else.

## Composition

- **With `discover-features/2.0`.** An agent discloses
  `https://wyvrn.app/group-chat/2.0` with roles `member` and `admin` (every
  implementation plays both), and `https://wyvrn.app/group-chat/1.0` as well
  while it holds any 1.0 group. A sender in a group runs `discover-features`
  against *every member*, not only its contacts, both before adding a DID
  (does it support 2.0?) and to choose each member's form of group content.
- **With `chat-message/1.0` and `basicmessage/2.0`.** Group content is a
  `chat-message/1.0/message` — or, to a member that has not disclosed that
  protocol, a `basicmessage/2.0/message` in the plain form `chat-message/1.0`
  defines — carrying the group's id in `pthid` and sent separately to every
  other member with the same `id`. The sender chooses the type per recipient;
  one group message may go out in both forms. A receiver places a message in
  the group `pthid` names if, and only if, its sender is on the receiver's
  member list for that group (`chat-message/1.0`, "Conversations"). A
  `message-edit` or `message-delete` carries `pthid` as its target did.
- **With `receipts/1.0`.** Receipts in a group are pairwise, from each reader
  to the message's author only — never fanned out. A member that wants to know
  who has read its messages sends `request-receipts` to each member, as it
  would to a contact (an implementation SHOULD do so when it joins or when a
  member is added, if the person has receipts on), and each member that
  agrees sends it `message-receipts` for the messages it reads, naming them by
  `id`. An implementation shows who has seen a message as the profile pictures
  of up to five of those members, then a count of the rest.
- **With `user-profile/1.0`.** A new member knows the other members only by
  DID, and they it. An agent SHOULD send `request-profile` to each member it
  has no profile for when it joins or when one is added, and SHOULD answer
  such a request from any DID on a member list.
- **With `chat-pins/1.0`.** Whether a member other than the admin may pin a
  message for everyone is this protocol's `settings.who_may_pin`.
- **With `disappearing-messages/1.0`.** That protocol sets who may change a
  conversation's timer in terms of this one's admin: anyone in a group with no
  admin (a 1.0 group), only the admin once a group has one.
- **With `multi-device/1.0` and `history-sync/1.0`.** The group record,
  including the removed set and the admin, is state a person's devices hold in
  common; a device admitted later gets it through history sync, and a
  membership message a sibling device sends reaches the others as a copy from
  their own DID and is applied like any other.
- **With `group-chat/1.0`.** Side by side, never mixed: a group is one version
  for life, as above.

## Message Reference

Every message here REQUIRES `from` and `created_time`; none sets `pthid`
(the group is named in the body — an `invite` is to someone not yet in the
group's conversation). Times are UTC epoch seconds. A DID is any DID.

A **member entry**, used in every `members` list:

| Field | Type | Description |
|---|---|---|
| `did` | string | REQUIRED. The member's DID. |
| `added_time` | integer | REQUIRED. When they were added, UTC epoch seconds; for the creator, when the group was created. |
| `added_by` | string | OPTIONAL. The DID of the member who added them. |

A **settings** object. Each key is OPTIONAL; an absent key means its default.
Keys this protocol doesn't define are kept and passed on, not interpreted.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `who_may_add` | `members`, `admin` | `members` | Who may add a member. |
| `who_may_pin` | `members`, `admin` | `members` | Who may pin a message for everyone (`chat-pins/1.0`). |

### `invite`

Message Type URI: `https://wyvrn.app/group-chat/2.0/invite`

Sent to a DID being added to a group, at creation or later. Sent by any member
`who_may_add` allows.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. The group's id, a UUID. |
| `name` | string | REQUIRED. The group's name. |
| `picture` | string | OPTIONAL. `#` + the id of an inline `image/*` attachment. |
| `admin` | string | REQUIRED. The admin's DID; on the list. |
| `members` | array of member entry | REQUIRED. Every member, the sender and the invitee included, in order. |
| `settings` | settings | OPTIONAL. Absent means all defaults. |
| `invited_by` | string | REQUIRED. The sender's DID. A receiver acts on `from`. |

Schema: [`schemas/invite.json`](schemas/invite.json).

### `member-added`

Message Type URI: `https://wyvrn.app/group-chat/2.0/member-added`

Sent to every existing member except the new one, by whoever added them.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. |
| `new_member` | string | REQUIRED. The DID added; its entry is in `members`. |
| `members` | array of member entry | REQUIRED. The full list after the add. |

Schema: [`schemas/member-added.json`](schemas/member-added.json).

### `member-removed`

Message Type URI: `https://wyvrn.app/group-chat/2.0/member-removed`

Sent by the admin to every remaining member and to the removed member.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. |
| `removed_member` | string | REQUIRED. The DID removed. Never the admin. |
| `members` | array of member entry | REQUIRED. The full list after the removal. |

Schema: [`schemas/member-removed.json`](schemas/member-removed.json).

### `leave`

Message Type URI: `https://wyvrn.app/group-chat/2.0/leave`

Sent by a member leaving, to every other member. The member removed is `from`.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. |
| `members` | array of member entry | REQUIRED. The full list without the sender. |

Schema: [`schemas/leave.json`](schemas/leave.json).

### `admin-transfer`

Message Type URI: `https://wyvrn.app/group-chat/2.0/admin-transfer`

Sent by the admin to every other member. The sender is no longer admin once
it is sent.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. |
| `new_admin` | string | REQUIRED. The DID of the member who is now admin. |
| `members` | array of member entry | REQUIRED. The full list, unchanged by this message. |

Schema: [`schemas/admin-transfer.json`](schemas/admin-transfer.json).

### `update`

Message Type URI: `https://wyvrn.app/group-chat/2.0/update`

Sent by the admin to every other member. Carries only what changed; at least
one of `name`, `picture`, `settings` MUST be present.

| Field | Type | Description |
|---|---|---|
| `group_id` | string | REQUIRED. |
| `name` | string | OPTIONAL. The new name. |
| `picture` | string or null | OPTIONAL. `#` + the id of an inline `image/*` attachment, or `null` to remove the picture. |
| `settings` | settings | OPTIONAL. Each key present replaces that setting; absent keys are unchanged. |

A picture update, for reference:

```json
{
  "id": "c4d5e6f7-a8b9-4c0d-9e1f-2a3b4c5d6e7f",
  "type": "https://wyvrn.app/group-chat/2.0/update",
  "from": "did:example:bob",
  "to": ["did:example:carol"],
  "created_time": 1791405000,
  "body": {
    "group_id": "b1f6c1d2-3e4f-4a5b-8c6d-7e8f9a0b1c2d",
    "picture": "#pic"
  },
  "attachments": [
    {
      "id": "pic",
      "media_type": "image/png",
      "byte_count": 14211,
      "data": { "base64": "iVBORw0KGgo..." }
    }
  ]
}
```

Schema: [`schemas/update.json`](schemas/update.json).

### Group content

No message type of its own: a [`chat-message/1.0/message`](../../chat-message/1.0/readme.md)
(or `basicmessage/2.0/message`), and the edits, deletes, reactions, pins and so
on of the companion protocols, with the standard DIDComm v2 `pthid` header
carrying the group id:

| Header | Type | Description |
|---|---|---|
| `pthid` | string | The group this message belongs to. Its absence means a one-to-one message. |

Sent separately, with the same `id`, to every member except the sender.

## Implementations

Name / Link | Implementation Notes
--- | ---
[`wyvrn-chat`](https://github.com/wyvrn-cloud/chat) | Not yet implemented. Its `group-chat/1.0` handler (`src/handlers/groupChat/groupChatHandler.ts`) and group record (`src/types/group.ts`) are the starting point; the record gains an admin, settings, per-member `added_time` and a removed set, and the handler the four new message types and the reconciliation rules.

## Endnotes

### Why the group id is a UUID and not a DID

A DID identifies something that can act: it has keys, a document that
resolves, and endpoints at which it can be reached. A group here has none of
that. Nobody holds a key for it, nothing resolves it, no message is ever
addressed to it — every message goes to a member. An identifier for it needs
only to be unique and stable, and a UUID minted by the creator is exactly that.
It is carried in `pthid` because that is the header DIDComm already defines for
"the larger exchange this message belongs to", which is what a group
conversation is to a message in it; and a basic message's own spec puts group
messaging out of its scope, so a body field for the group would have been
illegal there.

The question has been asked whether a `did:group:`-style identifier would be
more right. Honestly: not for this protocol. A DID method defines how its DIDs
resolve to a document, and a `did:group:` DID that resolved to nothing would be
a UUID wearing a prefix — it would satisfy the grammar and none of the
purpose, and every DID-aware tool that tried to resolve it would fail. It would
also invite the assumption that the group has keys, that one could `authcrypt`
to it, that `did:group:…` could appear in `to`, none of which is true.

Where a DID *would* be right is a group that does have an agent: a
server-hosted group, where a relay holds the membership and forwards
author-signed messages to members (the shape `chat-message/1.0`'s endnotes
anticipate for community channels). That group has a document, keys and an
endpoint, and could be addressed by its DID like any other party; its
membership messages would then be sent *to* it, and `pthid` would still carry
its id — a DID string, since `pthid` is just a string. Nothing in this
protocol prevents that; a future version or a companion protocol can give such
a group a DID without changing how a message says which group it is in.

### Why the removed member is told

The removal is sent to the removed member so that its agent can stop: turn
off sending, stop asking for receipts, stop showing the group as live. An
agent that was not told would go on sending to members who ignore it, and
the person would wonder why nobody answered. Telling them costs one message
and no information beyond the fact itself; the reason, if there is one, is
between people and not part of the protocol.

### Why succession is a rule and not a message

A departing admin that sends no `admin-transfer` could be made to send one by
the protocol, but an admin can also vanish — a lost device, an identity that is
simply never used again — and then there is no message to send. A rule
computed from the member list handles both, and the longest-standing member is
the one choice every member can make from the state it has: the one with the
earliest `added_time`, which every member holds, by this protocol's rules, as
the same value. Any other rule (most active, most contacts) would depend on
state members do not share. The gap is that a vanished admin sends no `leave`
either, so succession never fires; a member who needs an admin then creates a
new group, which is the limit of what can be done without a server.

### Future Considerations

- An accept/decline step for `invite`, instead of joining on receipt; and,
  with it, a request-to-join.
- History for a new member: sending recent messages to someone just added, by
  the adder or by the admin. Each message was encrypted to its recipients at
  the time; a new member can only be sent copies.
- More than one admin, or roles between admin and member (moderators).
- Deletion of another member's message by the admin, with the message's
  author told; today only an author deletes (`chat-message/1.0`).
- A reason, shown to the removed member, on `member-removed`.
- Re-keying on removal, which needs a group key to rotate; this protocol has
  none, by design.
- A server-hosted group addressed by a DID, as above.
