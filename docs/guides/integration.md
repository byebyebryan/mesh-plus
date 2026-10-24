# Integration handoff

Mesh owns reusable authority and cached-state delivery. Observers own native
meaning and pure profiles; consumers own presentation and actions. Start with
[getting started](../getting-started.md) and [architecture](../reference/architecture.md).

## Select interfaces explicitly

| Domain | Native/profile selection | Owner |
| --- | --- | --- |
| Agent full state | API 4 / snapshot 6 / Service 4 / explicit Agent v3 profile | Agent Observer |
| Agent working-set | Working-set v1 / explicit working-set profile | Agent Observer |
| Tmux | Independently versioned Tmux observation/service/profile | Tmux Observer |
| Host authority | Host Mesh v1 process facade or supported library/native selection | SSH Plus public contract; Mesh implementation |

Mesh SDK 1 and Read/Delivery 1 are distinct from each native/profile version.
The SDK retains legacy defaults for compatibility; current Agent clients must
pass their explicit reviewed profile, rather than assuming the default means
the latest native contract. Standalone Agent active-only support is withdrawn.

## Compose an integration

1. Resolve the intended endpoint's configured authority and directional scope.
2. Select the compatible producer package and pure profile; preserve exact
   host/source/home identity and uncertainty.
3. Host the owner's cached service independently. Configure a fixed source and
   Observer-owned publisher factory. A bridge exports no aggregated fleet.
4. Use [`configured_reader`](../reference/sdk.md) with that explicit profile and source.
   Keep admitted/prepared consumers bound to the same profile instance.
5. Apply public domain selection and current-time expiry. Handle unavailable,
   partial, warming, gap/resync and disconnect without inventing positives.
6. Close owned streams/clients and revoke current views on loss or cancellation.

See [publisher API](../reference/publishers.md), [prepared consumer](../reference/prepared-reads.md),
[owned admission](../reference/admission.md) and [diagnostics](../reference/diagnostics.md).
Core Mesh never collects from providers or dispatches desktop/lifecycle actions.

## Validation

Run the [standalone source gate](../maintenance/development.md) first. It requires no sibling
checkout or native provider. Optional gates have different evidence scopes:

| Gate | Establishes |
| --- | --- |
| Source/contracts | Frozen bytes, synthetic lifecycle/proof/expiry and lint |
| Owner conformance | Pure profile behavior against the declared native contract |
| Isolated wheel | Package resources/imports and installed public interface |
| Native/SSH | Exact producer and transport behavior using owned resources |
| Consumer | Adopted read path, uncertainty, presentation and cleanup |
| Managed rollout/recovery | Selected bytes, role configuration and paired rollback |
| Graphical/physical | Actual input, focus or device behavior in the recorded scope |

A source or package pass does not establish later gates. No test count from an
older tuple transfers to a different artifact. [Conformance](../maintenance/profile-validation.md)
and [operations](../maintenance/operations.md) identify owner tools and release records.

## Supported scope

The published a25 release supports the reviewed full/working-set/Tmux/authority
interfaces with independent role pins. Ordinary readers retain complete views;
optional WSS/view-feed adoption needs its own consumer gate. Delta-sync remains
dark after failed CPU/capacity qualification.
