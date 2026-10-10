# Changelog

## 0.1.0a6 (unreleased)

- Add explicit `LibraryMeshAuthority` reads for services selecting the same
  imported authority package. Reuse the canonical config parser, route-health
  model/store and bounded catalog encoder without repeatedly starting a CLI.
- Bound read jobs to one per adapter, reject special/oversized source files,
  use deadline-bound nonblocking health locks and report incomplete shutdown.
  Route reports retain the existing process writer; default process authority,
  extracted authority bytes and frozen wire schemas remain unchanged.
- Measure the catalog watch interval between check starts so read cost does not
  extend the configured scope-recheck cadence.
- Reuse static profile-schema success for identical full JSON bytes across
  independent in-process consumers. Retain only one SHA-256 digest per domain;
  native validation, proof/receipt checks and current-time expiry always run.
- Check metadata bounds through a read-only view excluding native bodies,
  avoiding a deep copy of complete session inventories before discarding them.
- Reduce JSON safety-walk overhead for ordinary decoded values and serialize
  validated frames without walking the same tree twice. Unicode, nesting and
  finite-number checks retain their existing bounds.

## 0.1.0a5 (unreleased)

- Dispatch Host Mesh authority commands before importing delivery or native
  dependencies. Catalog rechecks retain the same authority and wire behavior
  while avoiding the state SDK's repeated import cost.
- Keep the frozen contract, packaged schemas and independently selected Agent
  reader unchanged. Tmux operational resource acceptance remains a separate gate.

## 0.1.0a4 (unreleased)

- Bind Agent frame limits through its supported pure service descriptor.
- Conservatively omit stale unsaved runtime rows from current selection while
  preserving the original owner envelope and independently valid saved history.
- Add `configured_read.configured_reader` for shared client endpoint binding,
  with explicit route-reporting policy disabled for read-only consumers.
- Keep the frozen state profile, authority and packaged schema bytes unchanged.

## 0.1.0a3 (unreleased)

- Add `doctor` and bounded, explicitly requested snapshot/push `probe` commands;
  probes close owned connections and never write route-health state.
- Add redacted client and completed application-frame counters outside the wire
  contract. Source configuration is opened without following symlinks and read
  with a size bound after validating the opened private regular file.
- Add a producer-free synthetic IPC/SSH fault and resource lab, isolated workload
  measurements, CI fault checks and an optional connection-pool design proposal.
- Preserve the frozen contract, shared authority bytes and deployed a1 selection.

## 0.1.0a2 (unreleased)

- Keep completed and failed subscription iterators exhausted after their terminal
  item, while retaining explicit subscription cleanup.
- Wake pending request callers on a valid request `ended` frame without closing
  sibling work.
- Add a shared standalone CI/local validation command and integration handoff.
- Keep disposable SSH key paths private independently of the validation
  environment location, preserving StrictModes in isolated wheel acceptance.
- Separate current readiness, historical checkpoints, candidate package evidence
  and deployed authority selection. The frozen contract is unchanged.

## 0.1.0a1 (2026-10-09)

- Freeze cached polling and pushed state over IPC and SSH stdio, including
  nonce proof, bounded delivery lifecycle and pure consumer validity checks.
- Publish the experimental wheel; SSH Plus selects its shared Host Mesh authority
  on Snap and Starship through an independently pinned chezmoi installation.
- Keep Observer transport migrations, ordered events/replay, WSS and the shared
  fleet broker behind independent acceptance gates.
