# Common input contract agreement receipt

Observer commit `7a1d6661538a4e632c90c0c6334dbf125a1be969` explicitly accepts
Mesh's exact public reserve/resize/seal/consume signature and ownership-state
contract. The Mesh document remains
`docs/delta-sync-owned-input-api.md`, SHA256
`7f7751ecd9df93277a3e7110ca72ebfda343d38fa629cd0212ec40b3a8f1d124`.
This advances the agreement gate recorded as pending in the earlier dated
[source checkpoint](OWNED-INPUT.md); those historical bytes remain unchanged.

The pinned Observer `docs/delta-sync-interface.md` is 22,972 bytes, SHA256
`a7bd065a76180c31a96adba7982c51039e0a40c8a316461f7c7e2947981a2669`.
Its live document matched that commit when captured. Exact provenance/scope is
in `input-contract-agreement.json`, SHA256
`54e1c02350a074f91af2a62de04d61ea0cd76a0645b6b284db6461caf3bc01cf`.
Mesh source checkpoint `1d50db0` retains the agreed public signatures; its
pre-construction accounting fix changes no reviewed signature.

Agreement covers the common cache-backed source contract, not completed
Observer implementation, native intake/resource acceptance or API/schema freeze.
Source sessions own and revoke their own refs, then cancel/await their I/O;
they never close a shared cache-minted InputOwner or native service. Receive,
header, DTO and batch leases remain charged until their actual storage retires.
Every receiver still independently admits material and proof.

The native opt-in adapter, generic owned-session acquisition integration and
complete intake/pin/stage accounting remain open. Packed baseline/recovery must
actually deliver the target within the existing frame, aggregate and absolute
acquisition limits and obtain a fresh bounded nonce proof. An unavailable journal
is counted baseline-required recovery, not successful incremental delivery or
permission to retain authority over a known moved target.

The near-cap source result reported by RLCD `e-bfb5a850` remains source-only;
it grants no 2,000-row transport, cold/recovery, CPU/RSS or installed acceptance.
Unmatched component timings do not close performance gates. Compact codec/
packing and joined native vectors remain pending. A1 coordinator review is
already issued; joint producer agreement on that separate role remains open.
No cap, deadline, authority, frozen schema/lock, artifact, normal role or
deployment changed in this receipt. No runtime file was edited or requalified.
