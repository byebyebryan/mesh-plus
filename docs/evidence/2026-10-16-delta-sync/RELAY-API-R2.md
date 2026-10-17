# A1 relay exact-interface review handoff

Planning/source checkpoint, 2026-10-16. This supplies the concrete pending A1
interface review; it does not repeat the role amendment or accept a producer.

Owning location is **Starship**, checkout `/home/bryan/code/mesh-plus`, branch
`mesh-delta-sync-20261016`. The exact packet is
[`docs/delta-sync-relay-api-r2.md`](../../delta-sync-relay-api-r2.md), SHA256
`8616bfba7c05dcf8982e431309bcd0bdf354c91bc023fdf0fcf85dcbe4c7abdd`,
27,392 bytes. Later edits require a new announced revision/hash and same-byte
counterpart review. The original packet and the agreed cache-input document
are retained unchanged; the supplement distinguishes its proposed relay owner,
ref and consumer types from the existing cache-backed input seam.

The packet specifies trusted factory/channel operations, explicit role/encoding
negotiation, a structural source/scanner protocol, ownership transfer through
output drain, exact nested delivery/proof framing and lease attenuation. Relay
refs are byte ownership only. They cannot skip Reader validation, mint semantic
views, carry profile decisions or act as admitted-material reuse capabilities.
The factory accepts no semantic profile and creates no material cache.

The independent-of-runtime stdlib arithmetic oracle is
[`scripts/reproduce-sync-relay-vectors.py`](../../../scripts/reproduce-sync-relay-vectors.py),
SHA256 `defeb1d4c67b811a3fefc3f3586759d8005fd758cbe19bf110bbdca2469defcf`,
9,594 bytes. Its retained
[`relay-api-r2-vectors.json`](relay-api-r2-vectors.json) is SHA256
`968ea89860e86fc8493681f6a8edc472c99794fbf580275d9bde5a2efa29c39d`,
12,690 bytes. Twelve formula/framing fixtures and four attenuation rejection
fixtures reproduce exactly on Python 3.14.8 and 3.11.17. Role/encoding request
hashes differ, two aliases preserve one native tag with distinct source wrappers,
and the noncanonical native head bytes survive envelope splicing unchanged.
The fixtures use toy descriptors and unverified native roots; they do not
validate an Agent payload, callback implementation, transport or ownership peak.

Commands executed in this checkout:

```sh
rtk proxy .venv/bin/python scripts/reproduce-sync-relay-vectors.py --check docs/evidence/2026-10-16-delta-sync/relay-api-r2-vectors.json
rtk proxy /home/bryan/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11 scripts/reproduce-sync-relay-vectors.py --check docs/evidence/2026-10-16-delta-sync/relay-api-r2-vectors.json
rtk proxy .venv/bin/python scripts/check-contract-lock.py
rtk proxy .venv/bin/python scripts/check.py
```

The selected Python 3.14.8 canonical gate passed: 33 locked inputs/25 identical
packaged schemas, 116 offline design checks, 169 delivery checks, 276 core tests
with no skips, and Ruff over src/tests/scripts. No runtime, contract, test or
packaging file changed in this checkpoint. A preliminary invocation used the
nonexistent `scripts/check-lock.py` name and failed before running; the actual
`check-contract-lock.py` and the canonical gate then passed. No gate was bypassed.

Unchanged inputs are frozen G0 appendix SHA256
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`,
old LOCK SHA256
`11736752d08b7e29688a5816327b86477a615b1c7af8c76bfb47278dcc1890a4`,
root A1rev2 commit `665f6caaed99740a755de9467c7ae53322f7e720`/SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`,
original Mesh packet SHA256
`05e5a9bef61d0235d6d82c326e630209dac610a122f581117bdb65beaa36183d`,
and common cache-input contract SHA256
`7f7751ecd9df93277a3e7110ca72ebfda343d38fa629cd0212ec40b3a8f1d124`.
The common input agreement receipt remains `7f92bab`; current runtime source
remains `1d50db0`. Current package metadata stays a23; no artifact was built.

Observer same-byte exact API/clock/context/lifecycle agreement and RLCD's A1
acceptance record are pending. Compact codec/native domain-vector agreement,
native owned-source implementation, real IPC/fixed SSH, installed paired wheels,
full intake/output/pin/DTO resource accounting, paused/cancelled/failure cleanup,
dense CPU, cold/recovery and full end-to-end gates were **not** run or accepted
by this packet. Dense `100637b` source +126.82% and six baseline-required
retirements remain explicit failures. Timestamp target support and packed-layout
frame feasibility remain separate evidence. No sibling edits or rollout.
