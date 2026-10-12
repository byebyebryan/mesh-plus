Mesh Plus 0.1.0a15 publishes the accepted generic cached publisher/factory seam and optional native WSS transport. It retains SDK interface 1 and existing Read/Delivery/native profile schemas. Contract lock revision 2 adds the separately reviewed WSS configuration/carrier boundary.

- Public `CachedSource`, `CachedPublication` and explicit-profile `CachedPublisher` separate Observer-native acquisition from Mesh envelope/proof construction.
- Trusted, lazy Python publisher factory maps serve local IPC, the unchanged fixed SSH bridge command and optional WSS listeners. Existing reference defaults remain; selected factory failures do not fall back.
- Optional `mesh-plus[wss]` adds native mutual-TLS poll/push, immutable mixed-backend configuration, and the separate `mesh-plus-wss` diagnostic/listener/read/watch CLI. WSS adoption is explicit.

Accepted bytes: `mesh_plus-0.1.0a15-py3-none-any.whl`, SHA256 `42b25045f8f89afda61e56525f443a189dcc6769637aee5bcab959f096527f0f`. The previously accepted private wheel is published unchanged. `provenance.json` binds release commit, runtime checkpoint and exclusions; `SHA256SUMS` covers wheel and provenance.

Validation: 113 installed standalone tests, 151 native/SSH regressions and 43 native WSS tests; installed publisher checks on Python 3.11/3.13/3.14, both domain profiles and fixed SSH/WSS carriers; a15 explicit-reader/a10 reference-bridge compatibility; four hosted CI jobs passed. Reviewed native regression inputs are Tmux a5/Agent a16, not current owner HEADs or extracted sources.

This is an experimental prerelease. No live pins, Observer packages, shared launcher or chezmoi deployment are selected by publication. Owner-native publisher/resource/managed acceptance and WSS real-fleet, suspend and matched performance acceptance remain separate. No performance improvement for the promoted bytes is claimed.

[Publisher API](https://github.com/byebyebryan/mesh-plus/blob/v0.1.0a15/docs/publisher-api.md) · [Installed acceptance](https://github.com/byebyebryan/mesh-plus/blob/v0.1.0a15/docs/evidence/2026-10-11-publisher-factory/README.md) · [WSS guide](https://github.com/byebyebryan/mesh-plus/blob/v0.1.0a15/docs/wss.md)

Assets are distributed through this GitHub prerelease; no PyPI publication is implied. Install the downloaded wheel into an isolated Python 3.11+ environment. Add `[wss]` to that wheel requirement only when selecting the optional backend.
