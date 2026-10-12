# Installed publisher ownership seam acceptance

2026-10-11 (local date). **Mesh producer source/private-wheel acceptance complete.**
Runtime checkpoint `c46262c0f0185244e96c79ea2036e4f57b2e4e1e`; the following
acceptance commit adds documentation/evidence only. No Observer implementation,
managed launcher, deployed pin or live service was changed by this pass.

## Accepted surface and preservation

The [reviewed plan](../../publisher-factory-plan.md) and
[public API/owner handoff](../../publisher-api.md) define a generic cached native
source, public CachedPublication/CachedPublisher and keyword-only trusted Python
factory injection. One static factory serves IPC, unchanged fixed SSH stdio and
optional WSS. Config/wire cannot select modules or executables. Selected factory
failure never falls back; omitted domains retain the reference branch.

SDK interface remains 1. All previous public SDK signatures/exports survive;
three publisher names are added. LOCK.json and all frozen normative/native/read/
delivery/WSS schema bytes are unchanged. Host Mesh authority, SSH source command,
source descriptor version/fields, route health and picker history are unchanged.

Mesh constructs copied envelopes/digests, original-receipt remaining leases and
proofs after a new checked cached acquisition. Observer-owned native sources
retain UID/request/clock/order/receipt/passivity obligations and operation-owned
cleanup. Generic tests do not certify either owner's extracted native source.

## Installed gates

| Gate | Exact scope | Result |
| --- | --- | --- |
| Canonical source | `.venv` Python 3.13.7; `scripts/check.py --native --wss` | 21 locked inputs/20 original schemas, 116 Read, 169 Delivery, 151 runtime, 43 WSS, Ruff; passed |
| Installed core | a15, Python 3.13.7, jsonschema 4.26.0; no Observers/WSS dependency | 113 tests, no skips |
| Installed native/SSH | Tmux a5 / Agent a16, Python 3.13.7 | 151 tests, no skips |
| Installed native WSS | same Observer wheels, websockets 17.2 | 43 tests, no skips |
| Installed publisher without Observers/WSS | Python 3.13.7, real owned SSH included | 10 tests, no skips |
| Installed publisher all carriers | Python 3.13.7, websockets 17.2 | 11 tests, no skips |
| Mixed old bridge | a15 reader/factory suite plus installed a10 reference SSH bridge, both profiles | 12 tests, no skips |
| Installed publisher Python 3.11.10 | no Observers; real SSH and WSS, websockets 17.1 | 11 tests, no skips |
| Installed publisher Python 3.14.8 | no Observers/WSS dependency; real SSH | 10 tests, no skips |
| Hosted CI runtime checkpoint | Python 3.11/3.13, standalone and WSS | all four jobs passed |

The publisher suite includes independent portable profile/network conformance
for both profiles, polling/proof/push/restart, factory binding/terminal failures,
reference default/omitted-domain dispatch, mutation isolation, nonce-before-read,
original receipt monotonicity, failed-admission atomicity, cancellation and SIGTERM
cleanup. Its real SSH case executes the actual fixed remote command through a
private installed-style trusted launcher. Mixed a10 acceptance separately invokes
an installed reference bridge through owned SSH; it does not select a live bridge.

The independent native regression inputs are old reviewed packages, **not** sibling
HEADs or current live Agent/Tmux collection. Source parity against siblings,
provider-native acquisition in new owner sources, real-fleet selection, performance
budgets, graphical behavior and physical suspend are excluded. There are no
performance improvement claims for this helper; extra validation/copy costs need
owner artifact resource acceptance. Existing reference integrations stay usable.

## Artifact

[Package audit](package.json) records the private candidate:

`/tmp/mesh-publisher-promotion/wheel/mesh_plus-0.1.0a15-py3-none-any.whl`

SHA256 `42b25045f8f89afda61e56525f443a189dcc6769637aee5bcab959f096527f0f`.

59 runtime/resource members match checkout bytes. Relative to the accepted a14
wheel, 54 members are unchanged; only version, public API exports, standard CLI
and WSS CLI change, with one new publisher module. All schemas and authority
bytes are identical; dependencies remain jsonschema plus optional websockets.
No tests, studies or docs are packaged. Accepted a14 and released a13 artifacts
remain untouched; this a15 wheel has not been released or deployed.

[Exact environments and baseline wheel hashes](inputs.json) bind test inputs.
Individual reports record installed package origins and runtime/test digests.
Final runtime digests were checked against current source. Canonical log remains
at `/tmp/mesh-publisher-canonical.log`; installed logs and environments are retained
under `/tmp/mesh-publisher-promotion` for reproduction. Temporary native/SSH/TLS
fixtures are owned and removed by their tests; listener/process retirement is
checked within each gate. This is not a global process-state assertion.

CI: [runtime checkpoint](https://github.com/byebyebryan/mesh-plus/actions/runs/38209904655).
Later docs/evidence commits have separate CI receipts.

## Resume owner work

Both owners may resume **source integration and private candidate acceptance**
against the exact a15 surface/artifact above. Implement a CachedSource and pure
profile, construct CachedPublisher, and provide a lazy static factory map to a
trusted launcher for local and remote paths. No copied Mesh CLI or private Mesh
helper import is needed. See [the API](../../publisher-api.md) for signatures,
resource ownership and explicit failure/default behavior.

A public immutable release and each owner's exact artifact/resource/installed
native/managed acceptance are following gates before operational adoption. Mesh
has not installed an Observer factory or selected a launcher for either owner.
The reference branch remains supported for compatibility and rollback.

Reproduce installed generic acceptance with:

```sh
rtk proxy /absolute/a15-env/bin/python scripts/check-publisher.py --installed --ssh
rtk proxy /absolute/a15-wss-env/bin/python scripts/check-publisher.py --installed --ssh --wss \
  --baseline-python /absolute/reviewed-a10-env/bin/python
```

The optional baseline interpreter must contain exactly Mesh a10/Tmux a5/Agent a16.
It is a disposable fixture input, not a proposed operational tuple.
