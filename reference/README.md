# Frozen source references

These source contracts, fixtures and documents are copied byte for byte from
reviewed producer checkouts. Repository revisions, original paths and SHA-256
hashes are recorded in [source baselines](../docs/evidence/source-baselines.json).
Default validation verifies these hashes without requiring sibling checkouts.
The optional `--check-sources` gate additionally verifies the current producer
heads, file bytes and pure semantic validators.

Source Markdown is preserved unchanged for provenance. Its own relative links
may reference files outside this selected snapshot; resolve those against the
original producer revision. Mesh design documents link directly to the frozen
files so the main design remains readable in a standalone checkout.
