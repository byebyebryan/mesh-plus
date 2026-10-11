# Mesh SDK maintenance plan

Reviewed planning checkpoint, 2026-10-10. This is proposed implementation scope,
not a new SDK guarantee, frozen contract revision or deployment selection.
The [SDK interface](sdk-api.md), [owner handoff](sdk-owner-handoff.md) and
[contract freeze](contract-freeze.md) remain authoritative.

## Decision and sequence

Make the existing SDK boundary portable to owner tests, improve diagnosis of
that boundary, then select internal optimizations from matched measurements.
Keep direct IPC/SSH state delivery and the released a11 interface as the starting
point. Observer adoption can proceed independently using today's handoff; it
does not wait for this tooling. Mesh does not implement their profiles for them.

| Phase | Deliverable | Exit gate |
| --- | --- | --- |
| M0 | Portable profile conformance kit and independent oracle tests | Installed wheel works outside a Mesh checkout; correct external profiles pass and deliberately broken ones fail; no runtime signature or frozen schema changes. |
| M1 | SDK compatibility diagnostics and a separate validity assessment | Existing acquisition diagnostics retain their meaning; bounded reports distinguish transport acquisition from current evidence without exposing records or changing producer state. |
| M2 | Matched explicit-profile measurements and one justified internal refinement | Reproducible baseline, demonstrated cost reduction, exact state/validity parity and no regression in cancellation, isolation or cleanup. No optimization is also a valid outcome. |
| M3 | Immutable package checkpoint and current documentation | Isolated wheel gates, exact inputs and exclusions, green CI, published checksum and download verification. Live selection is separate owner work. |

M0 and M1 can be released without waiting for M2. Each phase gets a bounded
review and validation before publication. Do not hold the whole sequence open
for optional optimizations or live Observer adoption.

## Review findings and validated baseline

At source `17b8096beed20eeece3d0d86e2df655d1bc1f8ed`, a11 has 39 runtime/schema
members identical to the released wheel. Its SHA-256 is
`9d3c2446b2391ab2271236804b4dfc03dfa5d29f2766d72b3d12086848b36359`.
The [planning evidence](evidence/2026-10-10-sdk-maintenance-review.json) records
fresh installed-wheel probes, 16 focused tests and differential comparison.
The preceding same-source review also passed 85 core, 119 native/SSH and 82 SSH
authority tests; their original [package evidence](evidence/2026-10-10-sdk-v1/README.md)
remains dated acceptance of those inputs.

1. `tests/test_sdk.py` proves explicit-profile networking, but imports
   `sdk_fixture` and checkout-relative contract/catalog fixtures. Neither those
   tests nor a conformance package are in the released wheel. Running them from
   another working directory succeeds only when the checkout test path is
   supplied. This is a portability gap, not a failure of the released runtime.
2. `scripts/check-sdk-compat.py` uses default reference profiles. Its 12 cases
   and 36 selections equal a10, but it does not test an owner's injected profile.
3. `doctor` reports package availability, not SDK compatibility. Binding failure
   currently becomes the safe generic diagnostic `rejected`.
4. `probe` acquires a validated snapshot or subscription baseline. It does not
   request a remote proof, evaluate expiry or apply a fleet `ReadGuard`.
   Acquisition success must retain that meaning.
5. `measure-reader.py` exercises reference codecs and imports checkout test
   helpers. It lacks an explicit-profile comparison and does not measure the
   consumer guard/current-view path. Optimizing from its worker CPU alone could
   miss validation cost in the consumer or SSH publisher.

No new transport backend or wire capability is justified by these findings.

## M0: portable owner conformance

Proposed location: an explicitly imported `mesh_plus.testing` package, with its
own conformance interface version. Keep it out of `mesh_plus.api` and ordinary
runtime imports. Review its minimal callable/DTO signatures before implementing
them; this plan does not freeze those names. Reuse standard-library `unittest`
and async fixtures rather than adding a test framework dependency.

The owner calls the kit from its own tests and passes trusted factories directly.
No module discovery, CLI plugin loader, remote code selection or native collector
is needed. Separate two suites:

- Pure profile cases: native frames, aggregate fixtures, clock evaluation points,
  expected reconstruction, complete record identities and expected current rows.
- Owned networking cases: a pure profile factory and a disposable cached
  publisher/scenario factory for local IPC, remote proof semantics, updates,
  restart and controlled failures. Mesh owns the temporary endpoints and cleanup.

The expected oracle must be supplied independently of the profile under test.
Do not generate expected receipts or eligible rows by calling the same callbacks
being checked. Mesh may include a curated fixture corpus with independently
reviewed expectations; owners add native semantic cases from their supported
facades. The standard corpus covers only supported IPC/SSH state profiles, not
every example matching a filename glob or reserved WSS/event studies.

Cases must include current, empty, warming, historical and partial source/host
views; local/fleet shape; identity/order; original receipt attribution; missing
or empty required receipts; expiry boundaries; reconstruction; descriptor,
host/source/hello binding; nonce/digest/clock forgeries; publisher restart;
gap/resync; catalog replacement; disconnect; healthy sibling preservation;
setup deadline; repeated cancellation and completed owned retirement.

Use deterministic events for race tests and explicit evaluation times for pure
expiry checks. The existing wall-clock rebinding in `sdk_fixture` is useful for
owned live IPC, but should not define the pure semantic oracle. Avoid requiring
owners to reproduce private Reader fields or Mesh's reference adapter inheritance.

Check the profile with configured source selectors and also with source `default`
used by native-only reconstruction. Native receipt source IDs remain opaque and
separate. A cached native publisher adapter may remain a reference adapter while
the owner adopts its pure profile.

Mandatory cases cannot silently skip and still certify a suite. Report stable
case IDs and pass/fail/error/skipped counts, suite version, SDK version, profile
descriptor and curated fixture digests. An invalid fixture or unrelated exception
is not successful rejection. Never include payloads, private paths or arbitrary
exception messages in a shareable JSON summary. Test failure output remains
local to the owner's runner.

Mutation validation must demonstrate detection of a broken reconstruction,
missing required receipt, overly permissive eligibility, wrong identity/binding
and lease upgrade. These are negative test controls, not runtime mutation hooks.

Package only the small required fixtures as test resources, outside the frozen
`schemas/` directory. Use `importlib.resources.files()` rather than resolving a
repository root. Python's [resource documentation](https://docs.python.org/3.11/library/importlib.resources.html)
supports installed/zip-backed resources; its
[unittest documentation](https://docs.python.org/3.11/library/unittest.html)
supports reusable suites and isolated asynchronous cases. No directory extraction
API newer than the Python 3.11 floor is required.

Acceptance requires an installed wheel and external test caller from a temporary
working directory with Mesh source/test paths absent. Test one independent
correct implementation without Observer packages and broken variants. Pin native
wheels separately for reference parity; their availability does not certify
owner extraction. Actual owned SSH acceptance is a separate labelled gate,
not the IPC-backed connector-binding test. Preserve the existing core gate.

## M1: diagnostics without changing authority

Add SDK interface/profile descriptor information to the offline package check
through an explicitly reviewed diagnostic format change. Do not claim native
compatibility from an installed package version alone. Provide a narrow allowlist
of safe binding/descriptor/lifecycle failure codes; unknown exceptions remain
redacted. Preserve the existing acquisition `probe` and its `ok` semantics.

Design a separate Reader-backed assessment before implementing its CLI spelling.
The input is explicit configured selection and cached access. It must use
`configured_reader`, the same injected profile in validation/current helpers,
and a watch guard when assessing subscription validity. Remote positives require
the ordinary nonce proof. All connections/iterators are owned and retired;
route reporting is disabled and no producer collection occurs.

The report separates acquired delivery, current evidence, partial/unavailable
hosts and expiry. A successfully acquired empty inventory is not a failure;
zero current rows alone cannot establish expired or missing evidence. Derive
receipt/delivery summaries from validated metadata rather than guessing from
row counts. Do not advertise a total deadline that excludes cleanup grace.
Review new output compatibility explicitly instead of changing diagnostics v1
or hiding assessment inside frozen Read extensions.

Acceptance: correct acquisition with stale/no-positive evidence; a current empty
inventory; partial host/source; unsupported subscribe with no poll fallback;
wrong profile/binding; disconnect/restart; deadline and repeated cancellation;
redaction and no route-health/history writes. Use owned fixtures, not live fleet
reconfiguration.

## M2: measurement before refinement

Extend the Mesh-owned harness with a trusted explicit profile factory and an
optional consumer guard/current-view workload. Compare reference and independent
profiles using identical native bodies, source receipts, proof intervals, update
cadence, readers, carrier and duration. Validate outputs before timing; the
independent semantic oracle is separate from the measured callbacks.

Use fresh processes and alternate candidate/baseline order over repeated runs.
Cover both domains, IPC/SSH, idle/update, one/multiple readers, ordinary/large
frames and fault/recovery. Start with a small descriptive matrix; enlarge only
when variance or a proposed optimization warrants it. Record harness/runtime
digests, profile/fixture versions, raw samples, cleanup and test exclusions.

Separate acquisition, validation/projection, consumer validity, serialization,
full-proof bytes and transport costs. Profiler runs diagnose hot paths and are
not timing acceptance. Worker CPU excludes some SSH work; process-tree samples
can miss short processes and peaks; framed bytes are not NIC traffic. Preserve
these distinctions. No universal performance threshold is justified yet.

Select at most one internal refinement per comparison. Prove exact native
reconstruction, receipt/lease decisions, exception behavior and lifecycle parity.
Do not cache acceptance across clock changes, proof nonces, publisher epochs,
catalog revisions or payload mutations. No measurable win means keep the simpler
implementation and publish the measurement result.

## M3: release, boundaries and coordination

Run the canonical core gate, fault lab and affected pinned native/SSH tests;
run SSH Plus's reviewed authority compatibility gate when relevant. Packaging
changes require an isolated wheel with runtime/resource parity and no checkout
dependency. Current Python floor and CI matrix remain applicable. Record skipped
tests and failures; do not convert exclusions into acceptance.

Publish a new immutable candidate with checksum/download verification, signature
and conformance-format evidence, updated current guides and owner examples.
Preserve a11 and all historical evidence. Release acceptance does not select a
live artifact or authorize Observer/SSH Plus deployment.

Mesh owns this kit, diagnostic tooling, measurements and transport refinements.
Observer agents own profiles and native semantic tests. SSH Plus is Mesh's direct
authority client; config, route-health and picker history ownership remain
distinct. Compatible work need not synchronize sibling HEADs. A native semantic,
public guarantee or frozen wire change requires separate explicit review.

Pooling, digest-proof, WSS, ordered events/replay, refresh/actions, shared brokers,
Plus migrations and producer performance remain outside this sequence. Keep all
project docs, scripts and evidence here; chezmoi receives only separately needed
deployment configuration.

## First implementation slice

Review the minimal testing surface and implement pure projection/validity cases
first, with the installed-wheel external-caller test and broken-profile controls.
Then extend that same kit to owned IPC lifecycle cases and separately gated SSH.
Complete M0 before starting a new diagnostic product or performance refactor.
