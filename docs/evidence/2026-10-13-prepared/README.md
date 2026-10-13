# Prepared consumer candidate qualification, 2026-10-13

## Decision and scope

Implement the user-authorized additive [prepared interface 1](../../prepared-consumer-api.md)
through SDK 1, preserving legacy behavior, defaults, lock 3, frozen schemas and
authority bytes. Runtime checkpoint `4406dc8` hardens exact descriptor bindings and freezes
additive signatures; `b70d938` adds the reentrancy barrier;
`c0145da` corrects qualification fixtures. This branch extends the earlier
`cd4acc5` simplification and `54a09b8` ownership study; shared main `c4ec7ca`
and published a15 are separate inputs, not changed operational selections.

The preparation owner explicitly promises generation-static rules. Existing
profiles are not implicitly certified. Mesh admits once, compiles from deeply
immutable native facts, seals original row bytes and derived original expiry,
and releases transient native state. Query exports own their dictionaries.
Gap/error/disconnect, clock/binding failures, cancellation, malformed rules and
failed replacement retire positives. No unchecked fallback or new transport.

## Source, private wheel and compatibility

[Inputs](inputs.json) bind source/runtime, harness/test hashes and 181 verified
files of the read-only Tmux a7 installed copy. This is an installed snapshot of
`/home/bryan/.local/share/tmux-observer/python`, not an independently downloaded
Tmux wheel. No Agent development checkout or package was used.

Private Mesh wheel: `mesh_plus-0.1.0a16-py3-none-any.whl`, SHA-256
`68c0f17ddde616e79de14c36bdccc923708ef317316aa21acbba56353832ec3f`.
It lives in a new private artifact directory; it does not overwrite an earlier
candidate or released artifact. Whole runtime/schema parity against source
passes. Relative to the preceding simplification wheel, only `api.py`, `view.py`
and the added `prepared.py` change. Packaged schemas and `authority.py` are
byte-identical. The version label alone does not distinguish these candidates.

Python 3.13.7, jsonschema 4.26.0, ruff 0.16.10, websockets 17.2:

- [Canonical source gate](source-gate.log.gz): 140 core tests, 34 standalone WSS
  tests, 116 Read checks, 169 Delivery checks, lint, 25 locked inputs and 21
  identical packaged schemas; zero skips.
- [Isolated installed-wheel gate](installed-gate.log.gz): same counts and zero
  skips, without Observer packages. Imports use the installed wheel under `-I`.
- [Portable compatibility conformance](conformance.json): 35 profile/network/
  owned SSH cases, including both independent frozen domain fixtures; zero skips.
- The additive signature fixture is checked separately from the preserved
  legacy SDK fixture; final source/signature validation is archived below.

The first canonical attempt correctly rejected the newly added exports in an
exact-export assertion. The test now explicitly allows the six reviewed additions
while preserving the old export/signature fixture bytes. A scope test initially
queried after its mock compiler binding was restored; it now checks inside the
bound lifetime. Neither finding required weakening runtime admission.

## Native and transport acceptance

Actual pinned Tmux a7 factory, pure facade and disposable owner run through a
private IPC bridge, fresh remote nonce proof and Reader watch. Prepared/legacy
rows agree during baseline and pushed rename. Final qualification also checks
source loss while the watch remains open, no positives after disconnect, failed
snapshot after owner termination and zero remaining Reader connections.
[Initial native gate](native-initial.log.gz) retains its earlier scope; the final
[native log](native-reviewed.log.gz) is separate. This remote proof is over IPC, not a native SSH route.

The standalone mixed-carrier WSS test now compares both consumers on real IPC,
authenticated disposable SSH stdio and mTLS WSS watch frames, including publisher
updates and disconnect. Both domains there use independent frozen native
fixtures. This does not certify active Agent semantics or a published owner
preparation facade. The actual Tmux native case is independent of those fixtures.

## Matched complete consumer timing

[96 fresh-process trials](cases.json.gz), four ABBA blocks per cell, compare the
legacy and prepared paths using the same installed candidate/pinned Tmux facade.
Eight complete consumer lifetimes per trial, 32 rows/host, identical identities,
admissions/queries and teardown. CPU includes construction, full admission,
immutable input, test compiler thaw/allocation, preparation, owned results,
identity oracle and disconnect. Imports/schema warm-up and source/carrier I/O
are outside timing. No profiling, counters, allocation tracing or concurrent
acceptance workloads run inside decision timing. Original leases must hold.

| Hosts | Reads per publication | Median consumer CPU reduction | Four-block range |
| --- | --- | --- | --- |
| 1 | 1 | 18.63% | 18.22–19.12% |
| 4 | 1 | 23.09% | 22.09–23.43% |
| 1 | 4 | 58.43% | 57.85–59.53% |
| 4 | 4 | 59.46% | 57.94–60.07% |
| 1 | 16 | 76.54% | 75.91–76.76% |
| 4 | 16 | 77.55% | 77.32–78.01% |

[Summary and harness hashes](summary.json) retain every block. Unlike the earlier
double-admission study, this implementation shows consumer benefit even at one
query in these cells. It does not establish whole-pipeline savings, actual GUI
read/publication ratios, or a reason to silently change defaults. Static owner
certification remains necessary regardless of measured speed.

## Allocation, replacement and failure evidence

[Allocation report](memory.json) and [progress log](memory.log.gz) cover 128
replacements per cell. Old-generation and disconnect weak references clear;
retained allocations remain within 128 KiB of the initial steady reading. Raw
views, native DTOs and requirement sets are not retained by Mesh preparation.

| Hosts / rows per host | Serialized retained body | Initial steady traced bytes | After churn | Peak including replacement/exports |
| --- | --- | --- | --- | --- |
| 1 / 32 | 12,192 | 18,033 | 82,042 | 398,229 |
| 4 / 32 | 48,270 | 66,359 | 130,884 | 687,606 |
| 16 / 32 | 192,798 | 261,071 | 330,381 | 1,814,480 |
| 1 / 256 | 82,752 | 116,993 | 180,205 | 1,114,961 |

Retirement leaves approximately 62–68 KiB of traced allocations in these cells, not retained
generations; this report does not assert zero global Python/cache allocation.
The serialized body ceiling is 16 MiB per generation and 32 MiB for old/new
transactional bodies. Transient native/frozen/compiler inputs, Python overhead,
decoded exports and caller-retained results are additional allocations. These
cells do not exercise every maximum byte-shaped frame or promise a hard RSS/PSS
ceiling/global memory pool. Tracing is separate from CPU decision measurements.
Churn queries use fixed admitted time to isolate ownership, not runtime leases.

The [rejected first memory fixture](rejected-memory-fixture.log.gz) attempted
1,024 rows/host, exceeding Tmux's 256 native row limit. Full native admission
rejected it. Initial candidate reports are archived with the initial- prefix and wheel
SHA-256 in initial-inputs.json; final measurements use the tightened wheel.
The corrected fixture preserves that native limit; the rejection
is not hidden or counted as a passed allocation trial.

## Handoff and remaining gates

Mesh's additive implementation and controlled qualification pass.
[Final documentation validation](final-design.json) passes 116 offline checks;
[runtime checkpoint CI](runtime-ci.json) passes on the pushed `4406dc8` bytes.
The final documentation commit has its own later CI result. Run the
[reproduction tools](../../../studies/prepared/README.md) with exact inputs.

1. Owner publishes a reviewed preparation facade with explicit implementation/
   package identity and static-rule promise. Certify golden, partial/missing,
   expiry, future timing and code/version invalidation independently. Tmux first;
   Agent can do this independently of current profile-only development.
2. Measure complete actual consumer lifetimes and read/publication ratios, then
   explicitly opt in where useful. Existing consumers remain fully supported.
3. Separately review publication/version selection and operational rollout with
   rollback to ReadGuard. No source refactor selects or deploys a release.

Excluded: Observer repository edits, Agent development imports/native collection,
Tmux/Agent Plus migration, SSH Plus/deployment changes, ordinary fleet LAN/tailnet
performance, physical suspend, GUI acceptance, cross-Python native prepared
owner certification and live adoption. `--native` and `--check-sources` were
deliberately not run: the full native gate requires both historical producers,
whereas this pass uses pinned Tmux only and independent Agent fixtures. No
skipped tests are counted as acceptance. Frozen references and dated prior
evidence remain unchanged.
