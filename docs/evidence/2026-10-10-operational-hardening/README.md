# Operational hardening and measured next decision

The narrative below records the initial source checkpoint. Subsequent candidate
and adoption work is recorded separately so earlier acceptance retains its
exact runtime bytes.

This pass follows the coordinated a9 adoption. Mesh source checkpoint
`504a176d9d9037634465ef1ab7a71988f317ca60` introduces an **a10 candidate**, not
a released or deployed cohort. Snap and Starship retain the accepted Mesh a9,
Tmux Observer a4 / Plus a4 and private Agent reader a13 / bridge a12 selections.
Collector/writer selection, source receipts, native sessions and desktop policy
are outside the transport changes.

## Concrete findings

1. Python 3.14 logs a late subscription-admission shield-future exception when
   cancellation meets `ended(cancelled)`. The new real-IPC regression fails on
   installed a9 and passes on source and isolated a10 wheel. Waiting for the
   admission future without a shield wrapper preserves cancellation, observes
   terminal outcomes and keeps independent requests usable.
2. A single `LibraryMeshAuthority` admits one filesystem read. Sharing it between
   four independently monitored Readers makes their concurrent catalog checks
   fail with `catalog_busy`. The profiling harness now owns one adapter per
   Reader. This is a harness ownership correction, not an authority relaxation.
3. Installed Mesh-backed refresh repetitions expose two failures in 400 trials.
   A detailed failure contains a valid, matching `refresh_result` after the
   coordinator's native owner scope changed. The Tmux control source now rejects
   changed epoch/scope/route bindings with `stale_scope`; installed a4 fails the
   three deterministic binding-change cases. The trigger for the occasional
   scope revocation remains open. A later 100 delivery-instrumented repetitions
   pass; that does not establish a root cause or fix the intermittent revocation.
4. The private Tmux bridge allowed only one handler. Client closure can precede
   publisher retirement, so rotation can collide with that retiring slot. A
   deterministic real-IPC fixture with 100 ms delayed retirement incurs three
   failed setups over three rotations on the one-slot source and none with an
   active-plus-retiring bound of two. The Tmux source and owned profiling bridge
   now provide that bounded headroom; the general IPC server policy is unchanged.

Tmux source also admits the exact a10 candidate explicitly and keeps its library
authority path. The initial six owned Mesh coordinator/native tests pass with the isolated
a10 wheel. The source dependency and deployed a4 artifact still select a9.
Agent's archived-artifact verifier continues to reject a10 until its next exact
manifest and immutable Observer artifact are reviewed together.
The a10 pairing also passes 200 additional owned grouped-refresh trials; passing
exposure does not close the original revocation finding.

Fixture teardown itself invalidates owner associations. Its counted
`stale_scope` events must not be treated as refresh failures. Earlier legacy
fixture exposure did not exercise Mesh and is excluded from Mesh acceptance.

## Measurement scope and decision

Private cached native inputs contain seven Tmux sessions and 128 Agent records.
Replay retains original receipts and expiry, grants no new native truth and
never publishes the input records. Hashes identify the inputs. Serial matrix
cases compare identical inputs/cadence for IPC and owned localhost SSH, one/four
independent processes, idle/one-second replacement updates, and polling/watch.
Watch and snapshot reports have separate harness digests.

Each independent SSH worker owns a disposable carrier fixture. Its full owned
RSS therefore includes fixture/setup overhead and cannot quantify a production
shared-broker saving. Steady worker CPU excludes SSH publisher CPU, whereas an
IPC publisher shares the worker; it cannot rank carriers by total CPU. The
reports preserve these boundaries. Ordinary host load and concurrent soak work
are uncontrolled; these are descriptive measurements, not an optimization A/B.

The instrumented Agent trace identifies pure native shape/text validation as
substantial repeated work. Instrumentation adds overhead; hotspot times are not
unprofiled production latency. Separate live four-Reader profiles on both hosts
also pass, with a larger fleet inventory than the private local replay input.
Their resources include consumers and local descendants, excluding ordinary
collectors and remote bridges.

**Decision:** retain direct IPC/SSH. Prioritize bounded Agent pure-validator
profiling and compatible implementation improvements before a new transport.
One compatible improvement is implemented in Agent source: an ASCII regex scan
with unchanged non-ASCII Unicode-category validation. All 128 ASCII characters,
Unicode category/boundary cases and spoofed string subclass admission have
regressions. ABBA validation of the identical 128-row snapshot uses 31.2% less
process CPU; this is pure validation cost, not whole-fleet or collector savings.
Agent's 448-test Mesh/jsonschema-enabled source gate passes without skips;
ordinary source acceptance has four explicitly recorded optional skips.
Snapshot/watch schema documents remain identical. No Agent artifact is selected
or collector process restarted from this source result.
Repeated full proof/push bytes and independent connections scale with consumers,
but no shared-service candidate has yet demonstrated useful net savings.
Digest-proof still needs capability/receipt-equivalence review; pooling still
needs explicit leases and cross-process acceptance. Neither is enabled here.

## Acceptance boundaries

The a10 wheel has isolated Python 3.11 core acceptance (75 tests, no Observers)
and Python 3.14 native/owned SSH acceptance (107 tests, no skips). The selected
source environment also passes the canonical native gate. Its editable package
metadata contains historical versions; it is not evidence for the installed
wheel tuple. Frozen Read/Delivery checks remain 116/169 and the lock gate keeps
18 normative inputs / 20 packaged schemas unchanged. The optional exact-source
parity check rejects the evolved Tmux HEAD; the frozen baseline is preserved.

The first 30-minute installed-a9 runs are retained as failed acceptance:

| Domain | Observed rotations | Fresh recoveries | Strict-gate finding |
| --- | --- | --- | --- |
| Tmux | Snap 4, Starship 3 | All seven | Four setup failures make resource counters partial. |
| Agent | None | None | Peak 2,204 handles; elapsed time did not reach a rotation. |

The initial a10-wheel Tmux run completes 20 minutes with two rotations and fresh
recoveries on each host, zero active connections or cleanup failures, and two
failed setups. Its partial resource coverage fails the strict gate. The longer
Agent run and corrected Tmux run are pending at this checkpoint.
An immutable follow-up harness adds bounded delivery-transition error counters
and active-plus-retiring bridge capacity;
the completed negative run remains recorded rather than being relabeled.
Final acceptance requires two observed revocations and fresh resync recoveries
on each host, complete metrics, and no active connections or cleanup failures.
`review-status.json` distinguishes a checkpoint from completed source/candidate
review; running counters do not count as acceptance.

These additional Readers retain the real 4,080-handle budget
and use a test-only 100 ms proof interval; they do not change producer cadence.
This cannot certify ordinary 3/10-second cadence over multiple hours, graphical
viewer interaction or physical suspend/wake. Those gates remain separate.

A10 consumer-pin review, immutable release and paired deployment remain a new
[adoption checkpoint](adoption-checklist.md). The source fix does not overwrite released wheels or
silently replace any installed environment. Tmux's control fix likewise requires
its next independently accepted artifact and exact consumer pin updates.

## Follow-up

1. Carry subscription admission, control binding and private bridge retirement
   headroom into reviewed artifact tuples.
2. Trace the rare refresh scope revocation with producer/native delivery events;
   distinguish gap/backpressure/reconnect from reply corruption.
3. Accept the pure-validator refinement in a new Agent artifact, then measure
   whole-fleet savings against matched selections without changing collectors.
4. Extend rotation acceptance at ordinary cadence, then do endpoint-specific
   graphical/viewer and suspend/wake acceptance.
5. Keep Agent Plus/devices, WSS, broker leases and negotiated digest-proof separate.

## Reproduction and provenance

The isolated candidate wheel SHA-256 is
`95cfbfa85c61b1dcd313e78c3b14c14d03d0d9ea084be6a60970dd49015cad82`.
`candidate.json` binds source checkpoint 504a176, packaged runtime parity, and
unchanged released-a9 authority/schema/lock bytes. No native input records are
published; private replay files were created exclusively in a 0700 directory
with 0600 permissions. Capture them with `scripts/capture-profile-input.py`.

`run-process-matrix.py` drives the watch/snapshot matrix using an explicitly
selected interpreter and the same private frame. `measure-validator.py` now
selects the explicit pre-change Agent revision rather than moving HEAD; its
original ABBA execution bytes are retained separately. Frozen checkpoint and
pre-format harness copies retain exact versions where available. The initial
Mesh-refresh harness was not archived; its digest alone is not reproducibility
proof. Candidate refresh reporting reads the later formatted pathname digest,
so its pre-format executed bytes have an explicit separate hash. The first
soak likewise preserves executed bytes separately from a later pathname digest.
`harness-provenance.json` and `soak-provenance.json` make these limits explicit.

The strict finalizer refuses pending or failed lifetime gates. `--checkpoint`
records completed measurements without upgrading them to overall acceptance.
Recorded runtime Python/schema hashes, protected controls and active service
incarnations remain unchanged on both hosts at the checkpoint; the final capture must
be repeated after all owned jobs terminate.

Interrupted independent-process matrices now signal owned workers for graceful
cleanup before a bounded process-group kill fallback. A real SIGINT acceptance
on four disposable localhost SSH workers observes 25 owned processes and zero
remaining identities afterward. It certifies graceful cancellation, not the
forced-kill branch; the earlier completed matrix reports keep their original
executed harness bytes and do not certify this later cleanup change.

The final Tmux source checkpoint is `1a2b3eb59e5778b27e3f52fed93a2684e29d58a3`:
383 standard tests and seven separate a10 Mesh tests pass. A first standard-gate
run failed one isolated deferred-session fixture with `server exited
unexpectedly`; the targeted retry and subsequent full gates pass. The failure
is retained separately and is not attributed to the SDK admission change.
Agent pure validation is checkpoint `3986474bd8d0d841a742b47ed2dfcd0f04cf0dd2`.

## Refined candidate continuation

The corrected 30-minute Tmux soak passes seven production-budget rotations
(Snap four, Starship three), with matching fresh resync recoveries, complete
metrics, no failed setup and no live connections or cleanup failures afterward.
The longer Agent soak completed two hours with clean counters and cleanup,
but missed required Starship coverage: Snap rotated twice, Starship once.
A separately bounded follow-up is recorded in the
[artifact continuation](../2026-10-10-hardening-artifacts/README.md).
Neither result certifies ordinary
proof cadence, desktop input or physical suspend.

Fresh installed pairing exposed a CLI startup race: socket publication could
precede installation of SIGTERM/SIGINT handlers. A deterministic publication
delay reproduces the failure on the original a10 candidate; source checkpoint
`3684fe083c0ab5af3c74aa27dff169e5764489f5` fixes shutdown ownership before
publication. The refined a10 wheel has SHA-256
`c9fecd77e3ea181d43447784824616232874cfc9ead12a30460d0682bdc3684d` and passes
fresh installed 75-test core / 108-test native gates. It does not overwrite the
original candidate. Reader, Client and transport modules are byte-identical;
the long soaks do not certify the changed CLI startup path.

The new pure-domain tuple is Tmux Observer a5 / Agent Observer a16. An initial
Agent wheel was rejected because an ignored build directory retained the
deleted `service_scheduler.py` module. A clean committed export produces exact
runtime parity; the rejected artifact is retained. Tmux Plus a5 pins all 83
Observer Python modules across the three package roots and passes its installed
headless frame/callback gate. These are candidate gates, not managed adoption.

Snap is headless in this operational baseline: no Niri socket or managed desktop
context is active. The captured-desktop resource gate records that failed
prerequisite. A separately labeled `headless-cached-delivery` resource scope
excludes desktop/viewer readiness while retaining the 600-second measurement
and original CPU/RSS limits. Managed adoption must preserve this headless state;
Starship desktop acceptance remains endpoint-specific.

The final original-baseline capture was repeated after these owned jobs completed,
before controlled managed recovery. Both endpoints retained all captured package
bytes, controls and service incarnations. A subsequent Starship Mesh bridge
restart repairs deleted-interpreter drift; it is separately recorded in the
artifact continuation and is not covered by that earlier preservation claim.
