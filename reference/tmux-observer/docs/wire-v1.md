# Version 1 wire rules

The three bundles under `contracts/` define structure. These rules define
semantics. Use both; schema validation alone cannot establish freshness or
native acceptance. `scripts/read-contract` is an independent acceptance reader
and does not import the producer package.

Each wire record is strict UTF-8, one JSON value on one line and one final LF.
Duplicate keys, BOM, trailing data/whitespace, NUL, nonfinite numbers and invalid
Unicode are rejected. Integers are bounded by signed 63-bit magnitude; known
counters are nonnegative integers, never booleans. Strings contain no ASCII
control characters or DEL and are at most 16,384 characters. A tree has at most
32 nested containers and 100,000 nodes, including object keys. Unknown fields
are permitted within these bounds and grant no capabilities or authority.

Observation and fleet view records are at most 1 MiB including LF. Service and
fleet frames contain an optional view plus at most 16 KiB of envelope, and are
at most 1 MiB + 16 KiB. Requests, tickets and operation errors are at most
16 KiB. Limits apply to exact encoded bytes, including unknown extensions.

`observation-v1/schema.json` describes a fresh host-local read. `source` fixes
the logical host ID, UID and `default` server; native hostname is diagnostic.
The native adapter fixes `tmux -L default`, clears inherited `TMUX`/`TMUX_PANE`,
and captures `TMUX_TMPDIR` and the execution environment at adapter startup.
It never follows an ambient alternate socket. Public CLI requests offer no
socket, executable or arbitrary tmux format selection.
The full session reference is `(hostId, serverGeneration, sessionId, createdAt)`.
Generation is opaque text, preserved exactly. Session IDs are unique within
an owner document. Creation/activity/attachment times are Unix seconds;
`sample.observedAt` is Unix milliseconds. All other clocks are milliseconds of
Linux `CLOCK_BOOTTIME`, scoped by boot ID and time namespace. Cross-host clocks
must never be subtracted. Nullable metadata means unavailable, not zero.

Complete coverage has no error. Failed, partial or unsupported coverage has an
error, null generation and no authoritative rows. A verified absent server is
complete coverage with null generation and no rows. These cases are distinct.
`capabilities` fixes the requested profile. Optional pane and option fields
appear only when requested; every option key is present, with null for absent
and empty text for a set empty value. At most 256 sessions and 512 total panes
are accepted. Observation never exports viewer/action handles or close safety.

`service-v1/schema.json` describes an owner delivery frame. Publisher UUID
identifies a service incarnation; it is independent of tmux generation. Sequence
is per connection, starts at zero and identifies stream order; a skipped queued
update produces a gap frame. One-shot reads have their own connection/sequence.
View revision identifies material changes. Neither
delivery nor heartbeat renews native evidence. A warming publisher has no
accepted sample and no snapshot. A failed publisher can retain a previous
complete snapshot as historical data. Ready receipts bind to the retained
sample's start, finish and clock domain. `accepted` counts complete native
samples, `attempted` counts started reads and `acceptedAttempt` identifies the
accepted attempt. Attempt counters do not reset until publisher restart.
`lastAttemptResult` retains the most recent finished result while a new attempt
is in flight. The first unfinished attempt uses `none`.

Owner validity expires at `startedAt + leaseMs`, never finish or delivery time.
Lease is at most 10,000 ms. At encoding, ready `remainingMs` equals
`max(0, expiresAt - encodedAt)` and is positive; every nonready receipt has zero
remaining validity. Ready service snapshots use the fixed minimal profile:
no panes and no arbitrary options. Clients guard expected source, publisher,
clock, sequence and request nonce in addition to validating a frame.

`fleet-v1/schema.json` is the composed view; `frame.schema.json` wraps it in
stream/control metadata. Embedded views bind to the frame's reader UUID,
desktop context, clock, encoding time and view revision. A ready mesh has a
route revision and exactly one local host, first. `local_only` has one host and
no route revision. A prepared ready view has at most 16 owners. Catalog failure
retains historical data without current routing/fleet authority.

Remote owner clocks remain in their original domain. Only a response to a
matching probe establishes local expiry. For locally measured send `t0` and
receive `t1`, remote remaining validity `r` and margin `m >= 100 ms`, the bound
is `t1 + max(0, r - (t1 - t0) - m)`. Round trips exceeding 2,000 ms are rejected.
Proof receipt cannot be in the future. Material unsolicited updates are
candidates requiring proof; heartbeats and cached arrival cannot extend a
positive receipt. Negative failures can invalidate an existing receipt.

Desktop evidence has its own context, epoch, input hash and lease. `open` and
`none` require both current owner and current desktop evidence. An unknown
desktop never proves absence. Open confidence is `confirmed` for exact evidence
or `matched` for a qualified association; matched requires positive owner
attachment count. These are display facts and provide no close/action authority.

Requests select fixed configured sources, never executable paths, sockets or
cadence. Status/snapshot/watch/probe reads do not schedule native collection.
Explicit refresh returns a bounded ticket. A successful source names a native
attempt; only samples causally eligible after ticket acceptance can satisfy it.
An older in-flight read needs a successor. Mixed outcomes are failed with
per-source results. Terminal tickets have no outstanding work. Ticket UUID and
publisher/reader UUID are both required for later lookup. Deadline is at most
15,000 ms after acceptance. Restart makes old tickets stale, not complete.

Typed `operation_error` records are separate from observations and frames;
they convey invalid requests or unavailable services without fabricating an
empty native roster. Error codes are bounded open tokens and messages are
diagnostics, never instructions. Readers may accept unfamiliar bounded codes.
