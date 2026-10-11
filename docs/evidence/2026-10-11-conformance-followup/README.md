# Conformance follow-up acceptance

2026-10-11 review follow-up. This record covers a13 conformance tooling and current
guide synchronization; a12 acceptance remains evidence for its own exact bytes.

The result runner requires an explicit passing outcome for every selected case.
Expected failures, unexpected successes, skips and failing/skipped subtests are
reported without private details and cannot certify a profile. Portable network
coverage grows from eight to ten cases per domain. Live publisher updates and
restart pass through Bridge, owned IPC, Reader and ReadGuard, with both local and
remote-proof endpoint bindings. A silent publisher negative control fails rather
than benefiting from periodic reads. Restart must revoke rows before reconnect
and accepted resync; original source receipts stay unchanged.

Package and final validation inputs are recorded alongside this guide. No sibling
checkout or deployment is modified. Native validation uses pinned Tmux a5 / Agent
a16 wheel facades; it does not certify current owner checkout adoption. Actual
SSH carriage remains a separate owned fixture suite, rather than a claim that the
new IPC transition cases run over SSH. No provider collection, ordinary fleet,
GUI, physical suspend, production soak or performance matrix is exercised.

Acceptance passes 104 standalone tests on Python 3.13 source and Python 3.11
installed wheel, plus 141 installed native/SSH tests on Python 3.14; no skips.
The canonical gates also pass 18 locked inputs, 20 packaged schemas, 116 Read
checks, 169 Delivery checks and lint. The external installed kit passes six
suites/35 cases without Observer packages, detecting two broken profiles and
rejecting two suites containing expected failures. Twelve frozen projections
and 36 effective selections equal the separately installed a12 baseline.

See [package inputs](package.json), [validation](validation.json),
[external conformance](conformance-wheel.json) and [a12 differential](differential.json).
The a13 wheel is 107,803 bytes, SHA-256
`62b42bc76e7d79d95d89c41ee6f73c5e0169d24e2f1ac911c151c13f1f2b6f07`.
All 49 runtime/schema/resource members match source. Only the package version
marker and `testing/network.py` / `testing/suite.py` differ from a12.

The [immutable a13 release](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a13)
is tagged at the complete evidence commit. [Publication verification](release.json)
records green source CI and byte-identical downloaded wheel/checksum assets.
The earlier preparation commit briefly linked reports before their addition;
its failed documentation gate is retained explicitly rather than claimed green.
Runtime acceptance inputs stay source-identical to the final release tag.

Reproduce with isolated installed wheels:

```sh
rtk proxy /path/to/core-python scripts/check.py
rtk proxy /path/to/core-python scripts/check-conformance-wheel.py --ssh --report /tmp/conformance.json
rtk proxy /path/to/native-python scripts/check.py --native
```

The frozen lock, packaged schemas, SDK API, authority, Reader, Client, Bridge,
transport, state/view and diagnostics bytes retain their a12 reviewed content.
The conformance interface retains v1 and its public signatures. Live selection
and owner integration remain separate acceptance gates.
