# Coordinated hardening artifact checkpoint

This is a published-artifact checkpoint following the
[operational hardening study](../2026-10-10-operational-hardening/README.md).
The selected a9 cohort remains installed. The following fresh artifacts were
built into separate private output directories and published as new prereleases;
GitHub asset digests match all five accepted payloads. Old artifacts retain
their bytes. Publication does not select or deploy them.

| Package | Candidate source | SHA-256 |
| --- | --- | --- |
| Mesh 0.1.0a10 | `3684fe083c0ab5af3c74aa27dff169e5764489f5` | `c9fecd77e3ea181d43447784824616232874cfc9ead12a30460d0682bdc3684d` |
| Tmux Observer 0.6.0a5 | `5d8b7234ba10920beb59bde35c2f79c73d382b25` | `958d2f5381d57f172294e35654e19c96770ccd38e7ef8421a23f3dcf00abe536` |
| Agent Observer 0.5.0a16 | `301b57a6eb12bacde220603d47c21995548bb7b6` | `94705baebfa51a9664e9dbfa7603dcb932d6301146cf9a59017017c5285b3b17` |
| Tmux Plus 0.12.0a5 wheel | `8d5242ac3b5252028803a982e70d8215613d5010` | `61a3a98fae0a72fd94680cea7e7aa774bd1f13b8bb109d037a40f42e62d67ed0` |
| Tmux Plus managed bundle | Same Plus checkpoint | `07df66c71e0684987dcd10ca524a5ecf72d583b3802be024ab3e64acf73947b6` |

All runtime payloads match the committed source. The packaged Mesh schemas,
contract lock and reviewed SSH extraction retain released-a9 bytes. Consumer
pins include all 83 Tmux Observer Python modules across its three package roots.
Later Tmux harness/SDK-source-pin checkpoints `3e3914f3d57670519882e111c80fab8e06285294`
and `4dee90caf5cb5a5e74fc5d193ab242dadcb3f328`
leave the packaged Observer payload unchanged; they select the refined Mesh
source and add explicitly headless resource measurement and independent refresh/gap fixtures.

## Exact installed gates

- Mesh core: Python 3.11.10, 75 tests, no Observer packages, no skips.
- Mesh native: Python 3.14.8, 108 tests, installed a10/a5/a16 tuple, no skips.
- Tmux native Mesh: eight tests on the installed candidate tuple.
- Plus source: 293 tests, formatting/lint/shell gates pass with exact a5 input.
- Plus installed headless: both Snap and Starship pass owned server, frame,
  callback, bounded outage and cleanup checks. These use disposable fixtures.
- Agent source: 448 tests with optional Mesh/jsonschema dependencies and no skips.
  Both hosts have verified, unselected a16 reader and bridge environments;
  Snap retains the source-only Claude history SDK profile and Starship core.

The first paired 107-test Mesh check exposed SIGTERM before CLI startup handlers
were installed. `mesh-native-final.json` retains the failure. A deterministic
publication-delay regression fails the original a10 wheel and passes the refined
wheel. Its fresh full 108-test result is `mesh-native-refined.json`; the older
candidate's lifetime measurements certify only byte-identical Reader/Client/
transport modules, not the new CLI startup path.

The initial Agent wheel retained a deleted module from an ignored build
directory and was rejected. A clean committed export produces the selected
candidate hash above. `agent-rejected.json` and `agent-clean-parity.json` keep
these results separate.

## Resource scope

Snap has no active Niri session or managed desktop reader in the captured
baseline. The desktop resource attempt records this failed prerequisite in
`tmux-resources-desktop-prerequisite.json`. Source harness checkpoint 3e3914f
adds `headless-cached-delivery`, explicitly excluding desktop and viewer
readiness. It retains ordinary default-server passive reads, real SSH,
600-second duration, owner/reader/associated bridge accounting and original
resource targets. It starts and cleans up only owned temporary services.

| Endpoint | Combined CPU | Fleet and associated bridge RSS | Owner RSS |
| --- | --- | --- | --- |
| Snap | 2.53% | 82.53 MiB | 23.26 MiB |
| Starship | 2.30% | 82.16 MiB | 24.81 MiB |
| Original limit | 5% | 96 MiB | 64 MiB |

The gate passes, preserves native references/generations/hooks and cleans up its
owned services. Sampled RSS can miss transient peaks. Ordinary workload and
parallel soak work are uncontrolled. This establishes the labeled cached
resource gate; graphical input, positive viewer matching and physical wake
remain separate acceptance. The published report removes native snapshot
frames and hashes native reference lists. It retains timing samples, input
identities and preservation proof; long resource time series become count/hash
and first/last samples alongside unchanged aggregate gates. The complete raw
report remains private and is bound by SHA-256.

## Refresh attribution

`refresh-refined.json` retains two failures in 200 repetitions of the old
success fixture. `refresh-attributed.json` records two failures in 100 repetitions
with control-binding, projection and exception-stage diagnostics. Actual delivery
coalescing emits a gap: scope authority is revoked before a fresh replacement.
A matching native control reply cannot preserve a revoked scope. One observed
five-second fixture timeout waited on an already terminal `stale_scope` ticket;
the fixture omitted this terminal state. Historical uninstrumented failures
remain unattributed.

The Tmux harness now recognizes all contract terminal states. The success case
paces only its owned synthetic publication stream through actual IPC consumption;
it verifies complete refresh when every replacement is delivered. An independent
case injects a real gap/control/full-resync sequence and requires terminal scope
revocation. All eight installed native tests pass; the gap case also passes
50 repetitions. Production gap policy, wire bytes and overall wait budgets are
unchanged. Successful delivery passes 200 repetitions with unchanged input paths.

The intermediate `refresh-stable.json` and `refresh-sequenced.json` retain failed
fixture attempts; their separate executed test copies preserve the bytes actually
loaded. These older tools hashed input paths at completion, so mutable pathname
hashes do not establish executed bytes. The refined diagnostic tool captures
input hashes before the loop and reports whether paths remained unchanged.

The canonical source/native gate passes 108 tests with no skips. Adding
`--check-sources` rejects the current Tmux checkout HEAD against a frozen historical
reference; that reference and lock are deliberately preserved. Exact wheel/module
parity and native gates certify the new inputs independently.

The retirement-overlap CI fixture timed out during initial readiness with a
synthetic four-handle budget. It now establishes readiness under the production
4,080-handle budget, then exercises three rotations with the tiny steady-state
budget. Thirty repeated owned IPC cases pass. This is fixture scheduling
refinement; the captured CI failure does not establish an independent runtime
bootstrap defect.

The broad picker source/contract check uses an owned detached clone of held
Agent Plus revision `6d30f8c71a9e44ba1da19f4102292f6811df50d8`; its newer active
checkout and managed selection remain untouched. With the candidate interpreter,
SSH passes 82 tests, Tmux Plus 293, and held Agent Plus 320 with four explicitly
skipped tests. Contract sync passes. Its public PATH stage uses the still-selected
Observer a4 root and rejects the new Plus a5 inventory, so that stage remains
pending until paired selection. The earlier default-system-Python attempt lacked
Mesh imports; it is not acceptance of the selected shared authority.

## Remaining before adoption

The two-hour Agent production-budget run finished without runtime failure or
connection/cleanup failure, with complete counters and all six opened channels
closed. It fails required coverage: Snap has two rotations/recoveries, Starship
one. `agent-two-hour-coverage.json` preserves this negative gate. A follow-up uses
released Mesh a10 and Agent a16 in an owned local bridge and explicit private
remote stdio bridge. Ordinary collector/writer selection stays unchanged. It
retains the 4,080 admission threshold, records per-host delivery transitions,
and stops only after two rotations/recoveries on both hosts, with a four-hour
hard maximum. Its fixture-only remote executable override leaves public launchers
and routes untouched. `run-agent-followup.py` and `profile-fleet-followup.py` bind
executed bytes; source/root inputs match the released artifacts.

A two-host owned IPC check validates coverage-driven stop and owned cleanup
with a small synthetic handle budget. The canonical native gate still passes
108 tests, no skips; this does not substitute for actual production-budget
follow-up coverage. Starship's baseline
live-artifact gate rejects a bridge still running a deleted Python executable
whose hash differs from the current interpreter. Its selected package files are
unchanged. `deleted-bridge-interpreter-starship.json` retains this drift. After the old soak completed and original baseline preservation was confirmed,
only the Starship Mesh bridge was restarted. A fresh baseline now passes its
canonical interpreter/artifact, unit, endpoint, desktop service and cached-read
gates; ordinary collector/writer incarnations remain protected. Original negative
drift evidence is retained. Scoped paired selection, recovery, rollback/reselection and exact
final live selection are pending. Managed source URL/checksum and private role
selectors are prepared; the ordinary collector/writer configuration is unchanged.

Checksums bind this checkpoint's evidence files. Original replay inputs and raw
native frames stay in private scratch space and are excluded from the repository.
