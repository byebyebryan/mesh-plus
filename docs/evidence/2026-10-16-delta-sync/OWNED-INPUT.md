# Public owned-input source checkpoint

This is experimental Mesh source, not API freeze, native intake acceptance or
G1/G2 readiness. Runtime checkpoint
`1d50db0ebb92394695647458fc54ce0196ddcbf0` includes the initial implementation
`0ca3b99c7413d2542ab48ff11e8e58fb82f73d93` and a pre-construction accounting fix.
The exact public signatures, ownership states and limit/error table are in
[`delta-sync-owned-input-api.md`](../../delta-sync-owned-input-api.md), SHA256
`7f7751ecd9df93277a3e7110ca72ebfda343d38fa629cd0212ec40b3a8f1d124`.
Observer owning agreement has been requested on those bytes and remains pending.

The opt-in cache mints an epoch-bound InputOwner. Reserve/resize precede receive,
copy and parser storage. Seal transfers only exact immutable raw-buffer credit;
the original lease retains live framing/header/DTO/batch credit. Cache baseline,
transaction, batch and proof methods consume opaque refs through their complete
existing independent admission paths. Disconnect revokes handles immediately
while active receive leases and synchronous pins keep their storage charged
through cleanup. A failed foreign-alias consume cannot refund sibling credit.
Neither reservation nor seal creates semantic/current authority.

The owner control allocation itself is now prepaid before its constructor is
called. A separate at-limit regression covers this case as well as receive
allocation rejection. Close is bounded/idempotent; consumption clears borrowed
streaming aliases and saved failure frames before refunding its input pin.

`owned-input-prepay-source.json`, SHA256
`0e9447f331d0c2ccc3ed7dff8dca1d14a43447de3c802a5c3ff9638cc2e1dbf0`,
records stable before/after hashes for 144 Mesh and 79 Observer inputs on Python
3.14.8. The canonical `rtk proxy .venv/bin/python scripts/check.py` passed:
276 core tests, no skips, lock/design/delivery and Ruff gates. The independent
Observer source's existing Mesh-profile test module passed 31 tests against
these exact generic bytes. Its code was read, not edited. Logs and exact input
maps accompany the report. The earlier `owned-input-source.json` records the
275-test initial checkpoint with its own exact bytes and remains historical.

The 17 new generic tests cover seal conservation, strict immutable input,
independent baseline/proof admission, malformed/duplicate headers, four-frame
batch and unvisited-member cleanup, alias isolation, active receive credit on
disconnect, before-allocation/control-slot rejection, failed seal/consume,
callback disconnect, GC-disabled retirement and repeated cancellation. These
are source-level generic tests with fixture-owned raw input, not real Observer
source intake or a semantic full/active pair.

The requested native adapter and complete qualification remain open. Observer
must adopt the public opt-in source session and qualify paused baseline,
transaction/watch, actual full+active aliases, four transactions, head/control,
boundary/malformed/duplicate headers, failed consume, disconnect and repeated
cancellation. Intake, pending/rest, parser/DTO, batch/ticket and output storage
must be included in shared peaks; intake CPU belongs in end-to-end totals. The
existing generic acquisition controller is not yet wired to owned sessions.
No native IPC/fixed SSH, installed pair, matched CPU/bytes/RSS/plateau or package
acceptance is claimed here.

A1 relay agreement and compact codec/storage work are separate gates. The
known dense 2,000-row decoded-capacity failure and expanded native-wire failure
remain blocking. All caps, proof/absolute deadlines, Reader checks and old
contracts/schema bytes remain unchanged. No version/wheel was allocated, and
no sibling runtime, normal role, consumer, service or deployed pin was changed.
