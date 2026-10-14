# Changing-watch qualification and a18 candidate, 2026-10-14 UTC

## Decision and integration

The prepared path passes changing-publication qualification and remains optional.
It reduces consumer CPU in these cells while increasing transient allocation.
Existing consumers, transport defaults and wire contracts remain unchanged.
Owner preparation certification and actual consumer adoption are independent
next steps, not prerequisites for legacy networking.

Integration `8045582` combines accepted Agent v3 main `fe7e700` with prepared
branch `3bec36f`. The only conflict was the standalone suite list; both Agent v3
and prepared/simplification tests remain. Source freeze `37c3e01` advances the
private candidate to **0.1.0a18**, preserving the accepted a17 artifact. SDK 1,
optional preparation interface 1, accepted lock 4, schemas, native references,
authority and default selections remain byte-identical to their accepted inputs.
No lock regeneration or new normative wire change is included.
[Candidate CI](candidate-ci.json) passes at the exact source freeze;
[final documentation validation](final-design.json) passes 116 offline checks.
The final evidence/main commit has its own later CI result.

## Candidate and gates

[Inputs](inputs.json) bind complete runtime, lock, harness and 181 verified files
of the pinned read-only Tmux a7 installed copy, not a downloaded Tmux wheel.
Active Agent packages/checkouts and sibling source checks are excluded. Agent
v1/v2/v3 golden comparisons use independent frozen fixtures; v3 coverage was
added during integration, without certifying a native Agent preparation facade.

Private wheel: `mesh_plus-0.1.0a18-py3-none-any.whl`, SHA-256
`035f0a54a06581e702ad79cce93ecf56f3d5dcf8d28535b533c0098e97ae2098`, in
`/tmp/mesh-watch-artifacts-20261014/wheel/`. The [isolated build](build.log.gz)
creates a distinct artifact without overwriting released/prior candidates.
All runtime/schema files match source and the installed wheel byte-for-byte.

Python 3.13.7, jsonschema 4.26.0, ruff 0.16.10, websockets 17.2:

- [Canonical source](source-gate.log.gz) and [standalone wheel](wheel-gate.log.gz):
  **144 core + 34 WSS tests**, zero skips, lint, 116 Read/169 Delivery checks,
  **29 locked inputs / 22 identical packaged schemas**. The standalone wheel
  environment contains no Observer packages; Agent v3 tests remain in the suite.
- [Portable compatibility](conformance.json): **35 independent profile/network/
  actual owned SSH cases**, zero skips. This qualifies default compatibility,
  not owner preparation certification.
- [Native Tmux](native.log.gz): disposable owner/factory, private IPC, remote
  nonce-proof binding, pushed rename, source loss with watch open, prepared/legacy
  equality, disconnect and zero remaining Reader connections. Remote proof over
  IPC is synthetic. Standalone mixed-carrier tests separately compare both guards
  over actual IPC, disposable authenticated SSH and mTLS WSS fixture publishers.

The full `--native` gate requires both historical Observer packages and was not
run; neither active Agent imports nor `--check-sources` were needed. Exclusions
are not skipped tests or native Agent acceptance. Source, artifact and CI checks
do not select live services.

## Changing-publication CPU

The [earlier prepared study](../2026-10-13-prepared/README.md) repeatedly used the
same warmed publication and retains that scope. Here persistent consumers admit
changed publications, forcing full Mesh schema validation every time without
weakening the production cache or contract. Two workloads retain original source
receipt counters/expiry and input chronology:

1. **Envelope:** reader sequence/revision changes, with fixed native content.
2. **Native:** additionally change session names and native service sequence/view
   revision, recomputing remote native payload digests. The pinned pure Tmux facade
   admits these synthetic cached publications; no provider acquisition is measured.

[192 fresh-process cases](timing-cases.json.gz), **48 ABBA blocks** cover two
change kinds, 1/4 hosts, 32 rows/host and 1/4/16 reads per publication. Each trial
owns two persistent lifetimes with eight distinct publications each. The
normalized oracle compares identities, changed names and stream ordering;
volatile clock/UUID/evidence fields differ across fresh valid fixtures. An
untimed counted preflight requires eight full profile-schema admissions for
either implementation. No counters, profiler or tracing run during decision CPU,
and other local qualification workloads finish before timing starts.

Timing includes guard construction, every accept with native/proof/receipt/stream
admission, preparation, owned current results, oracle and disconnect. It excludes
fixture construction, imports/schema warm-up, collection, Reader/Bridge and
carrier I/O. Queries use actual BOOTTIME and must fit original leases; raw snapshot
exports are not part of the workload. This is consumer cost, not fleet throughput.

| Change | Hosts | Reads/publication | Median CPU reduction | Block range |
| --- | --- | --- | --- | --- |
| envelope | 1 | 1 | 7.07% | 4.72–12.98% |
| envelope | 1 | 4 | 38.51% | 37.62–40.97% |
| envelope | 1 | 16 | 66.71% | 64.68–67.43% |
| envelope | 4 | 1 | 11.01% | 10.02–11.71% |
| envelope | 4 | 4 | 39.85% | 38.23–43.71% |
| envelope | 4 | 16 | 68.10% | 67.41–69.61% |
| native | 1 | 1 | 7.05% | 5.35–10.11% |
| native | 1 | 4 | 39.68% | 37.45–43.20% |
| native | 1 | 16 | 66.33% | 64.51–66.70% |
| native | 4 | 1 | 10.31% | 9.44–13.62% |
| native | 4 | 4 | 40.24% | 38.98–41.12% |
| native | 4 | 16 | 67.20% | 42.29–68.75% |

[All blocks and ranges](timing-summary.json) are retained. The smaller single-read
gain supports keeping defaults and adopting only after owner certification and
actual workload benefit. These numbers do not establish GUI read/publication
ratios, native collection savings or whole-pipeline/network improvements.

## Allocation tradeoff

[Twelve separate process cases](memory-cases.json.gz) compare traced guard-only
allocation, excluding prebuilt inputs. One read/publication; 32 publications for
1/4 hosts and 16 for 16 hosts. Queries use fixed admitted time to isolate ownership,
not real-time cadence. Old prepared generation weak references clear after each
replacement; both paths disconnect. No history cache or global pool is added.

| Change | Hosts | Retained bytes legacy / prepared | Peak bytes legacy / prepared |
| --- | --- | --- | --- |
| envelope | 1 | 36,996 / 61,200 | 276,111 / 325,027 |
| envelope | 4 | 92,145 / 127,599 | 451,592 / 570,370 |
| envelope | 16 | 311,178 / 321,744 | 1,169,402 / 1,446,077 |
| native | 1 | 24,870 / 51,107 | 264,019 / 315,206 |
| native | 4 | 85,095 / 126,040 | 444,746 / 569,203 |
| native | 16 | 313,011 / 323,542 | 1,171,282 / 1,448,272 |

Prepared peaks are approximately **18–28% higher** here, and post-churn retained
allocations are higher. It is a CPU/ownership option, not a memory optimization.
Residual post-disconnect allocation is reported in the [full summary](memory-summary.json),
without attributing it to a leak or external cache absent further profiling.
Released generation weak references prove generation retirement only.

These are traced Python allocations, not RSS/PSS, a hard process ceiling,
maximum byte-shaped frames or unlimited churn. Existing 16 MiB generation /
32 MiB transactional-body accounting excludes transient/native/compiler/export
allocation. Caller-held exports and trusted compiler allocations remain extra.

## Independent owner handoff

The [API specification](../../prepared-consumer-api.md) defines immutable facts,
exact identity/receipt rules, version/profile binding and retirement. The fixture
compiler in tests is not a released owner facade. No consumer is automatically
migrated, and the production preparation interface has not changed in this pass.

1. Owner implements StatePreparation with an explicit implementation/package
   identity and deterministic static rules; no wall time, mutable state, provider
   I/O or actions. Existing pure profile and publisher work stays independent.
2. Independently certify complete prepared/legacy golden, partial/missing,
   multiple-receipt expiry, timing and code/version invalidation cases. Retire
   and re-admit whenever preparation/profile semantics change.
3. Opt in selected watch consumers. Wire EOF, framing/liveness failure and caller
   cancellation to disconnect. Use snapshot() for raw exports; mutable .view is
   not part of this API. Polling retains the existing APIs.
4. Measure actual read/publication ratios and complete consumer/pipeline cost.
   Select an accepted/published artifact separately, with rollback to ReadGuard.

The a18 wheel remains **unreleased and unselected**. Hosted a15 and the separately
accepted Agent v3/a17 operational tuple retain their own evidence; this pass does
not re-attest or alter live hosts. No sibling repositories, SSH Plus, chezmoi,
collectors, desktop policy or actions change. LAN/tailnet, GUI, physical suspend,
maximum-frame RSS and native Agent preparation are outside acceptance. Exact
reproduction and scope are in [the tools](../../../studies/prepared/README.md).
