# Mesh Plus

Start with `README.md` and `docs/guides/integration.md`. `docs/contract-freeze.md` and
`contracts/LOCK.json` define the accepted state-only boundary. Historical studies
and reserved schemas do not advertise additional runtime capabilities.

`docs/reference/architecture.md` describes current ownership. Mesh/SSH remain
the multi-host backbone. Agent Observer supplies Codex read-only observations;
Agent Plus independently opens native Codex/Claude managers through Host Mesh.
Tmux's generic workflows remain supported. Do not restore the former
Agent Plus -> Tmux -> agent-runtime dependency through a cleanup or migration.

Preserve the frozen wire contract and packaged schema bytes. A normative change
requires explicit review; do not regenerate the lock merely to make checks pass.
Compatible implementation fixes do not require a wire rename.

Keep transport and authority free of provider collection, desktop policy and
actions. Domain semantics come from supported pure Observer facades. Do not
infer current state from missing, partial or stale producer evidence.

`authority.py` preserves the reviewed SSH legacy extraction. Changes require
Host Mesh compatibility review; config, route-health and picker history ownership
must remain distinct. Source version, candidate wheel and deployed pins are
separate evidence. Never overwrite a released artifact or silently deploy a new
candidate as part of a source refactor.

Use `rtk` for shell commands in this workspace. Run the canonical gate with the
selected Python environment: `rtk proxy .venv/bin/python scripts/check.py`.
`--native` requires the reviewed Observer packages and owns disposable fixtures;
`--check-sources` additionally reads sibling checkouts. Packaging changes need an
isolated wheel check. Record exact inputs, exclusions and any skipped tests.

Keep project docs, scripts and acceptance evidence in the owning repository.
Use chezmoi/dotfiles only for deployment configuration that actually needs management.

Stage intended files only. Preserve frozen references and immutable release
artifacts. Acceptance belongs to its recorded tuple; source cleanup does not
accept new runtime bytes. Do not edit, migrate or deploy sibling projects without task scope.

Documentation starts at `docs/README.md`. Only entry points and the hash-locked
freeze belong at the docs root. Use lowercase kebab-case names in shallow
`guides/`, `reference/` and `maintenance/` folders. Delete superseded plans and
ad-hoc receipts; Git keeps earlier revisions. Do not add compatibility pages or
new history/evidence dumps. Machine inputs belong under tests/fixtures.
Run `scripts/check-docs` and the canonical source gate; retain frozen schema,
contract/lock and reference bytes. Deployment/consumer/physical gates remain
independent. Preserve concurrent work and research branches.
