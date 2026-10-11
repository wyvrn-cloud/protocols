# JSON-LD contexts

Vocabulary that wyvrn's credentials use and that no existing vocabulary has.
Each is published at the URL it names itself by, and does not change once
published: a change is a new version beside the old one.

| File | Published at | Used by |
|---|---|---|
| [`profile/v1.jsonld`](profile/v1.jsonld) | `https://wyvrn.app/ns/profile/v1` | The profile credential in a hosted DID's whois ([`did-hosting/1.0`](../protocols/did-hosting/1.0/readme.md#the-whois-profile)). Everything in it is schema.org but `ProfileCredential` and `background`. `name` and `description` are not in it: the credentials context already gives them, as schema.org's. |

An app carries its own copy of a context a signature depends on, and does not
fetch it.
