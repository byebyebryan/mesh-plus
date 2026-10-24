# Isolated WSS study

This directory is an explicit research runner, outside `src`, package discovery,
normal CLI and SDK exports. It does not promote WSS to the frozen runtime.
Run with the pinned study environment and reviewed Observer wheels:

```sh
rtk proxy /tmp/mesh-wss-study/env/bin/python -m unittest discover -s studies/wss -p 'test_*.py' -v
```

The carrier uses websockets 17.1's public Sans-I/O ClientProtocol/ServerProtocol,
over owned Python TLS streams. No high-level redirect or proxy discovery is
involved. A socket admission slot is acquired before accepting a TLS connection;
the loopback fixture has four total active or pending slots. Native mTLS, an
explicit certificate fingerprint policy, one fixed path and one configured
host/source/profile precede Bridge dispatch. Compression is not negotiated.

Proposed configuration namespace: `mesh-plus.wss-study.v1`. Only `state` and
`snapshot`, `proof`, `subscribe` are admitted. Configured sources retain
`[a-z][a-z0-9_]{0,127}`. Host IDs reference a separately validated Host Mesh v1
catalog; this study neither creates aliases nor writes SSH health/history.

The selection revision hashes the Host Mesh revision, ordered endpoint registry,
and captured public trust/client certificate configuration. Private key bytes
are excluded. The token hashes canonical JSON containing `bindingProtocol`,
`selectionRevision`, `hostId`, `endpointIndex`. Server authorization changes are
checked by the listener, independently of this client selection revision.

Prototype bounds: 3 seconds per TLS/header phase, five seconds per authorization
read, 2 seconds message assembly/write, 1 second graceful close followed by
bounded TLS retirement (up to three seconds overall), 256 fragments, two complete
queued messages, 64 KiB control/HTTP input,
and the frozen negotiated message ceiling. Deadlines use BOOTTIME. TLS certificate
validity uses wall time. Policy checks start no more than five seconds apart,
with a five second read budget; tests may choose a shorter interval. Any failed
policy check closes the connection. These are fixture bounds, not a global RSS
bound. WebSocket Ping/Pong and Mesh heartbeats never renew source receipts.

The experimental Reader labels outcomes through an immutable endpoint mapping.
Existing Reader metrics label JSON lines, so the specialization must also correct
its aggregate byte scope to completed JSON messages. Client/Bridge, native codecs,
full nonce proofs and ReadGuard remain the released a13 implementations.

Reference APIs: [Sans-I/O integration](https://websockets.readthedocs.io/en/stable/howto/sansio.html),
[client](https://websockets.readthedocs.io/en/stable/reference/sansio/client.html),
[server](https://websockets.readthedocs.io/en/stable/reference/sansio/server.html),
[owned accepted sockets](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.connect_accepted_socket).

See [roadmap](https://github.com/byebyebryan/mesh-plus/blob/12723500ea2fa7f06f3c7089fce62577c2d2fcea/docs/history/experiments/wss-roadmap.md) for acceptance and promotion gates.

Matched measurement runner:

```sh
rtk proxy /tmp/mesh-wss-study/env/bin/python studies/wss/measure.py --output /tmp/mesh-wss-study/measurements
```

This owns loopback subprocesses and disposable private SSH/TLS material. A
persistent publisher/Bridge worker per Reader is used by both carriers. SSH's
forced command uses `/usr/bin/socat` as a raw stdio-to-IPC relay; its descendants
are counted. IPC is a separately labeled local reference. Publishers broadcast
cached updates and preserve original receipts. No shared-listener topology is
attributed to a raw carrier benefit. Every run checks native admission, full
proofs, observed updates/recovery and owned cleanup before recording success.
The original 20 ms `/proc` sampler runs in the worker, so measured worker CPU includes
its process-count-dependent overhead. CPU differences require that qualification.
`refine_measure.py` repeats four-reader ABBA runs with a 500 ms sampler and
separately reports its CPU; `resources.py` runs fresh synthetic transport stress.

The [outcome](outcome.md), [decision](results/decision.json) and
[promotion proposal](promotion-proposal.md) conclude this loop. WSS remains an
isolated candidate. For reproduction of the original measurement inputs, use
commit `1b73295`; final refinement input hashes are retained in its report.

W0 baseline: source `57ca1ad`, installed a13, Python 3.13.7, websockets 17.1,
Tmux 0.6.0a5 and Agent 0.5.0a16. A fresh `/tmp/mesh-wss-study/env` was created
from immutable wheels: the existing design environment contained older Observer
and Mesh distributions and is not used for this study. Source canonical native
gate passed 141 tests without skips, plus 18 lock/20 package-schema, 116 design
and 169 delivery checks. Sibling source comparison is excluded.
