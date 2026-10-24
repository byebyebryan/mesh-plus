# Mesh Plus documentation

Start with [getting started](getting-started.md). The [repository README](../README.md)
is the short project entry point; [Fleet Plus](https://dev.byebyebryan.com/fleet-plus/)
carries the shared showcase and project relationships.

## Guides

| Read | Purpose |
| --- | --- |
| [Host routing](guides/host-routing.md) | Single authority, directional scope and SSH facade |
| [Integration](guides/integration.md) | Profiles, publishers, readers and separate acceptance gates |
| [Optional WSS](guides/wss.md) | Explicit transport/trust configuration |
| [Optional change feed](guides/change-feed.md) | Complete-view change delivery |

## Reference

| Read | Purpose |
| --- | --- |
| [Architecture](reference/architecture.md) | Authority and cached delivery boundaries |
| [SDK](reference/sdk.md) | Pure profile and Reader interface |
| [Publishers](reference/publishers.md) | Observer-owned cached publication and fixed factories |
| [Prepared reads](reference/prepared-reads.md) | Optional consumer preparation interface 1 |
| [Admission and selection](reference/admission.md) | Owned admission and selected summaries |
| [Diagnostics](reference/diagnostics.md) | Metadata and cached validity assessment |

## Maintenance

| Read | Purpose |
| --- | --- |
| [Profile validation](maintenance/profile-validation.md) | Independent owner conformance |
| [Development](maintenance/development.md) | Source setup and explicit optional gates |
| [Operations](maintenance/operations.md) | Releases, selections and recovery ownership |

The [contract freeze](contract-freeze.md) is hash-locked historical normative
input. Current profile support is described in the SDK and operations guides.

These pages describe maintained behavior. Superseded plans, status notes and
old receipts are kept in Git rather than in this documentation tree.
