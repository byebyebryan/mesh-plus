# WSS promotion proposal (review required)

This is a concrete follow-on proposal, not an accepted contract or SDK. The
isolated study demonstrates carriage of the released state protocol through
mutual TLS; it does not authorize packaging, listeners on real hosts or new pins.

## Proposed normative delta

Review these changes together before editing frozen inputs:

1. Increment `LOCK.json.lockRevision` from 1 to 2, use a new reviewed lock ID,
   add `wss` to `backends`, remove only `wss-runtime` from `excluded` and register
   digests of the reviewed WSS authority/configuration addendum. Preserve all
   existing native schemas, profile IDs, Read/Delivery envelopes and other
   exclusions. Do not regenerate unrelated schema bytes.
2. Extend the freeze's carrier lifetime section with native-client mTLS, mandatory
   server trust/hostname checks, exact fixed host/source/profile authorization,
   no Origin, compression, proxy discovery, redirect or SSH fallback. A listener
   exposes one trusted cached adapter. It never selects a collector or path from
   an untrusted frame. Existing setup-error versus malformed-close rules remain.
3. Make Read provenance explicit: every connecting, unavailable and ready remote
   WSS outcome reports `delivery.path = wss`. Tokens remain opaque to consumers;
   no Client attributes or transport function names establish backend authority.
4. Resolve revision/token ambiguity explicitly. Legacy factories retain their
   Host Mesh revision and SSH route token formula. The new composition owner
   produces `selectionRevision = sha256(canonical JSON)` of its binding protocol,
   Host Mesh revision, ordered registry and public local trust/client certificate
   configuration. That revision occupies Read's existing opaque catalog revision.
   Private keys and route health do not enter it. Existing SSH tokens remain
   derived from their separately captured Host Mesh revision and route index.
   WSS tokens hash exactly `{bindingProtocol, selectionRevision, hostId,
   endpointIndex}`. This is a reviewed factory interpretation, not a quiet
   reinterpretation of the legacy token rule. Mixed-backend acceptance must test
   both captured revisions and token formulas under one immutable selection.
5. Adopt bounded application policy observation: checks start at most five
   seconds apart while runnable, five-second BOOTTIME read budgets, failed checks
   revoke existing channels, then separately bounded cleanup. Certificate
   validity uses wall time; receipts and acquisition use BOOTTIME. Explicitly
   overlap certificate fingerprints during rotation. Any observed allowlist
   change conservatively retires prior sessions before readmission. No CRL/OCSP
   service or instantaneous remote revocation is implied.

The draft [registry](registry.schema.json) and [authorization](authorization.schema.json)
are concrete starting shapes. Their study namespace must be replaced only during
that review. Generic reserved endpoint/event schemas are not runtime formats.

## Proposed SDK and configuration work

Keep SDK v1 `Endpoint`, `Reader`, `Client.connect` and `configured_reader`
signatures and defaults. Add an opt-in module/factory, for example
`mesh_plus.wss.configured_reader(...)`, that accepts a captured `Selection` and
the existing pure profile. Expose a frozen backend binding with host, source,
profile, URL, endpoint index, revision and token. Ordinary imports must work
without the WSS extra installed; no plugin discovery.

Refactor Reader's private path construction into one overridable binding lookup,
or use a reviewed specialization like the study. Bind all outcomes and metrics,
including setup failure, before composition. Check the composed revision before
poll dispatch and each watch source acquisition; monitor every admitted client
catalog/registry/CA/certificate/private-key input. A changed or unreadable private
key revokes local authority without publishing its bytes or digest. Server trust,
credential and allowlist monitoring belong to the listener owner, not the client
catalog. ReadGuard and full checked nonce proofs remain unchanged.

Replace the study's positional authorization triple with a named object if
review favors readability; lock the chosen shape rather than supporting both
implicitly. Decide whether a registry entry references a separately named local
credential set or one selection-level set. The study deliberately uses one set;
per-endpoint credentials need independent bound inputs and tests.

## Implementation rules before packaging

The final study refinement implements graceful close with bounded abort, validates
decoding against the fragment deadline, uses BOOTTIME ticks for policy/ping checks
and hides captured private material from repr. The following remain promotion
requirements or regression rules; the operation byte counters and blocked-file
read boundary still need a reviewed runtime implementation.

- Preserve the study's supported Sans-I/O seam and pre-TLS admission. Review
  graceful WebSocket close against RFC 6455 as well as the required bounded abort
  path; a transport-safe TLS close alone is not a graceful WebSocket handshake.
- Include synchronous JSON/native validation in the first-fragment BOOTTIME
  deadline; exercise late validation and simulated resume, not merely read stalls.
- Schedule policy and ping checks against BOOTTIME deadlines when runnable;
  ordinary `asyncio.sleep` uses the loop's monotonic clock. Physical suspend
  still requires separate machine acceptance.
- Remove Client's inherited LF estimator from operation-result byte counters.
  The study's Channel/byKind counters count exact completed JSON messages, while
  some released Client operation counters add one byte. Preserve each byte scope
  in diagnostics and mixed fleets; never label these counters as encrypted bytes.
- Hide captured private material from object repr/debug output and retain owned
  snapshots. A bounded async wait cannot interrupt a blocked filesystem thread;
  decide whether promoted configuration reads use owned subprocesses or a
  documented local-file service boundary before promising hard cleanup budgets.
- Publish one total shutdown budget that accounts for parser/ping retirement,
  TLS shutdown and abort. Test pending TLS, partial headers, fragmented payloads,
  repeated setup/write/close cancellation, idle liveness failure and slow readers.
- Review aggregate setup and send budgets explicitly: the prototype has separate
  TLS/header/authorization budgets, and send encoding/schema validation precedes
  its write timer. Existing Client/Reader acquisition budgets still apply. A
  promoted generic carrier should include encoding and validation in its own
  BOOTTIME deadline rather than advertising a three-second aggregate opening.

These are Mesh-owned tasks. No producer field or native semantic change is needed.

## Packaging, conformance and operational sequence

Package reviewed optional modules with an extra such as
`mesh-plus[wss]` containing the selected websockets range; the study pins 17.1,
which declares Python >=3.11. Keep the standard dependency set unchanged. Add only
the newly reviewed configuration resources; original packaged schemas stay byte
identical. Build a new immutable version, never replace an a13 release asset.

Before release: standalone imports without extras or Observers, installed WSS
tests across supported Python versions, frozen/native profile parity, mixed
IPC/SSH/WSS provenance, authorization/configuration replacement and cleanup gates.
Keep source, private wheel, released asset and selected deployment evidence separate.

Observer owners can remain on existing SDK v1 pins. Later they choose the new
factory for their pure adapter/profile; provider collection, desktop actions and
UI remain outside Mesh. SSH Plus continues providing canonical Host Mesh identity
and its existing SSH health/history behavior. This study adds no SSH Plus route,
config or chooser integration. WSS-only host authority is a separate proposal.

Finally, install and select an opt-in listener on a disposable real fleet pair;
measure network loss, service/certificate rotation, restart, physical suspend,
WAN/firewall behavior and rollback. Rollback stops the listener, removes its
registry selection and returns to the separately pinned SSH configuration. No
automatic cross-carrier fallback is introduced. Operational files stay scoped;
docs and research runners remain in this repository, not chezmoi.

References: [Sans-I/O integration](https://websockets.readthedocs.io/en/stable/howto/sansio.html),
[Python socket ownership](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.connect_accepted_socket),
[RFC 6455 closing handshake](https://www.rfc-editor.org/rfc/rfc6455.html#section-7.1.2).
