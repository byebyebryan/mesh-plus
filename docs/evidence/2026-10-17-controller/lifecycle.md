# Actual-source controller lifecycle supplement

This adds bounded concurrency evidence for unchanged Mesh runtime
`a482abbd463d23ebf66f23c60e4e95a521c19cc6` and immutable Observer
`e3441d017b94ee27f4dfccb5f1f3f30612435adf`. It supplements the
[original controller checkpoint](README.md), without changing its bytes or
attributing its checks to another source tuple. The jointly agreed R2+R3
contract is independently recorded by coordinator `96e3927`; no further contract
approval was needed for this existing G1 work.

The [runner](verify_controller_lifecycle.py) passes **two parameterized methods /
20 scenarios on each of Python 3.14.8 and 3.11.17**, with zero failures, errors
or skips. Cyclic GC stays disabled throughout; actual returned exceptions are
retained and no explicit collection is used. Scalar outcomes and all 77 loaded
source pins match across versions. The [receipt](lifecycle.json) binds full
193-file Mesh / 211-file Observer inventories, eight protected inputs, runner,
logs and results to exact Git bytes.

| Cases per Python | Actual path and assertions |
| --- | --- |
| 4 watch scenarios | Expanded/compact × full/active. An actual native watch survives capsule end and a later 40 ms capsule's expiry. A new capsule receives the watch transaction, obtains a fresh actual head and exact independent Reader DTO, then stops that exact watch. |
| 4 wire-cancel scenarios | The controller receives cancel while a four-transaction batch is paused in output. Five distinct input buffers remain pinned/charged through cleanup; the failed connection emits only a partial prefix, no LF/result/new proof. A sibling on the same factory/source/ledger obtains a new baseline and fresh head. |
| 4 repeated server-cancel scenarios | Repeated cancellation of the owning serve task joins its operation/output cleanup before releasing physical pins. Scope revocation does not refund the five live buffers; sibling and final counters remain correct. |
| 4 source-close scenarios | Public source-session close is repeated while output is held. Its registry retires its refs immediately, but all five physical pinned buffers and distinct credits remain until unwind. Sibling session stays open and usable. |
| 4 partial-write failures | A controlled exception after an actual native body write closes the affected channel. No LF/result/new proof follows; the sibling completes actual source/Reader acquisition independently. |

The total reserved counter alone would not prove the native buffers remained
charged, because carrier and output scratch also retain credit. The final
harness additionally performs a disclosed, bounded **private storage audit**:
five exact raw buffers, five consuming records, five distinct open reservations
on the shared ledger, and each reservation's encoded amount equal to its raw
buffer length. It records scalar metadata only, retains no buffer/record from
that audit, and asserts zero such buffers after unwind. Explicit source/server
scope retirement sets their revoked flags while the raw credits remain open.
This is physical input-lifetime evidence, not a new public byte capability or an
aggregate memory/RSS qualification.

The disposable native Runtime runs with collection disabled and synthetic
ServiceState data. Actual expanded/compact source, structural codec, minted
carrier, dispatcher, relay and independent Reader participate. A test-owned
facade delegates supported source methods and records returned sessions/input
owners for audit. Drain/write hooks are installed on one writer instance to
provide deterministic test boundaries after real writes; they do not establish
populated-network slow-peer behavior. The Reader nonce helper, owning native
fixture close, factory-closed check and bounded physical-buffer audit are private
test instrumentation. Reader admission in this lifecycle runner uses an oracle
reserialization; exact original fragment preservation is the separate frozen
24-scenario runner's evidence.

The initial draft passed before the stronger physical-credit and no-LF assertions.
Both final runs include those assertions. No fail-before production defect is
claimed. Separate owner/Reader/relay accounts and oracle captures are outside an
aggregate resource measurement. Final Reader six-counter and relay five-counter
assertions pass, and native owner teardown returns to its configured base.
The test-owned caller disconnects its Reader cache on EOF and verifies that
acquisition is then unconfirmed; the sibling remains usable. This explicitly
models caller cleanup without claiming a production network Reader dispatcher.

Reproduce from fresh immutable exports and fresh output paths:

```sh
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-controller/verify_controller_lifecycle.py \
  --mesh /absolute/export/a482abb --observer /absolute/export/e3441d0 \
  --output /absolute/new/lifecycle-314.json --log /absolute/new/lifecycle-314.log
```

Repeat with the reviewed Python 3.11 environment. The receipt and saved
[3.14 result](lifecycle/314.json), [3.11 result](lifecycle/311.json) retain the
exact runs. Prior canonical 383, focused 64 and actual composition 24-per-Python
results remain at their original checkpoint and were **not rerun** here; runtime,
tests, contracts, scripts and pyproject bytes are unchanged.

This does not accept an ordinary authenticated/selected Reader route, aggregate
32/64 accounting, RSS/plateau, whole-pipeline CPU, dense 2,000-row delivery or
delivered cold/recovery, populated native providers, fixed SSH or an immutable
installed pair. The f3e3507 producer optimization and its reported CPU ceiling
failures are separate; it is not substituted for e3441d0 in this evidence.
No sibling, runtime/API/schema/ID/version/artifact/selection/service/provider or
rollout changes occurred.
