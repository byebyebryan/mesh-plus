# Dense material resource review

G1 promotion remains blocked. `normalized-density-diagnostic-r1.json` (SHA256
`94eb0e389080a5eb5d37d4864714200085d47d0113d370670a3ac4c1ea221372`)
tests the current generic normalized material independently of the oversized
Agent wire. The script is `scripts/profile-sync-density.py`; exact runtime and
script hashes, deterministic inputs and source stability are in the report.

It uses minimal reference bodies, all nine field tokens per record, one cohort,
no declared domain indexes and one shared 64 MiB decoded/32 MiB encoded ledger.
The two views use different descriptors. They are structural independent views,
not the Agent full/active semantic pair. Caller-owned normalized fixtures and
their full oracle are outside this cache ledger. No input frames, proof, source,
network or installed package participates; these are not total RSS or latency
acceptance results.

| Records per view | First-view retained bytes | Both retained bytes | Accounted peak | Result |
| --- | ---: | ---: | ---: | --- |
| 100 | 2,548,579 | 5,087,774 | 6,558,965 | both material roots admitted |
| 500 | 12,596,396 | 25,183,396 | 31,940,541 | both material roots admitted |
| 2,000 | not committed | second not attempted | 63,897,393 | first stage rejected by decoded capacity |

The 2,000-row rejection is a prepaid capacity failure; its peak being below the
cap does not imply the next requested allocation fits. Every case closes with
zero retained, reserved, encoded and pending allocation units. This finding is
separate from the known expanded native frame failure at 2,000 Agent rows.
Compact wire alone does not demonstrate that dense decoded storage fits.
The earlier `normalized-density-diagnostic.json` is a draft run of the same
stress with its own captured script hash, retained for history.

Proposed next storage work preserves all accepted C/H framing, logical tables,
birth/cohort identity, independent validation and public callback/query shapes:

- Avoid expanding compact masks into N-per-field public operation/ref objects
  before the semantic callback. This depends on the jointly reviewed provisional
  mask/normalization interface; that interface is not implemented yet.
- Prototype compact immutable hash-node records with explicit per-node live
  edge ownership and quota-accounted backing pages. Private refcounts/free-slot
  metadata may change; live semantic records cannot. Dead nodes must not retain
  old child graphs merely because a page contains another live node.
- Preserve exact canonical keys, token values, expected-value checks and roots.
  Any compact membership representation must expose the same logical lookup
  and metered enumeration, independent of the wire aliases.
- Count pages, unused page capacity, tables, payload references, controls and
  canonical buffers before allocation. Reject ABA/stale handles; prove bounded
  current/predecessor/stage retention and deterministic cleanup with GC disabled.
- Compare every new representation against the existing independent root oracle,
  all hash/permutation/adversarial tests, sparse visit bounds and fixed numeric
  CPU/bytes/RSS/plateau gates. Do not reduce accounting allowances or raise caps
  to turn this result into acceptance.

This is a review proposal, not an allocated package or changed representation.
The native compact codec/mask/alias contract and publisher admission/relay role
also remain open. Mesh source checkpoint `95c406f` passes 259 core tests and the
updated Observer source's 31 adapter tests with exact hashes; it does not freeze
G1 or qualify an installed pair. No sibling runtime, normal service, consumer,
firmware, deployed pin or immutable artifact was changed.
