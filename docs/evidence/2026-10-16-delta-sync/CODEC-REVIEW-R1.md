# Compact codec contract and arithmetic review packet

This packet responds to RLCD `e-843c848b`. It is a candidate for same-byte
Observer/RLCD agreement before shared implementation, not an ABI/schema freeze.
No `src/` file, contract lock or packaged schema changed in this checkpoint.

| Input | SHA256 | Bytes |
| --- | --- | ---: |
| `docs/delta-sync-codec-contract-r1.md` | `a67f11aee6c4b9f50048fbda55bdd4f82c6766ec69cd07abf31b749c3ba5b0b8` | 14779 |
| `scripts/reproduce-sync-codec-vectors.py` | `2363e95bd4e254858e8eb937cf5267f1506b338451f8c61c96df9b25edf95c3d` | 18612 |
| `codec-review-vectors-r1.json` | `5a2abd9ecf309acf9fd37de54bcaa05ef636bcfc07e8a96ab6e549e5dd409adb` | 97800 |

The contract pins before/after alias resolution, guarded births and alias reuse,
single-key operations, exact mask absence/null/zero/ranges and duplicate rules.
It separates provisional masks from final field tokens/cells, requires exact
eight-table/grouped-seal equivalence and atomic rollback, and defines candidate
scope/ownership, callback identity, head-only, quota and sparse-work obligations.
New candidate API details for owning review include per-space operation
iteration, provisional membership queries and generic-owned CanonicalValueRef
packing instead of unowned canonical bytes. No shared codec is implemented.

The stdlib oracle has eight positive arithmetic cases, 37 rejection cases and
four distinct optional-value token inputs. It compares sparse cell arithmetic
with an explicit full membership rebuild and all eight table/seal results on
toy JSON values; they are not Agent API 4 rows. Permutations include deletion/
insertion with the same alias and distinct births. It records expected logical
key changes, not measured runtime visits. Strict JSON checks are arithmetic
parser fixtures, not the future complete compact native schema admission.

Reproduction passed byte-for-byte on Python 3.14.8 and 3.11.17:

```text
rtk proxy .venv/bin/python scripts/reproduce-sync-codec-vectors.py --check docs/evidence/2026-10-16-delta-sync/codec-review-vectors-r1.json
rtk proxy /home/bryan/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11 scripts/reproduce-sync-codec-vectors.py --check docs/evidence/2026-10-16-delta-sync/codec-review-vectors-r1.json
rtk proxy .venv/bin/ruff check scripts/reproduce-sync-codec-vectors.py
rtk proxy .venv/bin/python scripts/check-contract-lock.py
```

The new oracle also matches four exact frozen G0 roots: empty records, a/A,
a/A+b/B and the p=2/c0 a/A+c/C branch. The lock check passes 33 locked inputs
and 25 identical packaged schemas. The original compact proposal remains
SHA256 `4187fd9befabba300e2f8a36a653f4d2b564c1c0157cc9e35089cd09f47f9f56`;
the G0 appendix remains `a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`.

Observer independent same-byte/API confirmation and joined native extraction,
body/observation/support vectors are pending. So are actual codec admission,
callback/root rollback, plan/iterator/context retirement, no-body head, binding
replacement, GC-disabled held-error cleanup, quota and sparse-visit tests. The
JSON explicitly lists pending runtime cases; arithmetic success does not execute
or accept them. No resource/CPU/RSS/byte-gate claim is made for this oracle.

A1 root review is already issued; joint producer agreement remains separate.
Owned source intake agreement/qualification remains its own gate. Prototype
50-test/33 MB findings and the preserved `68fb8a4`/220-test checkpoint are not
relabelled by this packet. Dense decoded and expanded-wire capacity failures
still block G1 promotion. No caps, deadlines, authority checks, package/version,
sibling runtime, normal role, installed selection or deployment changed.
