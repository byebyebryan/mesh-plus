# Private relay ownership/output source checkpoint

Runtime: `ea25fcb07bac14162453b0f8626aa416db10edf3`, built through source commits
`242ad2b`, `5b922ca`, `77a2e08`, and `ea25fcb` on `mesh-delta-sync-20261016`.
Observer input: immutable `af2bc7bf9316bc0fb58c83ec8f560a83788467e4`.
This is an **unfinished, unqualified source implementation**, with no wheel,
new version/encoding allocation, install, service selection or rollout.

The [implementation note](../../delta-sync-relay-implementation.md) records the
public Python API, owned close/output behavior and concrete remaining seam.
The accepted R4, G0, common input and compact R2 contract bytes are unchanged;
the previous a23 wheel and authority implementation are also unchanged.

## Bounded source results

| Check | Exact scope/result |
| --- | --- |
| Canonical Python 3.14.8 | 305 tests, zero skips; 116 design/169 delivery checks; frozen 33-input/25-schema lock and Ruff pass |
| Focused Python 3.11.17 | 15 relay tests, zero skips; also included in the 3.14 canonical run |
| Controlled source/Reader probe | Four cases on each Python version: full and active baseline/fresh proof, and invalid material for each view; zero skips/errors/failures |

The 15 focused tests disable cyclic GC and cover raw fragment preservation,
Reader independence, exact role/bridge/request checks, separate aliases,
single-consume owner isolation, live receive credit, close during scanning,
blocked output and repeated cancellation during held physical cleanup,
four-transaction preflight with a bad final header, fresh compact head
attenuation, raw LF rejection, callback replacement and reserve-capability
retirement, original capsule deadlines, and watch/capsule separation. Final
teardown checks all four heap/encoded live/reserved counters at zero.

The independent source probe uses actual supported `CachedAgentSyncSource`,
`AgentSyncTransportCodec` and `AgentSyncProfile`, with controlled native IPC and
Mesh IPC. Synthetic `ServiceState` fixtures contain three full records/two
active records. Native material is spliced verbatim. The ordinary Reader admits
the complete baseline without currentness; only its independent fresh proof
confirmation grants current receipts. Structurally valid changed bodies with
unchanged claimed roots are relayed and then rejected by independent admission.
The altered-body cases carry a 200,000-character opaque value, exercising several
bounded output chunks and strict receiving-frame handling.
Held errors survive explicit cleanup while GC is disabled; relay and Reader
ledger counters are zero afterward.

The probe's disclosed private calls are its existing test-only Reader nonce
builder and test-owned native fixture close. No private source graph, native
provider, normal service, collection or action is used. Fixture/oracle/capture
storage and the native owner's separate allocations are excluded from the
relay ledger. Its roughly 2.2 MB ordinary/2.74 MB altered-fixture peak is **not** aggregate resource,
RSS, populated-capacity or performance evidence. The four processes/runs are
correctness checks, not a serialized CPU comparison.

## Exact inputs and reproduction

[`relay-g1-source-review.json`](relay-g1-source-review.json) records 184 exported
Mesh and 193 exported Observer Python/JSON inputs, verified against the exact
commits above, plus every loaded probe module, protected hashes and all six
final log/report artifacts. These are the captured export inputs, not a claim
that the entire Observer suite ran. Both immutable export directories remain
readable on Starship at the manifest's absolute paths.

Use the selected Python with its pinned jsonschema/Ruff dependencies. From the
exact Mesh export, run the canonical gate with its `src` on `PYTHONPATH`:

```sh
rtk proxy /path/to/python scripts/check.py
rtk proxy /path/to/python -m unittest discover -s tests -p test_sync_relay.py -v
```

For the separately retained source probe:

```sh
rtk proxy /path/to/python docs/evidence/2026-10-16-delta-sync/verify_relay_source.py \
  --mesh-source /absolute/immutable/mesh-export \
  --observer-source /absolute/immutable/observer-export \
  --output /absolute/new-report.json
```

The probe refuses to overwrite its output. Earlier development and intermediate
242ad2b/77a2e08 results stay in the private `.cache` directories and are not
reattributed to this final runtime. This includes an initial probe assertion
using the wrong context key; the final assertion checks confirmed status and
current original receipts through the public context structure.
The initial large-body probe also hit its test sink's implicit 64 KiB asyncio
reader limit. The final sink uses the existing 8,470,528-byte Mesh frame ceiling;
no product cap changed. Those failed development logs remain separately retained.

## Open seam and acceptance boundaries

The source's existing `changes()` API verifies but discards native completion
bytes. The present material-chain scaffold cannot claim exact native completion
delivery, and cannot be selected as a completed transaction route. Mesh sent one
concrete supported completion-transfer review to Observer (`m118`); RLCD received
the issue (`m119`). It does not reopen A1 or request a new general go-ahead.
The [candidate additive public completion API](../../delta-sync-completion-transfer-r1.md)
makes that same review concrete; it remains unagreed and unimplemented.
Exact hello/setup/operation-request grammar and controller integration also
remain pending. No native JSON or operation schema is fabricated.

Owning runtime review, failed-shutdown quarantine, paused-watch/head concurrency,
populated full/active intake, packed recovery, original dense CPU gates, aggregate
resources/RSS, installed IPC/fixed SSH and exact paired qualification remain open.
The source tests do not establish producer readiness, close G1/G2, or select a
new artifact. Earlier input-owner and material-lifetime fixes retain their own
separate acceptance and evidence.
