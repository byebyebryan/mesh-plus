# Mesh Plus documentation

Start with [installation and first inspection](getting-started.md).
[Fleet Plus](https://dev.byebyebryan.com/fleet-plus/projects/mesh-plus/) provides
the product walkthrough and shared ecosystem presentation.

## Use and integrate

| Guide | Purpose |
| --- | --- |
| [Getting started](getting-started.md) | Install, inspect metadata and understand configuration prerequisites |
| [Host authority](ssh-plus-integration.md) | Single authority, public Host Mesh facade and directional route policy |
| [Integration handoff](handoff.md) | Compose an owner/profile/reader and choose independent validation gates |
| [Operations](operations.md) | Published artifacts, independent role pins and recovery ownership |
| [Architecture](architecture.md) / [components](components.md) | Authority, bridge, transport, profile and consumer boundaries |

## Interface reference

| Reference | Purpose |
| --- | --- |
| [Frozen boundary](contract-freeze.md) / [contract lock](../contracts/LOCK.json) | Normative state wire and exact frozen inputs |
| [SDK 1](sdk-api.md) | Pure profile, configured reader, poll/watch and lifecycle |
| [Publisher API](publisher-api.md) | Observer-owned cached publication and trusted fixed factories |
| [Prepared reads](prepared-consumer-api.md) / [owned admission](cpu-admission-api.md) | Explicit local preparation, expiry and selected summaries |
| [Diagnostics](sdk-diagnostics.md) / [profile conformance](conformance.md) | Read health and independent owner checks |
| [Complete-view feed](view-feed-api.md) | Separate opt-in change delivery; no production selection implied |
| [WSS](wss.md) / [owner selection](wss-owner-selection.md) | Optional transport configuration and independent adoption |
| [Active-only withdrawal](active-profile-retirement.md) | Retired standalone profile; working-set remains |

## Develop and investigate

[Development](development.md) explains source checks and documentation ownership.
[Source orientation](source-orientation.md) separates maintained main from retained
research worktrees. [Ecosystem ownership](ecosystem-role.md) records the local
interface boundary, while Fleet Plus carries shared product explanations.

The [history index](history/README.md) groups completed designs, delivery ledgers,
performance investigations and deferred experiments. Their old candidate labels,
provider tuples and future-tense steps belong to their checkpoint, not current
support or a new backlog. [`evidence/`](evidence/) retains exact dated inputs
and acceptance limits unchanged. Forwarding pages exist only to preserve links.
