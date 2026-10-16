# Mesh admission CPU qualification

2026-10-15. Source/private a22 candidate. No release or production adoption.
This receipt is completed with exact wheel and final gate/performance inputs
after qualification; draft screens are not installed artifact acceptance.

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
on Python 3.14.8. Draft focused tests exercise request/profile/order/scope binding,
detached mutation, clock/expiry, full-roster exclusions, independent host expiry,
selector failures/reentrancy, fallback and combined codec checks and owned IPC
cleanup. Final source and isolated package checks are recorded below when ready.

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

Final artifact, validation, performance, cleanup and producer disposition are
pending. RLCD owns subsequent pinned consumer adoption and live/device acceptance.
