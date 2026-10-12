# Optional WSS owner reader selection

2026-10-12 source review during the coordinated performance pass. This is a
networking handoff, not a selection or promotion decision. Ordinary readers
remain on IPC/SSH. The [execution ledger](evidence/2026-10-12-performance/README.md)
binds current installed and trial artifacts.

The accepted Tmux a7/Agent a20 publishers work with Mesh a15's optional WSS
listener using their unchanged owner factories and pure profiles. Agent's
private allocation candidate changes neither that construction nor the API.
SDK interface 1, Read/Delivery 1 and both native profiles remain the same.

The current reader wiring still constructs `mesh_plus.api.configured_reader`:
Tmux in `tmux_observer_client._mesh_worker`, Agent in `agent_observer.mesh_cli`.
Those constructors select IPC/SSH. Merely installing the optional WSS dependency
or starting a listener does not select it in either owner. This is the remaining
networking adoption step if a later decision chooses WSS.

## Required owner-side wiring

1. Resolve an explicit networking selection before starting a read/watch owner.
   Keep IPC/SSH the default. No transport choice comes from domain rows, provider
   metadata, desktop policy or a peer's payload.
2. For optional WSS, construct `mesh_plus.wss.Selection.load` from the five
   private inputs: captured Host Mesh catalog, endpoint registry, CA, client
   certificate and key. Install the reviewed optional dependency explicitly.
3. Pass the existing pure profile, source and local Mesh IPC socket to
   `mesh_plus.wss.configured_reader`. It returns the same Reader-style snapshot/
   watch interface and frozen result shape. Its constructor differs from the
   IPC/SSH authority constructor because the selection owns registry and trust
   inputs. Keep that difference inside the networking binding layer.
4. Retain the existing `ReadGuard`, reconstruction, current-row calculation,
   original receipt expiry and request-scoped stream lifetime. Close the Reader
   stream before `Selection.close()`. Selection changes revoke the watch and
   require a fresh selection; they do not mutate an existing authority owner.
5. Registered remote hosts use WSS; other captured remote hosts use SSH. Failure
   of a registered WSS endpoint remains its unavailable host outcome, with no
   automatic SSH fallback. WSS tokens/trust revisions remain distinct from SSH
   route health. The WSS factory does not accept IPC/SSH `report_routes` policy.
6. For SDK assessment, use `mesh_plus.diagnostics.assess(reader, ...)` after
   constructing the selected Reader. `assess_configured` is the IPC/SSH helper;
   it does not select WSS from networking metadata. Snapshot/probe/watch have
   separate delivery and native-evidence outcomes.

No Tmux Plus or Agent Plus implementation belongs in this binding step. It
does not add collectors, provider semantics, actions or new native contracts.
Authority configuration/history remain separately owned. SSH Plus does not
need a publisher or a WSS reader for its Host Mesh authority/picker role.

## Acceptance and operations

Before ordinary selection, each owner should prove mixed fleet native cached
poll/push, exact profile/host/source/nonce binding, registry/trust revocation,
failed-host isolation, reproof after reconnect, original lease preservation and
owned cleanup with its actual reader lifecycle. The coordinator must accept
native/fault/resource and rollback gates on the exact selected tuple.

Per-listener four-channel admission is not Tmux's 32 prepared downstream-reader
capacity. Existing prepared sharing and four raw upstream readers need separate
measurements. Dedicated listener ownership, private key provisioning/renewal,
certificate overlap/removal, startup dependencies and physical suspend acceptance
are operational gates. The current isolated trial does not enable managed units
or establish an unconditional default recommendation.

A later selection proposal should name exact wheels/dependencies, listener
owners, registry/catalog and credential locations, required private permissions,
the scoped managed diff and the previous IPC/SSH reader construction. Rollback
selects the prior constructor/pins and retires only the owned WSS listeners and
trial rules. Runtime failure does not perform that policy change automatically.
