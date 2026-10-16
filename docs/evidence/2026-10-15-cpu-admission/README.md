# Mesh admission CPU qualification

2026-10-15. Accepted Mesh source/private a22 candidate for independent pinned
Observer/RLCD integration. No release or production adoption.

Runtime source: `f1ced05a09124e7eaafb303c8a818301da393824`, branch
`mesh-cpu-20261015`, based on accepted a20 `c7b1d47`. The immutable
[wheel manifest](wheel.json) binds exact source/runtime/schema parity to
SHA-256 `5ac484d7dcb3f60665a66b5b6dcff780a967afa1d24a8c092800a430399f3314`.
The wheel is retained at
`/home/bryan/code/mesh-plus/dist/private/0.1.0a22-f1ced05-5ac484d7/mesh_plus-0.1.0a22-py3-none-any.whl`.
It requires Python >=3.11 and jsonschema >=4.26,<5; optional WSS retains
websockets >=17.1,<18. SDK/preparation/admission/selection interfaces are all 1;
the accepted lock remains 4. Package version does not replace these descriptors.

## Inputs and scope

The task branch starts at accepted a20 `c7b1d47`. The five profiled source modules
(`reader`, `view`, `prepared`, `protocol`, `state`) match the installed Mesh a20
hashes in RLCD's `20261015T225834Z/code-inputs.json` exactly. Its actual baseline
is Observer 0.7.0a5 / Mesh 0.1.0a20, Python 3.14.8, dashboard `358d265`, bundle
`807eab96b48825ae`. Mesh owns only its source, fixtures and package evidence.

The [API](../../cpu-admission-api.md) retains the frozen schema and wire bytes,
standalone raw admission, source cadence, remote nonce proofs, strict Client
validation and existing defaults. Local body reuse is deferred because frozen
Read rules require fresh correlated full replies for changed watch candidates.
No Observer/RLCD source, provider/session data, production endpoint, managed
package, service selection or hardware is modified.

The unmodified baseline canonical gate passes 155 standalone tests, zero skips,
on Python 3.14.8. Focused tests exercise request/profile/order/scope binding,
detached mutation, clock/expiry, full-roster exclusions, independent host expiry,
selector failures/reentrancy, fallback and combined codec checks and owned IPC
cleanup. The new fixture in `tests/fixtures/admission-selection-interface-v1.json`
records additive signatures without changing either preceding interface fixture.

Private a21 is reserved after Observer reported a historical retained candidate.
No candidate a21 wheel was built in this pass. Before reserving a22, read-only
Snap/Starship searches checked Mesh all-ref version history, retained Mesh/source
worktrees, `/tmp`, Mesh cache and Observer artifact roots, plus reviewed source
documentation, finding no prior a22 allocation. The [input ledger](inputs.json)
records the search boundary and prior-allocation provenance. No old wheel is
overwritten, and no hosted release is created.

## Acceptance

The [validation ledger](validation.json), compressed logs and
[installed input readbacks](installed-inputs.json) separate each exact environment:

| Gate | Result |
| --- | --- |
| Source canonical, Python 3.14.8 | 165 tests, zero skips, lock/read/delivery/lint pass |
| Fresh installed standalone wheel, Python 3.14.8 | 165 core + 34 WSS, zero skips |
| Fresh installed native wheel, Python 3.14.8 | 203 native + 43 native/WSS, zero skips |
| Fresh installed wheel, Python 3.11.17 | 165 core, zero skips, canonical gate pass |
| Outside-checkout installed conformance | 6 suites / 35 cases, no Observer packages, owned SSH included |

Every tested installed package manifest matches the immutable wheel. Native
runtime gates use the reviewed historical Agent 0.5.0a16 wheel and a fresh Tmux
0.6.0a5 wheel built from historical `5d8b7234ba10920beb59bde35c2f79c73d382b25`
inside this repository's disposable cache. Neither sibling checkout is modified.
Their exact hashes are in inputs.json. These legacy profile gates are separate
from the current Agent v3 pure validator used for performance and Observer's
independent new-facade acceptance.

`--check-sources` is excluded because current sibling heads differ from the frozen
source baselines. All 29 locked inputs and 22 packaged schemas retain their bytes.
An initial strict installed-conformance invocation rejected an installed venv
nested inside the checkout before executing tests; the outside-checkout rerun
passes. Draft screens and pre-freeze checks are excluded from final acceptance.

## Performance method

`scripts/measure-admission.py` compares exact work on synthetic complete Agent v3
fixtures: two hosts, 100 or 500 records, 15 changing replacements, four reads per
replacement. Selected records and all remaining current exclusion summaries enter
the semantic signature. Native-profile mode uses the same installed Observer a5
pure validation and preparation on both sides to isolate Mesh changes. Source
reads, transport, real publishers, collection and physical device are excluded.
CPU includes composition, schema/native admission, preparation, exports, reads,
selection and output signature generation. It is CPU milliseconds of exact work,
not percent CPU of a managed service. Final timing runs are serial ABBA; concurrent
gate execution and initial fixture mistakes are excluded from performance evidence.

## Installed-wheel performance

The [twelve exact timing records](performance.json) use the unchanged installed
Observer a5 pure codec/preparation on both sides, baseline Mesh a20 versus the
immutable a22 wheel. No optional combined-codec saving is included in these numbers.

| Serial ABBA case | Mean baseline CPU | Mean candidate CPU | Reduction |
| --- | ---: | ---: | ---: |
| 100 rows, owned admission + context + selected summaries | 958.02 ms | 747.44 ms | 21.98% |
| 500 rows, owned admission + context | 4672.14 ms | 3917.37 ms | 16.15% |
| 500 rows, owned admission + context + selected summaries | 4688.96 ms | 3536.59 ms | 24.58% |

Each case has two samples per variant. Every paired semantic signature agrees,
and every run completes cleanup. The 500-row selected case preserves 30,000
current row observations: 600 selected full rows plus 29,400 exclusion summaries
across sixty reads. Aggregate admissions fall from 30 to 15. Context exports
decode zero row bodies instead of 7,500. Selected queries decode only ten full
bodies per read; classification separately decodes all 500 once per generation.
The original complete roster remains available through snapshot().

These are synthetic identity-based selection rules, not RLCD domain policy.
Two samples per variant on one host with uncontrolled frequency/system activity
are not a confidence interval, memory-saving guarantee, actual managed-service
A/B or universal CPU promise. The original live 12.98% observation is not
reinterpreted as a new measurement. Transport/acquisition remain unchanged.

## Handoff and cleanup

The [machine-readable handoff](handoff.json) lists the exact APIs and acceptance
boundary. Mesh is ready for pinned upstream integration. Observer reported draft
read-interface 2 checks against Mesh source through RLCD coordination; its final
immutable package acceptance is owned by Observer and is not certified here.
RLCD owns consumer adoption, the complete-roster policy, selected pins, live CPU,
feed health, device/readback and rollback validation after both producers accept.

All owned fixture Readers/channels, native fixtures and benchmark processes
retire. No services, endpoints, native sessions, historical writer, USB, RLCD or
349 hardware were changed. Private wheel, isolated environments and bounded
non-native evidence remain for review/reproduction. No operational rollback is
needed for this source pass. A later adopter must retain and select its matched
previous Observer/Mesh/consumer tuple for rollback; upgrading source alone does
not select the new APIs or artifact.
