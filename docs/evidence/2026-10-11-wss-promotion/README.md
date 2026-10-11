# Optional WSS promotion acceptance

2026-10-11. **Implementation and private-wheel acceptance complete; release and
real-fleet selection remain separate.** The reviewed optional backend supports
cached polling and pushed replacement state. Source/runtime checkpoint:
`bfe5d91f4937dd545153b28fc5e7a7647683f1d5`.

## Reviewed boundary

[The plan](../../wss-promotion-plan.md) and
[WSS addendum](../../../contracts/wss-v1/contract.md) define the additive change.
Lock revision 2 adds only WSS carriage/configuration support. All prior normative
digests except the explicitly updated freeze remain unchanged. Native inputs,
profile IDs, Read/Delivery envelopes, SDK v1 exports/signatures, Host Mesh authority
and existing defaults remain unchanged. Native events/replay, digest-only proofs,
brokers/pools, WSS-only host authority, browser clients, refresh/actions and
automatic fallback remain excluded.

The new module owns native mTLS, fixed cached publisher authorization, immutable
registry/trust/credential snapshots and mixed IPC/SSH/WSS composition. It reports
WSS provenance on failed, connecting and successful outcomes. Legacy SSH token
derivation uses the separately captured Host Mesh revision; WSS tokens bind the
new public selection revision. Neither private keys nor SSH route health enter
that revision. No SSH Plus history/configuration/health writes are introduced.

## Acceptance matrix

| Gate | Exact accepted scope | Result |
| --- | --- | --- |
| Installed WSS Python 3.11.10 | websockets 17.2, Tmux 0.6.0a5, Agent 0.5.0a16 | 42 tests, no skips |
| Installed WSS Python 3.13.7 | same reviewed packages | 42 tests, no skips |
| Installed WSS Python 3.14.8 | same reviewed packages | 42 tests, no skips |
| Installed WSS lower dependency bound | Python 3.13.7, websockets 17.1, no Observers | 33 standalone tests, no skips |
| Installed core without extra/Observers | Python 3.13.7, jsonschema 4.26.0 | 104 tests, no skips |
| Installed native/SSH core | Python 3.13.7, reviewed Observer wheels | 141 tests, no skips |
| External installed owner kit | no extra/Observers, owned IPC and real SSH | 35 cases; negative profiles rejected |
| a13 pure-profile comparison | 12 frozen fixtures, 36 selections | identical result digests |
| Canonical source gate | lock, 116 Read checks, 169 Delivery checks, core, Ruff; native/WSS also run | passed |
| CI at runtime checkpoint | Python 3.11/3.13, separate core and WSS jobs | all four jobs passed |

The individual JSON reports bind actual installed runtime and checkout test
inputs. Installed tests reject editable/source runtime imports. Both pure native
profiles retain full nonce proofs, original receipts, expiry, gap/resync and
conservative effective rows. Coverage includes real mixed IPC/WSS/disposable SSH
poll/watch/failure isolation, authorization/credential changes, large UTF-8 and
fragment bounds, slow consumers, real 4,080-handle rotation, restart/listener loss,
configuration job ownership and CLI serve/read/watch/probe/SIGINT/SIGTERM cleanup.

Review added owned DNS resolution: hostname setup cannot leave an asyncio
executor thread. The fixed standard-library helper is reaped on cancellation and
timeout; numeric addresses bypass it and TLS still verifies the configured host.
Late send validation and cumulative setup/snapshot admission deadlines are tested.
Configuration is explicitly restricted to local filesystems; one outstanding
daemon read job is retained and reported if unretired. Arbitrarily blocked kernel
filesystem calls are not advertised as interruptible.

CI initially rejected an OpenSSL signing flag unsupported by its runner. The
fixture now uses portable `openssl ca` with a private disposable database. A
first correction missed the required output directory; the completed correction
passes smoke, installed gates and CI. No authentication negative case was skipped
or weakened. Earlier failed attempts are not accepted runtime evidence.

## Artifact and preservation

[Package audit](package.json) records the final private a14 wheel:

`mesh_plus-0.1.0a14-py3-none-any.whl`

SHA256 `aa26f9b840d940d1051fc43c58d8f40bff05938948f3a647a31096d813f1dc59`.

All 20 original packaged schemas and 47 of 49 original runtime/resource members
remain identical to a13. The two intentional existing changes are the version
constant and carrier-aware result byte accounting. Nine new WSS runtime/schema
members are packaged; no study/test/docs runners enter the wheel. The ordinary
dependency set remains jsonschema; websockets is an optional extra. Earlier
private package reports are retained as pre-DNS/pre-format checkpoints and are
not the accepted wheel. No released a13 asset was overwritten.

The [ownership audit](hygiene.json) found no remaining matching fixture processes,
temporary credential/native directories or disposable SSH directories after the
accepted runs. This is a scoped audit, not a claim about all machine state. No
sibling checkout, chezmoi file, live service or deployed pin was edited or selected.
Sibling HEAD/native collection acceptance was deliberately excluded.

CI: [runtime checkpoint](https://github.com/byebyebryan/mesh-plus/actions/runs/38163310420).
The evidence/docs commit may have its own later CI run; source, private wheel,
CI, released artifact and installed/live selection remain distinct evidence.

## Remaining owner operations

Publish a new immutable release only from the accepted source/artifact tuple.
Then explicitly select a listener on an owned real fleet pair and accept
LAN/tailnet/firewall reachability, loss/recovery, service and certificate rotation,
physical suspend and rollback. No WAN/fleet budget or promoted-carrier performance
claim is established here; the earlier study's cold setup numbers are not
attributed to the new owned-DNS implementation.

Observer owners can continue independently on SDK v1. Adopting WSS requires only
an explicitly selected networking factory/configuration and its operational
acceptance, not a provider or desktop policy migration. See
[configuration and SDK usage](../../wss.md).
