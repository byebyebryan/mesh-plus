# Independent Observer networking adoption

Mesh SDK interface v1 is implemented in a11. See the [interface](sdk-api.md) and
[package evidence](evidence/2026-10-10-sdk-v1/README.md). Existing reference
integrations remain compatible; owner adoption is independently schedulable.
Both Observer source checkouts remain unchanged by this Mesh pass.

A12 adds an optional [installed conformance kit](conformance.md) and
[cached diagnostics](sdk-diagnostics.md) under that same SDK interface, with
[package evidence](evidence/2026-10-11-sdk-maintenance/README.md). Owners can use
the kit against their own profile factories without copying Mesh tests. SDK v1
adoption against a11 remains valid; a12 does not require a coordinated migration.

| Work stream | Bounded next task | Acceptance |
| --- | --- | --- |
| Mesh | Transport fixes, cleanup, diagnostics and measured performance under SDK v1 | Standalone conformance, pinned native matrix when affected, SSH authority compatibility; preserve lock/schema bytes. |
| Tmux Observer | Supply a pure `StateProfile` using supported native/delivery facades; bind it explicitly at networking entry points | Pinned Mesh a11, native/frame projection parity, original receipts, configured IPC/SSH poll and watch, restart/gap/disconnect/expiry. No desktop or Plus dependencies. |
| Agent Observer | Supply a pure `StateProfile` using supported service/contract facades; pass it consistently through configured Reader and guard/view helpers | Pinned Mesh a11, native projection parity and preserved eligibility, per-source receipt independence, poll/watch recovery and owned cancellation. No collection or provider-policy changes. |
| SSH Plus | Continue selecting the reviewed Host Mesh authority ABI; consider new artifacts through its own selection gate | Canonical backend model/subprocess regressions, alias/class identity, separate config/health/history ownership. No authority migration is required by profile injection. |

Each Observer task can proceed alone. Its package must depend on a tested Mesh
artifact/interface, not the other Observer's checkout HEAD. A pure profile may
be introduced before moving the native cached publisher adapter. Retaining the
reference adapter is a supported intermediate state. Do not infer that an owner
has adopted its own implementation merely because Mesh's compatibility suite
passes with its native wheel.

Mesh provides transport, endpoint selection, proof/lease admission, lifecycle,
host outcomes, aggregate validation, conservative row validity and metrics.
The owner provides pure native validation, lossless projection/reconstruction,
identities, source receipts and eligibility. Profile callbacks are pure installed
code; they do not resolve hosts, contact services or collect providers. Mesh's
proof and scope checks remain compulsory regardless of callback implementation.

Use `mesh_plus.api`, `descriptor(domain)`, an explicit bound codec in each direct
`Endpoint`, and the same `profile=` for configured Reader, validation,
reconstruction, current selection and `ReadGuard`. Native-only reconstruction
bindings use source `default`; configured source IDs remain endpoint selectors,
independent of opaque native receipt source IDs.

The [independent test profile](../tests/sdk_fixture.py) demonstrates structural
implementation without inheritance. The [SDK boundary suite](../tests/test_sdk.py)
runs with Observer/reference-integration imports blocked. Owners should run the
same boundary cases with their native profile and their reviewed wheel fixtures,
including callable validators without `__self__`, wrong binding, forged proof,
receipt removal/lease upgrades, warming/historical views, empty required receipts,
publisher restart, gap, catalog replacement and repeated cancellation.

The [differential gate](../scripts/check-sdk-compat.py) compares 12 frozen
projection cases and 36 effective selections against a separately selected prior
SDK environment. Pair that networking oracle with owner-native semantic tests.
It does not claim arbitrary provider behavior has been reviewed by Mesh.

Changes to native/profile semantics or public SDK guarantees require explicit
review. Compatible implementation work proceeds independently. Shared live
artifact selection, bridge controls and rollback remain separately coordinated.
No Plus migration, new backend, event product or broker belongs to this handoff.
Keep project tooling and acceptance evidence in the owning repository; put only
necessary deployment configuration in chezmoi.
