# Controlled Mesh performance pass

2026-10-12. Authorized unattended execution. Ordinary transport stays SSH.
Agent Observer is actively developing and is excluded from source edits and
live testing. Any downstream check uses immutable Tmux artifacts and disposable
fixtures, not the changing sibling checkout or its ordinary services.

## Sequence and acceptance

1. Pin released Mesh a15, Tmux a7 pure profile, dependency versions, corpus and
   harness bytes in an isolated environment. Keep SDK/wire/lock/schema bytes.
2. Build a synthetic cached-state trace with explicit replacement steps and
   independently expected identities, revisions and original receipts. Readers
   acknowledge each step before the fixture advances; no polling filesystem or
   active collector is used as the benchmark producer.
3. Validate poll, push, expired receipts, reconstruction and teardown. Reject
   skipped steps, unanticipated proofs, gaps, drops and workload mismatches.
4. Pilot IPC, disposable actual SSH and loopback mTLS WSS using the same pure
   profile, cached-source interface and consumer guard. Account separately for
   fixture acquisition, publishers, reader/driver, SSH roles and sampler.
5. After pilot acceptance, use four ABBA blocks for IPC/SSH and SSH/WSS, then
   two/four independent upstream readers. Report topology sharing explicitly;
   raw TLS fanout does not certify a prepared downstream service capacity.
6. Profile the expensive controlled case. Make only a measured compatible Mesh
   improvement; otherwise record a no-change decision. A runtime candidate needs
   frozen-byte checks, adversarial/native tests and isolated wheel acceptance.
7. Commit reproducible evidence, exclusions, final decision and handoff.

This is operation-controlled cached delivery, not an ordinary proof-cadence or
fleet-budget test. Each cell executes the same number of state steps, proofs and
consumer admissions. Receipt initialization is fixture setup; replacements,
proofs and transport traffic do not renew them. Clocks and volatile identifiers
are normalized only in comparison evidence, never bypassed in runtime admission.

Main CPU accounting excludes setup/imports/key generation. Role CPU uses own
ticks and PID birth, never child tick aggregation. Unknown memory remains null.
Fixture/driver/sampler overhead and background load remain explicit. Sampling
cannot claim transient peaks. Loopback evidence is not tailnet or production
latency. WSS operations, real-host rotation and physical suspend remain separate
promotion gates. No ordinary deployment or alternate protocol belongs here.

The prior [fleet decision](evidence/2026-10-12-performance/decision.md) retains its
dated scope; this pass does not relabel its excluded comparisons as acceptance.
