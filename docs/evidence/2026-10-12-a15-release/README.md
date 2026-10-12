# a15 published artifact acceptance

2026-10-12. Mesh Plus **0.1.0a15** is published as an immutable GitHub prerelease:
[release and assets](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a15).
This publication selects no live environment, shared launcher or Observer artifact.

The accepted private wheel is published **unchanged**:

- `mesh_plus-0.1.0a15-py3-none-any.whl`
- SHA256 `42b25045f8f89afda61e56525f443a189dcc6769637aee5bcab959f096527f0f`
- release/tag commit `de2ee3642501664e8b6ede4dc6d3cf5ff6ba4713`
- runtime checkpoint `c46262c0f0185244e96c79ea2036e4f57b2e4e1e`

[Provenance](provenance.json) and [SHA256SUMS](SHA256SUMS) are published alongside
the wheel. The [download acceptance](download-acceptance.json) checks independent
draft, first public and final immutable public downloads against those exact bytes,
current source/runtime hashes and the accepted candidate. The remote tag resolves
to the reviewed release commit. A fresh environment installed from the public
wheel, with Python 3.13.7/jsonschema 4.26.0/websockets 17.2 and **no Observers**,
passes [11 publisher/carrier cases](published-installed.json) without skips.
The original [candidate acceptance](../2026-10-11-publisher-factory/README.md)
retains native regressions, cross-Python gates and their exact reviewed inputs.
The source canonical standalone gate was refreshed before publication and passed.

## Immutability audit

The first public download was correct, but the audit found repository release
immutability disabled and the release API reported `immutable=false`. The repository
setting was enabled through the documented API. The **same release**, tag and
asset IDs were moved to draft and republished; no asset was replaced, deleted or
rebuilt. [Final release state](immutable-release.json) reports `immutable=true`;
[repository setting](repository-immutability.json) reports enabled. A third independent
public download retains every accepted hash, and GitHub's signed release
attestation is checked with `gh release verify v0.1.0a15 --format json`, recorded
in [attestation evidence](release-attestation.json).

GitHub [documents](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)
that enabling immutability applies to future publications. Existing older releases
are not retroactively attributed this protection. `published.json` preserves the
initial public metadata; the final immutable state/attestation take precedence
for publication status. No other repository setting was changed.

## Capability and operational limits

A15 publishes the generic cached publisher/factory seam and optional WSS already
accepted in the separate candidate passes. SDK interface remains 1, Read/Delivery
and native profile schemas are unchanged, and lock revision 2 remains reviewed.
There is no PyPI publication. Use the explicit downloaded wheel, verify SHA256,
and add its `[wss]` extra only when selecting that backend.

The stock launcher continues using reference adapters. Observer-owned publisher
activation requires a reviewed static lazy factory map and separately accepted
owner artifact. Native extracted sources, normal/capacity resource budgets,
shared launcher adoption, WSS real-fleet selection and physical suspend remain
separate gates. The [WSS fleet plan](../../wss-fleet-trial-plan.md) records concrete
read-only preparation; it is not deployment acceptance.
