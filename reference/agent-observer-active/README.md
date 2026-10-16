# Projected Agent native schema reference

Copied byte-for-byte from Agent Observer source
`4ffd376441fcb556cbe291d55d983e0814c20551`, branch `active-feed-20261016`,
in the independent `/home/bryan/code/agent-observer-active-feed` worktree.
Observer committed only these new schemas at that checkpoint; implementation,
wheel and operational acceptance remain separate.

- `active-frame.schema.json`: SHA-256
  `0db6cfe16880467ff4c62b180ca2ae94db9e580543f43f9dcf9258c8a64d0b05`.
- `active-request.schema.json`: SHA-256
  `ada83b6a33fced2d9c1c62bf541b609ce887425a379ad49003802ee4a71f497c`.

The native selected body equals the unchanged frozen API 4 / snapshot 6 session
schema. Mesh lock revision 5 adds these references and the separate active
profile without altering any of the preceding 29 normative input digests.
Packaged native/request copies and active profile parity are checked by
`scripts/check-contract-lock.py`. Native semantic validation and acquisition are
owned by Observer; this reference does not add a Mesh provider implementation.
