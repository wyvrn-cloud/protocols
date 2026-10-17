---
title: DIDComm RPC
publisher: wyvrn
license: Apache-2.0
piuri: https://wyvrn.app/didcomm-rpc/1.0
status: Proposed
summary: Lets a controller run commands on a device it is allowed to drive, put files on it and fetch files from it, over DIDComm through a mediator, with nothing listening on the device and no port opened. Large files ride beside the messages as attachments by reference (files/1.0). Built for driving a development device (a VR headset) from a build machine that can reach the internet and nothing else.
tags:
  - remote
  - devices
  - files
authors:
  - name: wyvrn
---

## Summary

A `device` runs a small daemon that is a DIDComm agent mediated through a
mediator. A `controller` the device's owner has listed sends it messages:
run this, put this file here, give me that file, what are you, replace
yourself with this build. The device does it and answers on the same
thread. Neither side listens for anything: both reach out to the mediator,
so a device behind any network, and a controller in a cloud container, can
talk.

Small results travel inline. Anything bigger than a message goes through a
[`files/1.0`](../../files/1.0/readme.md) host and rides as a DIDComm
attachment by reference (`links` + `hash`), fetched and checked by the
receiver.

Until this protocol is proposed to didcomm.org and accepted there, it lives
under `https://wyvrn.app/`.

## Motivation

The first use is developing an app for a standalone headset from a build
environment that cannot reach it: a cloud container can open connections to
the internet only, and a headset on a home network is not on the internet.
SSH needs a path in; a CI runner on the device needs a CI service in the
loop and a repository that nobody else may push to. A mediator both can
reach is already there, and so is an identity for each, so the commands go
the way messages do: encrypted to the device, authenticated as the
controller, through a relay that reads neither.

That makes the device's daemon a remote shell reachable by anyone who can
send it a message. What stops that is the one rule this protocol is built
around: the device obeys only a sender whose key is one of the keys of a DID
its owner listed. Nothing in a message body grants anything.

## Roles

| Role | Description |
|---|---|
| `controller` | Sends commands and files, and receives results and files. A build machine, a person's laptop, an automation. |
| `device` | Runs the daemon: carries out what an allowed controller asks, on the account the daemon runs as. |

## Connectivity

Both roles are mediated DIDComm agents (`coordinate-mediation/3.0`,
`messagepickup/3.0`), typically through the same mediator, though nothing
requires that. A controller sends a request to the device's DID; the
device answers to the controller's DID, with `thid` set to the request.
Neither side has an endpoint of its own.

A device SHOULD keep a live-delivery connection to its mediator open
(`live-delivery-change`), so that a command arrives at once; it MUST also
pick up what was queued while it was away, since a request can be refused
as stale (below) but never silently lost. A controller waits for the answer
by the same means, for as long as it is prepared to wait.

Bytes that don't fit in a message go to a `files/1.0` host both can reach.
The device's owner gives the device a host and lists it there as an
uploader; the controller has its own. Each fetches what the other puts.

## States

| Role | State | Enters on | Leaves on |
|---|---|---|---|
| `controller` | `waiting` | sending a request | its answer; or giving up |
| `device` | `running` | accepting an `exec` | the command ending or timing out |

A device carries out requests one after another in the order they arrive,
unless the implementation says otherwise; a controller that wants two
things at once sends one `exec` that does both.

## Basic Walkthrough

A build machine (`did:peer:4zQmBuilder…`, whose key is listed by
`did:web:id.example:frosty:claude`) drives a headset
(`did:peer:4zQmHeadset…`).

1. It asks what the device is:

   ```json
   {
     "id": "0f1e2d3c-4b5a-4697-8877-665544332211",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/status",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:peer:4zQmHeadset..."],
     "created_time": 1792100000,
     "expires_time": 1792100300,
     "body": {}
   }
   ```

   ```json
   {
     "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/status-result",
     "from": "did:peer:4zQmHeadset...",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "0f1e2d3c-4b5a-4697-8877-665544332211",
     "created_time": 1792100001,
     "body": {
       "version": "0.1.0",
       "hostname": "frame",
       "os": "SteamOS 3.7 (aarch64)",
       "uptime_seconds": 84120,
       "load": [0.42, 0.31, 0.28],
       "disk_free_bytes": 48318382080,
       "controllers": ["did:web:id.example:frosty:claude"],
       "files_host": "did:web:files.example"
     }
   }
   ```

2. It puts a build on the device. The file is 12 MB, so it went to the
   files host first; the message carries the link:

   ```json
   {
     "id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/put",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:peer:4zQmHeadset..."],
     "created_time": 1792100010,
     "expires_time": 1792100310,
     "body": { "path": "vrm-ovrlay/frame-probe", "mode": "0755", "file": "bin" },
     "attachments": [
       {
         "id": "bin",
         "filename": "frame-probe",
         "media_type": "application/octet-stream",
         "byte_count": 12582912,
         "data": {
           "links": ["https://files.example/f/Hc3kq7vQ2mX9bL0pR5tY8w"],
           "hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
         }
       }
     ]
   }
   ```

   The device fetches the link, checks the hash, writes the file under its
   home directory, and answers:

   ```json
   {
     "id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/put-result",
     "from": "did:peer:4zQmHeadset...",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
     "created_time": 1792100014,
     "body": {
       "path": "/home/steamos/vrm-ovrlay/frame-probe",
       "byte_count": 12582912,
       "hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
     }
   }
   ```

3. It runs it:

   ```json
   {
     "id": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f80",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/exec",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:peer:4zQmHeadset..."],
     "created_time": 1792100020,
     "expires_time": 1792100320,
     "body": {
       "argv": ["./frame-probe", "record", "rec1", "--seconds", "20"],
       "cwd": "vrm-ovrlay",
       "env": { "XDG_RUNTIME_DIR": "/run/user/1000" },
       "timeout_seconds": 120
     }
   }
   ```

   ```json
   {
     "id": "e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8091",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/exec-result",
     "from": "did:peer:4zQmHeadset...",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f80",
     "created_time": 1792100043,
     "body": {
       "exit_code": 0,
       "duration_ms": 22310,
       "stdout": "device 0: distorted frames 1280x960, 1228800 bytes\nfirst frame after 310 ms: 1280x960, 1 bytes/pixel\n{\"device\":0,...}\n",
       "stderr": "",
       "truncated": false
     }
   }
   ```

4. It fetches the recording's summary, which is small, and comes inline:

   ```json
   {
     "id": "f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8091a2",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/get",
     "from": "did:peer:4zQmBuilder...",
     "to": ["did:peer:4zQmHeadset..."],
     "created_time": 1792100050,
     "expires_time": 1792100350,
     "body": { "path": "vrm-ovrlay/rec1/summary.json" }
   }
   ```

   ```json
   {
     "id": "07b8c9d0-e1f2-4a3b-4c5d-6e7f8091a2b3",
     "type": "https://wyvrn.app/didcomm-rpc/1.0/get-result",
     "from": "did:peer:4zQmHeadset...",
     "to": ["did:peer:4zQmBuilder..."],
     "thid": "f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8091a2",
     "created_time": 1792100051,
     "body": { "path": "/home/steamos/vrm-ovrlay/rec1/summary.json", "byte_count": 412, "hash": "QmZ3rJDqTp2eXRpkJ6Ws7GxLgvB1q2hAVwQpT4nUcj2hVn", "file": "f" },
     "attachments": [
       { "id": "f", "filename": "summary.json", "media_type": "application/json", "byte_count": 412, "data": { "base64": "eyJkZXZpY2UiOjAsImZyYW1lX3R5cGUiOi..." } }
     ]
   }
   ```

   The recording itself (300 MB) is fetched the same way; the device puts it
   at its files host and the `get-result` carries `links` + `hash` instead.

Had the message in step 3 come from a DID whose key no listed controller
has, the device would have answered nothing at all, and run nothing.

## Design By Contract

### Who is obeyed

- A device has a list of **controllers**: DIDs its owner wrote in its
  settings. A request is carried out only when it is sender-authenticated
  (authcrypt) and the key it was authenticated with is one of the
  key-agreement keys of a listed DID's document, resolved; a listed DID that
  equals the sender's DID counts too. A hosted DID (`did:web`, `did:webvh`)
  lets a controller be listed by a name shorter than its own DID, and lets a
  list of several controllers be kept at the host rather than on the device.
- A request from anyone else is **ignored**: no answer, not even a
  `problem-report`, so that the device gives nothing away to whoever can
  reach its DID (a mediated DID is not a secret). It MAY be logged.
- Nothing a message says changes who is obeyed. There is no message to add a
  controller; that is the device's settings, changed by whoever can change
  them on the device.

### Staleness and repeats

- Every request MUST carry `expires_time`. A device MUST NOT carry out a
  request whose `expires_time` has passed, and MUST answer it with a
  `problem-report` (`e.p.msg.expired`), so that a controller learns what
  didn't happen. A mediator queues what it can't deliver, and a device that
  was off for a day must not run yesterday's commands when it comes back. A
  controller SHOULD set `expires_time` a few minutes after `created_time`.
- A device MUST carry out a given message `id` at most once, and SHOULD
  answer a repeat with the result it already has, if it still has it: a
  mediator can deliver a message twice.

### `exec`

- `argv` is the program and its arguments, run as the daemon's user, in
  `cwd` (relative to the daemon's home directory, or absolute), with the
  daemon's environment plus `env`. A shell is a program like any other:
  `["sh", "-c", "…"]`.
- `stdin`, if given, is written to the program and closed. It is text, and
  small (at most what fits in a message).
- `timeout_seconds` bounds the run; past it the program and everything it
  started are killed and the result says `timed_out: true`. A device has a
  maximum it will grant, and a default when none is given.
- The result carries `exit_code` (absent if the program was killed by a
  signal; then `signal` says which), `duration_ms`, and what the program
  wrote: `stdout` and `stderr` as text (invalid UTF-8 replaced), **inline
  while each is at most 64 KiB**. Past that the device truncates what is
  inline, sets `truncated: true`, and MAY attach the whole of each by
  reference (`attachments` with ids `stdout` and `stderr`, and the body
  naming them in `outputs`) when it has a files host.
- A device MAY refuse an `exec` (`e.p.msg.not-allowed`) under rules of its
  own, say a list of programs, and SHOULD say so in its `status-result`.
  The reference implementation refuses nothing: the controller list is the
  whole of its access control.

### `put` and `get`

- `path` is relative to the daemon's home directory, or absolute. A device
  MUST refuse a `path` that resolves outside what it is willing to write
  (`e.p.msg.not-allowed`); the reference implementation writes anywhere its
  user may.
- `put` carries the bytes as the attachment `body.file` names: inline
  (`data.base64`) for anything up to 64 KiB, by reference (`data.links` +
  `data.hash`) otherwise. A device fetches a reference as `files/1.0` has it,
  checks the hash, and only then writes. A file that doesn't check out is not
  written (`e.p.msg.fetch-failed`). `mode` is an octal string; left out, the
  device's default. Directories on the way are made. An existing file is
  replaced unless `overwrite` is `false`.
- `get` answers with the bytes the same way: inline up to 64 KiB, else put
  at the device's files host and attached by reference. A device without a
  files host answers a large `get` with `e.p.msg.too-large`. `get` is for a
  file; for a directory the controller runs `tar` first.
- Both results say `byte_count` and `hash` of what was written or read, so
  a controller can check.

### `status`

- Answers with what the device is: the daemon's `version`, the `hostname`,
  `os`, `uptime_seconds`, `load`, `disk_free_bytes` where the daemon lives,
  the `controllers` it obeys (as listed), and its `files_host` if it has
  one. Fields a device can't say are left out. A device MAY add fields.

### `update`

- Replaces the daemon with the attached build. The attachment `body.file`
  names is the new program, by reference (it is never small); `body.hash`
  repeats the hash so that the intent is in the body as well as the
  attachment. The device fetches it, checks it, writes it beside the running
  program, makes it executable, moves it over the running program, answers
  `update-result`, and then restarts itself so that the next request is
  served by the new build. If anything fails before the move, nothing has
  changed and the result is a `problem-report`.
- A controller SHOULD follow an `update` with a `status` and compare
  `version`.

## Security

- **The controller list is the whole of it.** The device runs arbitrary
  programs as its user for anyone it obeys; being on the list is being able
  to do anything that user can. The list is kept where only the device's
  owner can write, and a listed hosted DID is only as safe as its host and
  its holder's keys. Listing a hosted DID means trusting the host not to
  change its document; a `did:webvh` is verifiable and preferable to a
  `did:web`.
- **Silence to strangers.** A device answers nothing to a request it won't
  obey, so an attacker who has its DID learns nothing from it: not that it
  exists, not what it runs.
- **Freshness.** `expires_time` is required and honoured, and ids are
  carried out once, so a queued or replayed request can't act later than
  its sender meant.
- **Fetched bytes are checked** against the hash in the message before they
  are written or run. The files host is trusted to keep bytes, not to be
  honest about them. A `put` or `update` whose bytes don't match the hash
  does nothing.
- **What travels through the mediator** is encrypted to the receiver and
  authenticated by the sender, as any DIDComm message; the mediator sees
  sizes and timing. The files host sees file sizes and names, and the
  bytes unless the controller encrypts them (`files/1.0`).
- **The daemon's own keys** are on the device, readable by its user. Whoever
  has them can receive the device's commands, which is to say: can read what
  the controller sends it, including files. They are not a way to become a
  controller.
- **A device should not be a controller's only gate.** A build environment
  that is a controller holds a key that can run anything on the device; it
  should hold nothing else of value.

## Composition

- **With `files/1.0`.** Every large transfer: a controller's `put` and
  `update` carry a file it uploaded; a device's `get-result` and a large
  `exec-result` carry one it uploaded. Each side is an `uploader` at a host
  of its own choosing; the other side only fetches.
- **With DIDComm attachments.** The attachment shape is the specification's:
  inline `data.base64`, or `data.links` with `data.hash` (a base58btc
  multihash of the bytes), plus `filename`, `media_type` and `byte_count`.
- **With `coordinate-mediation/3.0` and `messagepickup/3.0`.** Both sides
  are mediated; a device keeps live delivery on and picks up what was
  queued. A `from_prior` is not used: a device is listed by its controllers'
  keys, which survive a controller's change of DID.
- **With `discover-features/2.0`.** A device discloses nothing to anyone
  not on its list (it answers them nothing at all); to a controller it
  discloses `https://wyvrn.app/didcomm-rpc/1.0` with role `device`.
- **With `report-problem/2.0`.** Refusals to a controller are
  `https://wyvrn.app/didcomm-rpc/1.0/problem-report` with the codes below.

## Message Reference

Every request is from a `controller` and MUST be sender-authenticated and
carry `expires_time`. Every answer is from the `device`, with `thid` set to
the request's `id`.

### `exec`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/exec`

| Field | Type | Description |
|---|---|---|
| `argv` | array of string | REQUIRED, at least one. The program and its arguments. |
| `cwd` | string | OPTIONAL. Where to run it; relative to the daemon's home, or absolute. |
| `env` | object | OPTIONAL. Variables to set, over the daemon's own. |
| `stdin` | string | OPTIONAL. Written to the program, then closed. |
| `timeout_seconds` | integer | OPTIONAL. Killed after this many seconds. The device's default when left out, and at most its maximum. |

Schema: [`schemas/exec.json`](schemas/exec.json).

### `exec-result`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/exec-result`

| Field | Type | Description |
|---|---|---|
| `exit_code` | integer | OPTIONAL. The program's exit code; absent when it was killed by a signal. |
| `signal` | integer | OPTIONAL. The signal that killed it, when one did. |
| `timed_out` | boolean | OPTIONAL. `true` when the device killed it at `timeout_seconds`. |
| `duration_ms` | integer | REQUIRED. How long it ran. |
| `stdout` | string | REQUIRED. What it wrote, as text, at most 64 KiB inline. |
| `stderr` | string | REQUIRED. Likewise. |
| `truncated` | boolean | REQUIRED. Whether either was cut to fit. |
| `outputs` | object | OPTIONAL. When truncated and the device could upload: attachment ids under `stdout` and `stderr`, each an attachment by reference holding the whole of it. |

Schema: [`schemas/exec-result.json`](schemas/exec-result.json).

### `put`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/put`

| Field | Type | Description |
|---|---|---|
| `path` | string | REQUIRED. Where to write; relative to the daemon's home, or absolute. |
| `file` | string | REQUIRED. The id of the attachment holding the bytes. |
| `mode` | string | OPTIONAL. Octal permissions, `"0755"`. |
| `overwrite` | boolean | OPTIONAL. Default `true`. |

Schema: [`schemas/put.json`](schemas/put.json).

### `put-result`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/put-result`

| Field | Type | Description |
|---|---|---|
| `path` | string | REQUIRED. Where it was written, absolute. |
| `byte_count` | integer | REQUIRED. |
| `hash` | string | REQUIRED. Base58btc multihash of what was written. |

Schema: [`schemas/put-result.json`](schemas/put-result.json).

### `get`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/get`

| Field | Type | Description |
|---|---|---|
| `path` | string | REQUIRED. The file to read; relative to the daemon's home, or absolute. |

Schema: [`schemas/get.json`](schemas/get.json).

### `get-result`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/get-result`

| Field | Type | Description |
|---|---|---|
| `path` | string | REQUIRED. What was read, absolute. |
| `byte_count` | integer | REQUIRED. |
| `hash` | string | REQUIRED. Base58btc multihash of the bytes. |
| `file` | string | REQUIRED. The id of the attachment holding the bytes: inline up to 64 KiB, by reference otherwise. |

Schema: [`schemas/get-result.json`](schemas/get-result.json).

### `status`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/status`

The body is empty.

Schema: [`schemas/status.json`](schemas/status.json).

### `status-result`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/status-result`

| Field | Type | Description |
|---|---|---|
| `version` | string | REQUIRED. The daemon's version. |
| `hostname` | string | OPTIONAL. |
| `os` | string | OPTIONAL. |
| `uptime_seconds` | integer | OPTIONAL. The machine's. |
| `load` | array of number | OPTIONAL. 1, 5 and 15 minute load averages. |
| `disk_free_bytes` | integer | OPTIONAL. Where the daemon lives. |
| `controllers` | array of string | REQUIRED. The DIDs it obeys, as listed. |
| `files_host` | string | OPTIONAL. The `files/1.0` host it uploads to. |

Schema: [`schemas/status-result.json`](schemas/status-result.json).

### `update`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/update`

| Field | Type | Description |
|---|---|---|
| `file` | string | REQUIRED. The id of the attachment holding the new program, by reference. |
| `hash` | string | REQUIRED. Its base58btc multihash, repeated in the body. |
| `version` | string | OPTIONAL. What the controller believes it is, for the log. |

Schema: [`schemas/update.json`](schemas/update.json).

### `update-result`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/update-result`

| Field | Type | Description |
|---|---|---|
| `hash` | string | REQUIRED. Of what is now in place. |
| `restarting` | boolean | REQUIRED. `true`: the device restarts right after answering. |

Schema: [`schemas/update-result.json`](schemas/update-result.json).

### `problem-report`

Message Type URI: `https://wyvrn.app/didcomm-rpc/1.0/problem-report`

Sent only to a controller the device obeys, as `report-problem/2.0` has it.

| Code | Meaning |
|---|---|
| `e.p.msg.expired` | The request's `expires_time` had passed when it arrived. Nothing was done. |
| `e.p.msg.invalid` | A field is missing or malformed. `args`: which. |
| `e.p.msg.not-allowed` | The device's own rules refused it (a path, a program). |
| `e.p.msg.not-found` | No such file (`get`). |
| `e.p.msg.fetch-failed` | An attachment by reference couldn't be fetched, or didn't hash to `hash`. Nothing was written. |
| `e.p.msg.too-large` | The bytes don't fit inline and the device has no files host. |
| `e.p.msg.failed` | The device tried and couldn't. `args`: why. |

## Implementations

Name / Link | Implementation Notes
--- | ---
[`didcomm-rpc`](https://github.com/frostyfrog/didcomm-rpc) | `didcomm-rpcd`, the `device` role, as a user systemd service on a Steam Frame; `didcomm-rpc`, the `controller` role, as a CLI. Both roles' uploads through `files/1.0`.

## Endnotes

### Why not SSH over a tunnel

It would work, with a relay that both sides connect to and that forwards a
TCP stream. That relay would be one more thing to run, and SSH's keys and
`authorized_keys` would be one more identity to manage beside the DIDs
everything else here already has. A DIDComm message is a request with a
sender, and a mediator is a relay that already exists: the shortest path
was to use them.

### Why strangers get silence

A `problem-report` to an unlisted sender would confirm the DID is a device
of this kind, and invite more. The cost is that a controller whose key fell
off the list sees a timeout rather than a refusal; a `status` from a DID
that is still listed tells it why.

### Future Considerations

- Streaming a long-running command's output as it happens, as ordered
  messages in the request's thread (Advanced Sequencing's `sender_order`),
  so that a controller can watch and cancel.
- `cancel`: stopping a running `exec` by its thread.
- A device-side allowlist of programs and paths, for a device whose owner
  wants a controller to do less than everything.
- A controller running a session: several commands sharing one shell and
  its state.
