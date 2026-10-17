# Unified private profile ownership checks

This follows RLCD `e-3153acdb` without rewriting the original
[private packed-node report](PACKED-NODES.md). Root's separate pre-copy probe
demonstrated that the unchanged Observer resource assertion passes when its
test store owns the private arena and closes it at `store.close()`. The prior
30-case report and its exclusion remain exactly as published.

The new [private harness](verify_packed_owned_profile.py) adopts explicit fixture
ownership. It creates one arena per test ledger, tracks its owning stores, and
closes that arena after the ledger's last store closes. It neither edits nor
patches Observer's tests, assertions or teardown. In particular, the in-method
pre-copy assertion runs after its own `store.close()`, with no arena reservation
left behind. Closing one store cannot close another live store's shared arena.
The runtime's standard store/cache ownership and every production factory remain
unchanged. This is an in-memory test harness for the private backend only.

## Exact pairs and new results

Both Python 3.14.8 and 3.11.17 pass every discovered profile test with cyclic GC
disabled and no collection, skips or exclusions:

| Immutable Mesh source | Immutable Observer source | Cases per Python | Report SHA256, identical across Python versions |
| --- | --- | ---: | --- |
| `18e95c1791e66d20a211aa7d96b44d49b7fb78b7` | `4030d50c0d21c1e34daad45c29e2373502a3413a` | 31 | `d3e1a6391190219b02fbefbb0acd79b04e1fbc2e018113a3d0c4083458af4219` |
| `66b9c1e9c170dbfab847c1c691a6b7b11c9eff13` | `af2bc7bf9316bc0fb58c83ec8f560a83788467e4` | 32 | `a4c051ca6f1154313d53cb6daaa63b40b7e07222f1af331a5047d6308610f871` |

Each pair includes unchanged
`test_body_reservation_rejection_precedes_detached_copy`. The current pair has
one additional Observer case:
`test_structural_relay_ticket_cannot_bypass_independent_domain_or_root_admission`.
That is a source-level pure structural-ticket/Reader admission check; this run
does not implement or test an actual relay connection, native service or proof
timing. The complete original semantic/order/expiry/partial-support assertions
also execute unchanged.

After each case all ten audited counters are zero: heap, reserved heap, encoded,
reserved encoded, pending units/encoded, allocation units, live private nodes,
maps and controls. The harness's live owner registries are empty. It rejects
explicit collection attempts and checks that GC remains disabled after each
case; both pairs record zero attempts. These are
bounded fixture cleanup observations, not physical RSS/plateau or whole-process
allocation accounting. The report retains a row per case/arena; it does not
retain retired fixture graphs as audit history.

All four source exports are created from their exact git commits and verified
after the runs. The new [manifest](packed-owned-profile-review.json) binds their
source/test files, commands, all four raw logs/reports, the harness, and root's
separate pre-copy inputs. Root's `precopy.py` SHA256 is
`323fc6692b73aa6bd740d64c080f8c2d1b29f6058273a3bf16db50435e0ff661`;
`precopy-results.json` SHA256 is
`ccf7152a7a699d984cb656eaf3352ba76be170aeaeac90fee846141015594a6f`.
No sibling file is changed or invoked as a mutable test dependency. This adds a
new 31/32-case source qualification; it does not retroactively rename the old
30-case gate or old default compatibility counts. The `*-initial.*` reports/logs
precede the explicit GC monitor and are retained as development-only inputs;
only the final filenames/table above bind this harness revision.

Reproduce in fresh output paths, selecting source exports explicitly:

```sh
rtk proxy .venv/bin/python docs/evidence/2026-10-16-delta-sync/verify_packed_owned_profile.py --mesh-source /path/to/immutable-mesh --observer-source /path/to/immutable-observer --output /path/to/new-result.json
```

## Unchanged limits and remaining work

No runtime file changes in this checkpoint. The original density experiment
remains bound to `18e95c1`: 2,000 rows per view fits its structural two-view
fixture at 65,238,013 accounted peak heap, leaving 1,870,851 bytes before actual
Agent indexes/bodies/intake/output/pins. Its final encoded 17,818,566 bytes is
not a measured encoded peak. None of those figures is rerun or reattributed to
the newer pair here. The existing 64 MiB heap/32 MiB encoded caps stay fixed.

Actual private accesses around 13,000 versus roughly 700 logical reads and the
historical cold CPU regression remain profiling concerns. These correctness
runs were concurrent disposable processes and yield no matched performance or
peak-resource result. Dense/cold/packed-recovery CPU/bytes, inclusive aggregate
resources/RSS/plateau, real populated IPC/fixed SSH, immutable installed pairing
and G1/G2 acceptance remain open. The later A1 and compact interface agreements
are recorded independently; their implementations/schema gates are not settled
by this fixture harness. No API, artifact, package, service/provider, route,
consumer, sibling or rollout action occurs.
