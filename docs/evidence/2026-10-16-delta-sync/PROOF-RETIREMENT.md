# Compact proof retirement boundary

This source-only checkpoint follows `7f4f6dd`. Older predecessor reclamation
can visit a whole generation. Every material stage now retires that predecessor
before building its candidate, within the separate acquisition/staging budget.
Confirmation checks that this retirement has already occurred; publication
cannot reclaim a material generation inside the compact nonce operation.
Current/predecessor/stage retention remains within the accepted maximum, and
current native rows, change-base tags and original receipt contexts are retained
as before. Fresh baseline replacement already retires old material separately.

Proof decoding/canonical atom creation also enters the prepaid allocation scope,
including callback-produced receipt atoms. A regression test intercepts all
ledger releases across three confirmed generations and rejects any material
root reclamation during confirmation. Existing expiry, separate catch-up,
absolute deadline, repeated cancellation and failed-proof tests remain passing.

`proof-retirement-source.json` captures the exact before/after Mesh and Observer
source hashes and full logs. Python 3.14.8 passes the canonical 250-test core gate
with no skips (78 sync tests), design 116/delivery 169 checks, unchanged
33-input/25-schema lock check and Ruff; Observer's 28 source adapter tests pass.
This does not qualify actual two-millisecond native head CPU, network/installed
sync routes, aggregate RSS/plateau or the remaining matched performance gates.
The frozen appendix, old schemas/artifacts, package version, sibling sources and
deployed services are unchanged. Compact codec and publisher-role owning review
remain pending; no relay downgrade or dependent transport was implemented.
