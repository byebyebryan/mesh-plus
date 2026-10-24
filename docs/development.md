# Development

Use Python 3.11+ and maintained `main`; see [source orientation](source-orientation.md)
before changing a multi-worktree checkout.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . jsonschema==4.26.0 ruff==0.16.10
python scripts/check.py
```

This canonical standalone gate checks frozen contracts, design/adversarial
fixtures, delivery, view-feed, core runtime and Ruff. It needs no native
provider, sibling checkout or managed endpoint.

## Additional gates

```sh
python scripts/check.py --wss
```

Install the declared WSS extra before that optional gate. `--native` additionally
requires the reviewed Observer packages and owns disposable native/SSH fixtures;
run only within an authorized native acceptance scope. `--check-sources` reads
the recorded sibling source baselines and is not the normal standalone gate.
An isolated wheel check is required for packaging changes.

## Repository map

| Path | Contains |
| --- | --- |
| `src/mesh_plus/` | Authority, SDK, delivery, optional WSS/view-feed and pure testing interfaces |
| `contracts/` | Normative contracts, schemas, corpus and lock |
| `reference/` | Frozen producer contract inputs; not live sibling implementations |
| `tests/` / `scripts/` | Synthetic, conformance, package and explicit native gates |
| `docs/` | Current guides/reference |
| `docs/history/` | Completed designs, rollout ledgers, performance studies and experiments |
| `docs/evidence/` / `artifacts/` | Dated acceptance inputs and immutable artifact records |

## Documentation maintenance

Keep current guidance linked from [the index](README.md). Move completed plans
and investigations to history with an explicit checkpoint label. Update ordinary
links and retain short forwarding paths for immutable receipts/external clients.
Do not append release ledgers to the README or architecture.

Never rewrite `docs/evidence/`, frozen reference inputs, schemas or lock digests
to make a navigation check pass. A normative change needs separate review.
Validate local paths/heading fragments and preserve dated acceptance limits.
Source, release, installed role, consumer and physical evidence stay separate.
