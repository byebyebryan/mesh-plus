# Development

Use Python 3.11+ and maintained `main`. Inspect the branch/worktree before
editing and preserve research checkouts and unrelated work.

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
| `docs/guides/` / `docs/reference/` | Current workflows and interface references |
| `tests/fixtures/` / `artifacts/` | Executable fixture inputs and artifact provenance |

## Documentation maintenance

Keep only `README.md` and `getting-started.md` at the docs root. Use lowercase
kebab-case filenames in one shallow topic folder: `guides/` for workflows,
`reference/` for current interfaces, and `maintenance/` for development/operations.
Media belongs in `assets/`. Mesh's hash-locked `contract-freeze.md` is the sole
root exception; its original bytes remain normative input.

Update or consolidate the existing guide instead of adding a dated plan,
handoff or status page. Delete superseded notes; Git retains earlier revisions.
Do not add forwarding pages or copy old reports into the current docs tree.
Keep executable test data beside tests, not under docs. Record necessary release
provenance with an immutable Git/release link in the operations guide.

Run `scripts/check-docs` and the canonical source gate before committing. The
docs check enforces this layout and checks local links/heading fragments.
Package, native, managed, consumer and physical acceptance remain separate.
