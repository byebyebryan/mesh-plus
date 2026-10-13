# Agent system classification profile

Reviewed for the user-approved dashboard refinement pass on 2026-10-13.
Agent v3 binds Observer API 4, snapshot/watch 6 and Service 4 through SDK 1.
Read 1, Delivery 1, carriers, Agent v1/v2 and Tmux v1 stay unchanged.

The only new session enum is `kind=system`: an internal helper classification
reported by the supported native client. It is independent of persistence,
runtime and phase. Ephemeral status alone is not a system predicate. Native
confirmed child markers keep their existing precedence and malformed or
unsupported classification stays unknown with a bounded reason.

Raw producer and Mesh views preserve system identities. Presentation clients
may hide system rows by default while explicitly retaining diagnostic access.
Missing classification never proves a system thread. Classification does not
supply runtime authority or change source leases, activity or timing semantics.

The v3 schema copies the exact producer Session shape. Old profiles reject v3;
v3 rejects old negotiation. No conversion or automatic downgrade exists.
The native input hashes and independent package/IPC/SSH proofs bind acceptance.
The lock revision adds v3 inputs; every prior schema/native-input hash must stay
unchanged. Tmux owner selection and its factory remain independent.
