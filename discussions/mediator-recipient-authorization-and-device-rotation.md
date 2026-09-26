# Two open questions from building multi-device identity on `coordinate-mediation/3.0`

Both of these surfaced while designing multi-device support (one identity spanning
several devices, each with its own independent key) for a small personal DIDComm
mediator and chat client. Neither is a criticism of the spec so much as "we couldn't
find an answer in it, and want to check whether one exists before we invent our own."

## 1. `recipient-update` has no defined authorization model

[`coordinate-mediation/3.0`](https://didcomm.org/coordinate-mediation/3.0)'s
`recipient-update` lets an already-mediated party register additional `recipient_did`s
under its relationship (`action: "add"`), and remove them (`action: "remove"`). This is
clearly intentional and useful — it's how one mediation relationship supports several
pairwise DIDs, one per contact, for unlinkability.

What we couldn't find anywhere in the spec: **any requirement that a party registering
`recipient_did` prove it's actually authorized to claim it.** A straightforward reading
of the protocol (and, we found, a straightforward implementation of it) just associates
whatever `recipient_did` string is given with whichever authenticated sender sent the
`recipient-update` message — no check that the sender controls a key listed in
`recipient_did`'s own DID document, or any other proof of legitimate ownership.

Since a `recipient_did` isn't secret (it's the address a party hands out to be
reached at), this means: any two unrelated parties who've each independently completed
their own `mediate-request` against the *same* mediator can hijack each other's message
delivery, just by knowing the other's `recipient_did` — which, again, isn't secret,
it's public by design. Registering it a second time under a different owner appears to
be indistinguishable, per the spec's text, from the legitimate case of the same owner
registering an additional pairwise DID.

**Questions for the group:**
- Is there guidance elsewhere (an adjacent RFC, an implementation convention) that
  covers this we simply haven't found?
- If not: is the intended model "first claim wins, and a `recipient_did` is only as
  safe as how hard it is to guess before its rightful owner registers it" (i.e.
  security through the DID's own entropy, not an explicit authorization check)? If so,
  is that intended to be spelled out somewhere for implementers?
- Would a defined authorization mechanism (e.g. requiring a signed proof from a key in
  `recipient_did`'s own document when `owner != recipient_did`) be a welcome addition,
  or is there a reason this has been left open?

## 2. Using `from_prior` DID rotation as an ongoing device-roster mechanism

Multi-device identity, per the spec's own recommendation ("the default recipients of
the envelope SHOULD include all the `keyAgreement` entries representing Bob... This
allows Bob to decrypt his messages on any device he controls, without sharing keys
across his devices"), is naturally built as one DID document listing one independent
`keyAgreement` entry per device.

For a DID method whose value is derived from its own document content (e.g.
`did:peer`), this means *every* device enrollment or revocation changes the DID's
value — there's no way to add or remove a `keyAgreement` entry without minting a new
DID. The natural way to keep contacts up to date is `from_prior`: publish the new DID,
sign a rotation from the old one, and rely on the mechanism already defined for exactly
this ("switch from one DID to another, prove continuity").

The spec, though, frames DID Rotation as serving "a very specific and narrow need... at
the beginning of a new DIDComm Messaging relationship," not as a mechanism meant for
recurring use throughout a long-lived relationship. Repurposing it as the *routine*
mechanism for adding or removing a device — something that could reasonably happen
often over an identity's lifetime, not once at the start — doesn't seem obviously
wrong, but doesn't seem obviously endorsed either.

**Questions for the group:**
- Is there a reason `from_prior` was scoped narrowly that would make repeated,
  ongoing use of it (well after a relationship is established) unsound in practice —
  the timing/race caveats already in the spec ("care should be taken when choosing
  when to rotate... may cause lost messages if messages are arriving rapidly") read as
  more concerning if rotation is a recurring event rather than a one-time bootstrap?
- Is there existing prior art or a recommended pattern for multi-device DID/key-set
  management that we should be using instead of leaning on `from_prior` for this?
- If `from_prior` genuinely is the right tool here, is it worth a note in the spec (or
  a companion document) saying so explicitly, given its current framing reads as
  "one-time" rather than "as needed"?

---

Happy to share more detail on the actual multi-device protocol design (device
enrollment, key rotation, trust model for which devices may authorize a roster change)
if useful context for either discussion.
