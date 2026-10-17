# Lazy public value references

This source checkpoint follows `ef17118`; it is not G1/G2 acceptance. Opaque
root object/array references now select their type from owned canonical bytes
under the existing permit/lock checks. Creating a body reference and querying
its `materialization_bytes` do not decode its payload. An explicit read or
materialization performs the existing quota-accounted decode. Nested accesses,
scope checks and retirement remain checked. Both transaction and confirmed-view
owners share the same atom-resolution path rather than repeating divergent
lookup logic.

Immutable scalar outputs can share their value, as detached materialization
already does. Strings and integers have no backlink to a cache or generation;
holding a requested scalar cannot pin a retired tree. Packed scalar decoding is
prepaid before returning the requested value. Object/array payloads remain
revocable refs; no raw graph or admission capability is returned.

A regression test verifies zero body decodes for lookup plus copy-bound access,
exactly one decode at materialization, and immediate failure after disconnect.
`lazy-reference-source.json` captures exact input hashes and full logs. Python
3.14.8 passes the canonical 257-test core gate with no skips (85 sync tests),
design 116/delivery 169 checks, unchanged 33-input/25-schema lock check and Ruff.
Observer's 28 source adapter tests pass against the same byte-stable source.

Timing clarification for the preceding `CANONICAL-BULK.md` profiling discussion:
the cProfile cumulative figures (5.68/10.44 seconds) use its default elapsed
timer, not a process-CPU timer. The separately recorded diagnostic
`meshBaselineCpuMs` values use `process_time_ns`. Neither is matched installed
performance acceptance; the earlier profiler totals must not be interpreted as
component CPU savings.

The owning callback's whole-operation staging/pre-copy obligations, full
allocation/RSS/plateau audit, compact wire/codec/mask agreement, publisher role,
new reviewed schemas/artifacts, installed 3.11/3.14 and real sync IPC/fixed SSH
and all matched pipeline gates remain open. Frozen G0/schema/artifact bytes,
public semantic callback signatures, package version, sibling source and normal
services are unchanged. No dependent transport, relay downgrade or rollout was
implemented.
