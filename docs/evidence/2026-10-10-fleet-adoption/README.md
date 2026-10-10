# Coordinated fleet adoption, 2026-10-10

Mesh owns cached polling and pushed replacement-state delivery. This pass
coordinates transport adoption across the two Observer integrations and the
exact Tmux Plus consumer pin. It does not change provider interpretation or
advertise ordered event delivery, replay, WSS or shared upstream leases.

## Exact selected artifacts

| Component | Source checkpoint | Artifact SHA-256 |
| --- | --- | --- |
| Mesh 0.1.0a9 | `3b6754312000d1c39a3ab407986130b9c621f0d4` | `07882909a49cd513b5c114da7890bebfe9b1592da3a08cca69a68c24817164c2` |
| Tmux Observer 0.6.0a4 | `1c99f5fb1ae4bb5cf9c52014aeb1f9b22d8248d2` | `6282ed94c5b401579de86c9dc9f9e989d85f7dae2feb7da4607657a37136b6c2` |
| Tmux Plus 0.12.0a4 wheel | `42d17d857954cef289cd447a7c39c437b977d798` | `674d0c43c8591a7f27372291ef132461969d842cd99a640963447656cc00e48d` |
| Tmux Plus a4 native source bundle | same checkpoint | `f233ad398eb980b449848666261e80d016ceeee817fb2b59cb8573369e8285cf` |

All are immutable prerelease assets. Snap and Starship select the paired Tmux
artifacts and shared a9 SDK. Agent retains the exact a13 reader and a12 bridge
Observer wheels in new `-mesh-a9` roots. Its collector stays on a15 and writer
on a16. The managed selection tuples bind all package members, dependencies,
archived verifiers and control targets. Source-only Claude-history support stays
on Snap; Starship retains core. Agent Plus and SSH Plus artifacts are unchanged.
Older SDK and Agent roots remain available for rollback.

## Findings and implementation

A8 supplies proactive Client admission at 4,080 handles, visible Reader
revocation before resync, and cumulative redacted channel/Reader counters.
Tmux's actual worker now admits the reviewed SDK and keeps bounded library
catalog reads. A worker/projection regression forces repeated incarnations while
retaining one Reader and verifying fresh owner expiry after recovery.

Actual native accelerated rotation on Python 3.14 exposed a late shield-future
ConnectionResetError diagnostic. A9 replaces shield ownership with waiting for
the admitted bounded IO task through repeated caller cancellation, then observes
its result. Bridge frame ordering and Reader cleanup retain their ownership.
Deterministic tests cover repeated cancellation and late IO failure without a
background exception callback. Wire, lock, twenty schemas and authority bytes
remain unchanged. Reserved schemas grant no new capabilities.

Agent's archived verifier now admits exactly one reviewed a4, a8 or a9 manifest.
Duplicate and unknown manifests fail before invoking a verifier. Its native
producer/collector contract, collection cadence and provider authority stay
independent. Plus required a paired release because its Observer module bytes
are pinned exactly, rather than only by compatible version.

## Validation boundaries

Standalone installed Mesh acceptance: 74 tests on Python 3.11 without either
Observer package. Installed native/SSH acceptance: 106 tests on Python 3.14;
`a9-wheel-native.json` used the intermediate Observer a3 facade, while
`final-a9-wheel-native.json` binds the final a4 facade. Source gates pass Read
116, Delivery 169, LOCK 18, and runtime 106 plus Ruff. Source distribution
metadata can remain stale in an editable tree; installed wheel reports and
runtime digests are the artifact authority.

Tmux source gates pass 382 tests and the six optional installed Mesh cases.
Agent source passes 445 tests with four optional SDK skips; a separate installed
SDK run passes all seven Mesh CLI tests, plus the manifest ambiguity regression
in the full suite. Plus source passes 293 tests. Managed operation helper tests
pass twelve cases. Mesh, Tmux and Plus runtime release commits pass CI. The first Plus a4 CI run
received 404 before the required Observer release was published; the same runtime
commit subsequently passed after publication, without relaxing the artifact pin.

Installed Plus headless gates exercise frames, read-only callbacks, explicit
refresh, owner outage, preserved native references and private bytecode cache.
The isolated wheel p95 is 132.72 ms and managed Snap p95 78.01 ms against the
unchanged 150 ms target; managed Starship p95 is 48.60 ms. No graphical window/input
or physical suspend is claimed.

Actual native fleet rotation checks use additional private Readers with a
process-local four-handle threshold and 100 ms proof interval. They verify revoked
hosts lose current rows before fresh ready/resync, both hosts advance epochs,
and final metrics contain no active connection, partial instrumentation or
cleanup failure. Ordinary collector and production proof cadence are untouched.
These checks are distinct from the real 4,080-handle admission unit acceptance;
ten-minute ordinary profiles do not establish multi-hour production-budget
rotation. The retained harness and runtime digests bind this accelerated proof.

Agent CI additionally exposed a UID-1000 assumption in a new memo fixture;
the fixture now uses the actual caller UID and rebinds its store and row
namespaces consistently. Four memo admission cases also pass with UID 1001
injected locally; the Mesh CI lane pins a9.
The standalone Python 3.11 build here omits sealing names and `memfd_create`.
Source-only Agent refinements use stable Linux UAPI seal constants and fall back
to ordinary snapshot workers when memfd is absent. The full 445-test suite passes on that build with two explicit memfd capability
skips, including a real worker without memo transport. Installed collectors are unchanged; this producer fix
requires the next independently packaged producer release before deployment.

## Measurements and optimization decision

The a8 historical profiles are `normal-{host}-{domain}.json`; final a9 profiles
are `final-normal-{host}-{domain}.json`. Each is a 600-second additional native
cached-fleet Reader. Resource scope includes its local process descendants and
consumer, and excludes the existing collectors and remote bridge. RSS/process
sampling can miss short peaks. Other validation/build work ran concurrently.
These are descriptive measurements, not matched before/after savings.

A8 costs were 1.448% CPU / 45.70 MiB for Snap Tmux, 0.838% / 45.08 MiB for
Starship Tmux, 3.547% / 47.82 MiB for Snap Agent and 2.452% / 46.86 MiB for
Starship Agent. Agent exposed up to 130 cached records. All four closed their
connections with complete instrumentation and no connection/cleanup failures.
Final a9 values and the independent Tmux resource gate are recorded below.
The two resource gate files are explicit summaries: aggregate acceptance fields
are preserved, individual sample arrays are replaced by counts and canonical
hashes, and complete raw archive bytes/path/SHA-256 are recorded. Individual
samples remain locally available and are not duplicated in the repository.

`scaled-ipc.json` and `scaled-ssh.json` bind the stabilized a8 fixture harness:
eight cases each, 256 synthetic native rows, one/four Readers and idle/one-second
replacement updates, five-second steady intervals and three-second proofs.
All cases have complete instrumentation and clean teardown. The supplementary
`agent-1000-rows-ipc.json` is a short case-mode smoke without full runtime/harness
digests; it does not certify a production inventory or final a9 bytes.

Full payload validation and proof traffic warrant matched Agent workload study
before redesigning transport. Process-local pooling cannot share connections
between independent CLI processes; a daemon lease would require a separate
ownership contract. Digest-proof requires negotiated capability and equivalent
nonce/receipt/expiry semantics. Keep direct IPC/SSH as the default. No pooling,
digest-proof or backend migration is justified as a default by this pass.

## Operational refinements and retained limitations

The Tmux resource gate retains the original `native-viewers` mode. The separately
named `cached-delivery` mode uses the same ten-minute CPU/RSS budgets when a
host has no attached clients. Starship has zero attached clients; this gate does
not claim B5 viewer acceptance or Open authority. Actual Niri/process matching,
native identity and health still apply. Installed reference preservation and
resource sampling are distinct from graphical viewer acceptance.

Intermediate acceptance exposed an intermittent grouped refresh `invalid_refresh`.
Subsequent whole gates and twenty targeted runs passed; one instrumented repeat
hit the harness's five-second wait. No root cause was established and no control
runtime fix was inferred. Final installed refresh passes, but repeated refresh
under ordinary load remains a bounded follow-up. The first strict Agent rotation
run failed without persisting final counters; later repeated runs passed. The
harness now writes counters before asserting cleanup, preserving future failures.

The operation capture helper now creates its report parent before ZIP creation.
An initial scoped a8 apply omitted the versioned SDK parent and failed after
controls changed; the parent was created, apply completed and services restored.
Final a9 deployment precreates the parent. Private baseline payloads/controls
are retained. One Starship headless invocation without `-B` generated bytecode
inside the exact bundle; only those identified generated files were removed and
the gate rerun with `-B`. No release member was altered.

Starship's dirty divergent chezmoi checkout is preserved. Its deployment uses an
independent temporary source checkout. Protected configuration, original SDK
roots, Agent artifacts and collector process incarnation are checked before and
after deployment/recovery/rollback. Private control captures contain paths and
unit bodies and are retained locally rather than published in this evidence.

## Final operational gates

The final Tmux cached-delivery resource gate passes on both hosts with the
unchanged 5% combined CPU / 96 MiB fleet-plus-associated-bridge / 64 MiB owner
budgets. Snap reports 3.045% CPU, 83.18 MiB fleet-plus-bridge and 22.09 MiB owner;
Starship reports 2.057%, 82.04 MiB and 25.13 MiB. Both complete 600 seconds,
retain native references and clean up their private processes. The harness binds
the clean a4 source checkpoint and final a9 wheel tuple. These results do not
claim positive viewer or GUI acceptance.

Final additional a9 Readers all pass 600 seconds: Snap Tmux 1.401% CPU /
45.04 MiB, Starship Tmux 0.872% / 45.26 MiB, Snap Agent 3.812% / 47.20 MiB,
and Starship Agent 2.443% / 47.90 MiB. All have complete instrumentation, no
connection/cleanup failure and no active connection after teardown. Agent has
up to 129 records in these profiles. Rotation remains zero at ordinary budget
and cadence, as expected for this interval. These values include the additional
consumer and do not establish matched savings.

Recovery passes on both hosts: Tmux owner/fleet incarnations change and regain
ready prepared/fresh views; Agent bridge PID changes with installed interpreter
and kernel peer verified, and local/fleet snapshot/watch recover. The collector
PID and process-start identity, original artifacts and protected configuration
remain identical. Serial rollback/reselection passes on both hosts. Each restores and verifies
Observer a2 / Plus a2 / shared SDK a7 with private Agent SDK a4, then reselects
and verifies Observer a4 / Plus a4 / shared and private SDK a9. Original native
sessions, protected artifacts/configuration and collector incarnation survive.
Starship's foreign checkout HEAD, status and patch hashes remain identical.
`final-rollback-reselection-{host}.json`, baseline/final installed reports,
recovery reports and redacted CLI results bind these separate gates. The original first profile launcher retired its children before report
completion; it produced no acceptance report. Retained execution sessions own
the replacement profiles through completion.

The first Snap reselection stopped on chezmoi's expected restored-control drift
prompt. Before a scoped forced apply, the harness now compares every captured
Tmux and Agent control to its baseline. A complete repeated Snap rollback and
reselection then passes. A force does not bypass those equality checks.

## Follow-up order

1. Repeat ordinary refresh with structured failure counters before attributing
   or changing control runtime behavior.
2. Collect matched Agent payload/update and multi-process consumer traces to
   choose any validation optimization, digest-proof or shared lease work.
3. Run a prolonged production-budget rotation soak and endpoint-specific
   graphical/viewer/suspend acceptance when those endpoints are available.
4. Keep Agent Plus/device migration and direct WSS authorization/deployment
   separately scoped; the frozen state contract remains the handoff boundary.
