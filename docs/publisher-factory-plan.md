# Publisher ownership seam review and implementation plan

2026-10-11. Mesh-only implementation following the Observer publisher feasibility
review. Both Observer work streams are paused pending this public producer seam.
No Observer, desktop, authority, deployment or native collection changes belong
in this checkpoint.

## Decision

Add an explicit-profile generic `CachedPublisher`, frozen `CachedPublication`
and structural `CachedSource` in `mesh_plus.publisher`, exported by
`mesh_plus.api`. Observer sources own cached native acquisition/validation,
UID/clock/request/order checks and iterator cleanup. Mesh owns envelope/digest,
original-receipt remaining leases, proof construction and Delivery carriage.
A proof calls a new source snapshot after nonce validation; retained watch data
never substitutes for that acquisition.

Add keyword-only `publisher_factories` to `cli.configured_adapter`, `cli.run`
and `cli.main`, and optional WSS CLI run/main. The mapping is supplied only by
trusted installed Python launcher code, keyed by tmux/agent, with synchronous
factories `(host, source, socket)`. No module/executable/plugin selector is added
to CLI, sources.toml, wire or remote SSH command. Omitted domains retain the
reference adapter; a selected broken/missing-return factory fails terminally.
Host/source/profile, supported capabilities and required methods are checked
before endpoint publication. Factories must acquire no resources; native source
operations own all resources per invocation. No process-global publisher close
protocol is added.

The mapping is copied before dispatch, factories remain lazy, and the Host Mesh
stdlib fast path bypasses all publisher/state imports. IPC, SSH stdio and WSS
listeners use the same construction seam. Remote adoption requires a trusted
launcher named mesh-plus in the selected remote environment; changing local
Python code alone cannot change remote installed selection.

## Compatibility review

This is a compatible Python implementation extension, not a normative wire
change. Preserve LOCK.json and all normative/schema bytes; SDK interface stays
1 and existing defaults remain. Existing source descriptors and remote argv
remain unchanged. Use a new a15 candidate rather than overwrite accepted a14
private WSS bytes. Neither candidate is deployed or released by this pass.

## Acceptance sequence

1. Review and commit this plan; inspect existing generic profile/CLI constraints.
2. Implement helper and factory hook with independent pure fixtures; test mutation
   isolation, counter/lease monotonicity, failed admission, proof acquisition,
   binding rejection, push/restart and cancellation cleanup for both domains.
3. Validate canonical standalone/native/WSS gates with exact inputs. Use real
   owned SSH and configured IPC entrypoints plus WSS factory coverage. Preserve
   reference fallback defaults and authority import isolation.
4. Freeze a fresh private wheel; test installed imports/CLI, exact source/schema
   parity and owner conformance. Record skipped/excluded gates explicitly.
5. Commit acceptance and precise owner handoff. Observer-native/resource/managed
   adoption remains independently owned; no study results certify changed bytes.

The helper trusts installed pure profile code and source code. Synchronous
callbacks are bounded by checks after return, not preempted. This checkpoint
adds no global CPU/memory bound, pool, action, events or collection capability.
