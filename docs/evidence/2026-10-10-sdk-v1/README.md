# SDK v1 package acceptance

2026-10-10 local checkpoint. Mesh source/package a11 implements the additive
explicit profile boundary and a snapshot cancellation fix. It preserves all
frozen wire inputs, 20 packaged schema bytes and reviewed authority bytes.
The [immutable a11 prerelease](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a11)
contains the wheel and checksum; downloaded bytes match the manifest.
This evidence does not select or deploy new runtime artifacts.

- [Package manifest](package.json): wheel source
  `9d570c59041832d177519fd634d26c56ed572e81`, SHA-256
  `9d3c2446b2391ab2271236804b4dfc03dfa5d29f2766d72b3d12086848b36359`,
  39 runtime/schema members equal source, exact pinned Observer wheel hashes.
- [Validation](validation.json): isolated installed wheel passes 85 standalone
  tests on Python 3.11 without Observer packages, and 119 native/SSH tests on
  Python 3.14 with Tmux Observer 0.6.0a5 / Agent Observer 0.5.0a16. No skips.
  Both canonical gates also pass lock, 116 Read checks, 169 Delivery checks and
  lint. CI passes canonical standalone and synthetic fault checks on 3.11/3.13.
- [Differential oracle](differential.json): exact native reconstructions and
  36 effective selections across 12 frozen cases equal separately installed a10.
- [SSH authority](authority.json): 82 model/subprocess regressions pass with the
  canonical backend and the explicitly reviewed bounded-read baseline. The old
  literal-extraction gate still rejects; its historical negative is preserved
  in the [preceding review](../2026-10-10-sdk-boundary-review/README.md).

Ten independent SDK tests block native/reference-integration imports and exercise
profile injection, IPC poll/watch, the SSH route connector binding, proof
admission, reconstruction, expiry, guards, catalog replacement, setup deadlines
and repeated snapshot cancellation. The direct route test uses an owned IPC
channel as the connector; the separate native suite owns actual disposable SSH.
The locked public signature fixture is SDK acceptance, not a changed wire lock.

Two initial CI failures exposed snapshot cancellation returning before a sibling
finished cleanup. A deterministic delayed-close test fails on the earlier
unpublished a11 wheel and passes after the fix. Its source/wheel/log hashes and
failed CI references remain in validation.json; that wheel is not the released
artifact. No released a10 or earlier artifact was overwritten.

Reproduce with a11 installed in dedicated environments, pinning jsonschema 4.26.0
and ruff 0.16.10:

```sh
rtk proxy /path/to/standalone-python scripts/check.py
rtk proxy /path/to/native-python scripts/check.py --native
rtk proxy /path/to/native-python scripts/check-sdk-compat.py \
  --baseline-python /path/to/pinned-a10-python
rtk proxy /path/to/native-python scripts/check-authority-compat.py \
  --ssh-plus /path/to/rofi-ssh-plus --backend mesh-plus --baseline bounded-read-v1
```

Mesh's normal gate never requires sibling checkout parity. The authority gate
intentionally reads its direct SSH client, requires clean tracked source and
records its exact commit. Owner networking source tests and pinned native facade
admission are supplementary checks; they do not establish adapter extraction,
provider collection, Plus migration or live deployment. No production-budget
soaks, GUI or physical suspend acceptance were repeated for this SDK checkpoint.
Chezmoi and both Observer checkouts remain unmodified.
