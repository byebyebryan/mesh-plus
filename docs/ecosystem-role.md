# Current ecosystem role and ownership

Native provider managers and their shared runtimes own conversations and agent
work. The surrounding projects supply host access, read-only observation and
independent desktop conveniences.

| Project | Owns | Current consumers or connections |
| --- | --- | --- |
| Mesh Plus | Logical host authority, routes/revisions/health and reusable cached state delivery | SSH Plus authority facade; Observer networking and read clients |
| SSH Plus | SSH picker, connection history and canonical Host Mesh v1 process contract | Host discovery/routing for Agent Plus, Tmux clients and Mesh |
| Agent Observer | Codex discovery, native identity/runtime/activity semantics, local collection/service and pure read facades | Hardware dashboards, read CLI and additional read-only utilities |
| Agent Plus | Environment inventory and owned native-TUI window launch/focus | Host Mesh and its own headless host helper; native Codex/Claude managers |
| Tmux Observer | Generic tmux facts, prepared fleet/desktop composition and a separate action client | Tmux Plus and explicit tmux clients |
| Tmux Plus | Tmux browsing, presentation, explicit intent and compatibility CLI | Independently pinned Tmux Observer and Host Mesh |

Agent Plus has no Agent Observer, Mesh state-reader or Tmux runtime dependency.
Its Host Mesh use supplies routes rather than conversation state. Claude native
entry is supported there independently of Observer's retired Claude monitoring.
Codex is Observer's only implemented native adapter; frozen provider vocabulary
does not advertise additional native support.

## Authority and delivery are separate interfaces

Mesh owns the host/route implementation. SSH Plus retains its canonical
`contracts/host-mesh-v1` bundle and supported
`rofi-ssh-plus mesh list/report-route --json` facade. The native
`mesh-plus mesh ...` facade is separately available. Both operate on the
selected single authority; there is no second registry. Existing SSH-named
configuration and route-health paths remain valid. SSH history remains private
to the picker. See [the ownership/compatibility contract](ssh-plus-integration.md).

Default process consumers may invoke SSH Plus; callers can explicitly select the
native Mesh authority or reviewed library authority as supported by their owning
interface. Independent validation belongs at each public boundary. A copied
contract bundle or an independent decoder is not a second authority writer.

State delivery consumes already published host-local facts through supported
pure profiles. Mesh never queries a provider, classifies agent work, attaches a
terminal, or supplies lifecycle authority. Identity, native field freshness and
coverage remain attributable to the producer. Cached delivery/heartbeats do not
renew native evidence. Readers handle gaps, expiry, failure and new incarnations.
The [SDK](sdk-api.md) and [frozen contract](contract-freeze.md) define the exact
accepted interface; broader design studies add no runtime capability.

## Selection and compatibility

Source head, package release and selected host roles are different records.
Read CLI, collector, full feed, working-set feed, dashboard and SSH
authority can retain different exact artifacts. The deployment owner records
effective host/home selections and rollback inputs; producer repositories retain
the acceptance and compatibility evidence for their own interfaces.

The [execution census](evidence/2026-10-22-ecosystem-realignment/host-starship.json)
is a dated metadata observation, not an authoritative deployment configuration
or physical device test. Use the execution handoff for integration proposals and
the owner manifests for subsequent operational changes. A running service or
an installed artifact alone does not establish consumer or native acceptance.

The Tmux pair remains supported secondary tooling. A new feature needs a
concrete tmux workflow or consumer; reduced agent-runtime relevance does not
authorize service retirement. Observer writes and standalone active-only hosting are fully retired. Working-set
reads retain active membership and recent context; full diagnostic reads remain
supported. The [public delivery closeout](evidence/2026-10-23-public-delivery/README.md)
records publication and scoped managed retirement. Earlier writer/active receipts
retain their original historical and recovery bounds.

[Fleet Plus](https://dev.byebyebryan.com/fleet-plus/) owns the current shared
presentation and cross-project explanations. This guide retains Mesh's interface
ownership summary; source contracts and dated evidence stay in their owner repos.

## Development direction

Improve read-only utility usability through public Observer reads and optional
Mesh transport. Client selection/presentation belongs to each utility; reusable
native semantics belong to Observer and delivery belongs to Mesh. Preserve the
native entry client's narrower responsibility. Keep source/main integration,
artifact qualification, managed selection and physical behavior separately
reviewable. Existing complete-view routes stay selected; delta/view-feed and
optional transport experiments require their own adoption decisions.
