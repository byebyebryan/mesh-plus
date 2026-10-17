# Actual Observer compact codec compatibility

Mesh independently executed the unchanged owning Observer component tests at
`c1ae31f575921e58e23dbcd59585128a143585a9` against immutable Mesh checkpoint
`cdb8cd0e3c5f11e65728d2de7c157e89ca26d819`. Its runtime is
`f32218bffab8860d374964721e35384f66a86269`, including the generic compact
retirement correction after the earlier `030da1f` integration target.

All 171 selected tests pass with no skips on Python 3.14.8 and 3.11.17, with
cyclic GC disabled and retained errors/handles. These include the 15 actual
compact codec/profile tests and the relevant parser, compact/expanded structural
facade, expanded profile/Reader and legacy source component tests. The owning
test assertions check final ledger retirement, including the compact cache's
five counters and pending encoded bytes. This is independent execution of
Observer's tests, not an independently authored test suite or a real producer
acceptance run. Its separate 899-test source gate was not rerun here.

The configured `AgentCompactSyncCodec` uses the committed public frozen spec,
AliasViews, keyed before/after record lookups, per-space DTO iteration and
single-consume `ctx.pack`. The optional profile feature is explicit. Compact
callbacks supply derived field tokens, leave `membership_expansion == ()` and
preserve generic single-writer expansion and independent root checking. No
private Mesh admission/cache graph or alternate authority path is introduced.
The head decoder keeps the original LF frame and never opens a body schema.
The R4 transport scanner remains a separate Mesh-free role.

The selected cases admit all eight frozen baselines and ten transactions to
their expected native roots and reject eight schema-valid negative fixtures at
the intended codes. They also cover equal/omitted-mask token changes, exact
receipt-dictionary sides/existence, explicit features and strict no-fallback
behavior, saved retired handles, pre-read reservation refusal and schema credit
through reentrant close. Both synthetic full/active fresh-proof paths restore
the exact public native DTO. Runtime wrappers use explicitly configured valid
`agents_full`/`agents_active` selectors and independently recomputed source roots;
the unchanged dotted-name fixtures remain arithmetic-only inputs.

No interface conflict was found within these cases. The reviewed raw proposal,
schema, vector and verifier bytes remain unchanged. This records compatibility
for continued unselected G1 source integration; it allocates/freezes no schema
or encoding ID and changes no default, artifact or selected route.

The [review evidence](evidence/2026-10-16-delta-sync/observer-compact-review.json)
pins immutable source/test/schema inputs, the runner, logs and loaded modules.
The parser's conservative eight-MiB schema credit is included in these small
operations. Harness/import/raw fixture/oracle storage is outside their ledgers,
so these results establish neither aggregate 32/64-MiB capacity nor RSS, dense
2,000-row capacity, sparse complexity or CPU/cold/recovery byte gates.

Native compact serialization/journal/source dispatch and real populated
IPC/fixed SSH remain unqualified. Source completion, consuming-ref retirement,
controller grammar, original failed dense/recovery gates and an independently
qualified immutable installed pair remain separate open work. No sibling,
provider, service, package, a7/a23 selection or rollout changes occurred.
