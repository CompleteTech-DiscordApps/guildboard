# Guildboard board guide

<a id="board-runtime-evidence"></a>
This provisional guide for [GB-T13.02.02.T1 (#434)][guide] describes planned
workflows for guild administrators, moderators and board participants. The
[repository status][status] records a foundation and application scaffolds.
There is currently no runnable application, Discord installation link or
production deployment. The headings below describe tasks without prescribing
UI labels, bot syntax, installation steps, or shortcuts.

The [accepted T0 handoff][t0] governs server authority, tenant isolation,
durable acceptance and recovery. The [board workstreams][authz] define planned
capabilities. The [canvas fixture research][canvas] and [persistence
research][persistence-research] provide bounded feasibility evidence from
isolated runs. Client support, accessibility and complete workflows remain
unresolved. Dated Discord Activity and GoDaddy Linux VPS evidence belongs to
the respective platform and release owners. See the [documentation
contract][docs-contract] for claim ownership and evidence requirements.

## Claim status and handoff

Accountable expertise: moderation and policy owners; T2/T6 and editor/user
experience T3/T5/T7 consumers review their scope. Audiences: administrators,
moderators and end users. The [claim register](evidence/GB-T13-02-02-T1-guide-claims.json)
pins the existing anchors and the runtime gap to exact guide bytes.

| Claim anchor | Status | Next validating owner and scope |
| --- | --- | --- |
| [board-runtime-evidence](#board-runtime-evidence) | unresolved | GB-T13.02.02.V1 [#435][verification]: complete candidate workflows and claimed clients with feature owners. |
| [map-roles](#map-roles) | planned | T1/T2: role precedence, authority and mapping outcomes. |
| [manage-boards](#manage-boards) | planned | T2/T5: scoped lifecycle, visibility and retention outcomes. |
| [drawing-requests](#drawing-requests) | planned | T2: grants, requests, expiry and revocation. |
| [lock-and-modes](#lock-and-modes) | planned | T2/T6: lockdown fences, transitions and presentation. |
| [join-and-draw](#join-and-draw) | planned | T3/T7: authorized tools, conflicts and participant feedback. |
| [save-and-history](#save-and-history) | planned | T5/T7: durable acceptance, history and lineage recovery. |
| [accessible-options](#accessible-options) | unresolved | GB-T13.02.02.V1 #435 with T3/T7: keyboard, screen reader, touch and client scope. |
| [permission-recovery](#permission-recovery) | planned | T1/T2/T7: permitted recovery without widening access. |
| [manual-verification](#manual-verification) | unresolved | GB-T13.02.02.V1 #435: execute and retain each scenario before D1/G3 handoff. |

Every planned section still requires implementation and verification; its
embedded design uncertainties remain open. The unresolved runtime and manual
verification claims cover these gaps under #435. Existing canvas fixtures and
persistence research remain isolated feasibility evidence, with no integrated
board workflow, accessible client or real platform pass inferred from them.

<a id="map-roles"></a>
## Guild administrators

**Planned · T2 role mapping.** A verified guild administrator configures which
Discord roles map to Guildboard viewer, writer, moderator and administrator
capabilities. Verify the intended guild before changing mappings and check
the result with separate accounts for the affected roles. View and write
access are scoped to the board and depend on current server policy. Exact
role precedence, Discord privileges, onboarding procedure and the effect of
overlapping roles remain unresolved under [T1][identity] and [T2][authz].
Ordinary writers and moderators cannot elevate themselves to administrator.
Treat a denied or unavailable mapping action as unresolved until current
administrator authority and the recorded mapping are verified.

<a id="manage-boards"></a>
### Manage boards

**Planned · T5 board lifecycle.** In the verified guild, use the authorized
board management workflow to create, list or select a board, or to rename,
duplicate, or set a channel default where policy permits it. Confirm the
destination guild, board and channel before changing anything. Archiving is
planned as reversible. Deletion requires separate authorization and explicit
confirmation. Check which board you are acting on and confirm the recorded
outcome before attempting another change after an interruption. The exact
role-to-action mapping, visibility rules, lifecycle controls and retention
policy remain unresolved. [T2 authorization][authz] · [T5 board lifecycle][data]

<a id="drawing-requests"></a>
## Moderators

**Planned · T2 requests and grants.** On the intended board, review the
pending Request to Draw, verify the requester and current board policy,
and approve or deny it if authorized. Grant the Pen is targeted temporary
writing permission on that board. Check the confirmed grant and its expiry.
Expiry uses server time. An authorized moderator can revoke a grant or
restrict a user within policy. Self-approval, self-escalation and cross-board
requests are denied. If a decision times out, refresh the request and
effective permission before taking a new action. A pending request or
unconfirmed grant gives the participant no additional authority. [T2 authorization][authz]

<a id="lock-and-modes"></a>
### Lockdown, board modes and presentation

**Planned · T2/T6 moderation and modes.** Use the scoped lock or emergency
lockdown action when ordinary edits must stop. Confirm the authoritative
state. Lockdown overrides ordinary writes, including temporary grants.
The server fences existing connections and in-flight writes against the
committed policy change. An edit committed before the fence remains accepted.
Unlocking requires explicit authority.

The planned modes are open, moderated, locked, request-to-draw and
presentation. Open collaboration admits authorized writers. Moderated
collaboration limits editing to the authorized moderation workflow. In
request-to-draw, participants can ask for permission where policy allows.
Presentation has separate presenter and follow controls. Following controls
the viewport and carries no edit privilege. On a conflicting or interrupted
mode change, refresh the current mode and permissions before submitting
another change. Exact transitions and treatment of pending requests and
grants across transitions remain unresolved. [T2 authorization][authz] · [T6 modes][modes] · [T0 authority][system-auth]

<a id="join-and-draw"></a>
## Board participants

**Planned · T3/T7 board access and drawing.** Open the intended board in
the verified guild and check your access and the board mode. A viewer can
navigate a readable board. If the board accepts drawing requests and
you need to edit, request permission and wait for a confirmed decision.
With current write authority, the planned tools include freehand drawing,
eraser, shapes, connectors and text. Planned undo and redo apply to
accepted edits and require current permission. A conflict can prevent undo
when another edit changed the same object. Available tools and shortcuts
remain unresolved. [T3 canvas][canvas] · [T7 user experience][ux]

<a id="save-and-history"></a>
### Save status and history

**Planned · T5/T7 save, history and recovery.** An edit can appear locally
while pending. Treat it as saved only when the service confirms durable
acceptance. A rejected edit requires reviewing the reason and current
board state. A disconnect or missing acknowledgment can leave the result
unknown. Reconnect in the same guild and board and wait for reconciliation.
Use a verified retry flow for the original unresolved action when available.
Submitting a fresh copy while the outcome is unknown can duplicate the edit.
A new attempt after a confirmed rejection requires current write permission.

History and checkpoints are planned for authorized readers. Restoring a
checkpoint is a separately authorized action that establishes a new
lineage. After restore, reconcile to the active board before editing. A
receipt for an earlier lineage can confirm an earlier commit. It cannot
confirm the current board's state. The planned recovery flow keeps unresolved
old edits out of the restored board and allows deliberate discard or a new
authorized edit against the current state. [T5 history and recovery][data] · [T0 save and restore semantics][system-save] · [T7 feedback][ux]

<a id="accessible-options"></a>
### Accessible alternatives

**Unresolved · T7/T3 interaction and client support.** Planned alternatives
include keyboard board navigation, keyboard access to request and moderation
actions, visible focus, and non-canvas controls and announcements for mode,
request, save and reconnect status. Keyboard users need to be able to reach
and activate controls and recover focus after closing dialogs. Screen reader
users need meaningful state announcements without continuous cursor chatter.
Touch, narrow viewports and reduced motion also require checks. When canvas
interaction is unavailable, ask the session organizer for a text summary or
to record input on your behalf, using a channel authorized for the content.
That human alternative leaves board access and editing permissions with the
people already authorized. Supported shortcuts, assistive technologies and
which drawing tasks have usable alternatives remain open. [T7 accessibility][ux] · [T3 keyboard feasibility][canvas]

<a id="permission-recovery"></a>
## Recovering access

**Planned · T1/T2/T7 permission-aware recovery.**

| Situation | Next step |
| --- | --- |
| Board unavailable or access denied | Verify the Discord account, guild and intended board with the organizer or an authorized guild administrator. Ask them to check current access. An unavailable result may cover an unknown or foreign board without disclosing which. |
| Can view but cannot draw | Check mode, restrictions and the current grant. Use the drawing request workflow when allowed. If the grant expired or was revoked, ask an authorized moderator to review it through the normal flow. |
| Role or mode changed while connected | Refresh or rejoin through the supported flow and wait for the confirmed policy. New writes require current authority even on an existing connection. |
| Mapping, moderation or edit outcome is unknown | Re-establish the verified session and inspect authorized state before retrying. A missing result or read denial cannot settle an unknown commit. Ask the responsible admin or moderator for help within their scope. |
| Discord launch or service dependency unavailable | Confirm prerequisites with the organizer or support owner. Resume when the service and verified session are available. Record the client and redacted outcome if it persists. |

For a suspected permission or privacy defect, use the [private security
reporting route][security]. Keep credentials, account and tenant identifiers,
private links and board content out of public reports.

<a id="manual-verification"></a>
## Verification handoff to GB-T13.02.02.V1

[#435][verification] owns execution and evidence. Use a candidate with the
applicable product features and approved synthetic guild and board data.
Prepare separate administrator, moderator, authorized writer and viewer
accounts, a second board and a separate tenant. Seed a checkpoint, an active
temporary grant, and an independent edit for conflict testing. Select the
actual supported Discord clients, viewport and input modes from the candidate
scope. The actions above provide scenario intent. Use the candidate's real
controls and record the exact steps.

| Claim | Observe on the candidate | Denial, interruption or abuse check |
| --- | --- | --- |
| [Role mapping](#map-roles) and [board management](#manage-boards) | Administrator configures a valid mapping and verifies separate accounts. An authorized actor creates, selects and manages the intended board. Confirm archive and permitted recovery. | Invalid mapping or unavailable membership evidence fails closed. Wrong guild, unauthorized mapping and cross-board or cross-tenant access reveal no protected data and cause no accepted change. Interrupt a lifecycle action and inspect authoritative state before retrying. |
| [Requests and grants](#drawing-requests) | Confirm request, approval or denial, scoped Grant the Pen, expiry and revocation. Observe participant feedback on each outcome. | Try self-approval, the wrong board, expired authority and a lost result. Check that an already-connected writer cannot commit after revocation and a retry does not grant twice. |
| [Lockdown and modes](#lock-and-modes) | Exercise supported roles across modes, authorized lock/unlock, presenter designation, follow/unfollow and reconnect. | Race an ordinary write with lockdown while a grant is active. Check that policy ordering preserves accepted prior edits and fences later writes. Stale mode changes fail and following does not grant editing. |
| [Drawing](#join-and-draw) and [save/history](#save-and-history) | Verify bounded drawing, pending-to-saved feedback, scoped history, revision-aware undo and authorized checkpoint restore. Compare accepted state and receipts. | Deny viewer writes, unauthorized history reads and conflicting undo without a committed side effect. Disconnect before confirmation and after commit with a lost acknowledgment. Check no false save or duplicate edit and no old edit replay after restore. |
| [Accessible alternatives](#accessible-options) and [recovery](#permission-recovery) | Use keyboard alone and an actual screen reader for navigation, requests, moderation and permission/save feedback. Check focus, narrow and touch layouts, and reduced motion in the declared client scope. | Exercise revoked access and reconnect while using the alternative flow. Record inaccessible tasks and test the available participation alternative without expanding access or exposing content. |

Record the guide and candidate revisions, product and platform versions,
environment, executed steps, exact commands where applicable, expected and
actual results, raw evidence in an appropriate restricted location and
defects. Retain redacted evidence references and distinguish documentary
review, local fixtures, real Discord client/iframe/proxy results and GoDaddy
VPS evidence. This guide changes no deployment or runtime settings. Record
unavailable prerequisites and unexecuted checks with the validating owner
and affected scope. The scenarios above have no product execution result
in this draft.

[guide]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/434
[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/435
[status]: ../README.md#foundation-status
[t0]: workstreams/T0.md#t0-integration-and-handoff
[identity]: workstreams/T1.md
[authz]: workstreams/T2.md
[canvas]: workstreams/T3.md
[data]: workstreams/T5.md
[modes]: workstreams/T6.md
[ux]: workstreams/T7.md
[persistence-research]: research/t5-durability-research.md
[system-auth]: specifications/GB-T0-S1-system-contract.md#3-identity-and-authorization-invariant
[system-save]: specifications/GB-T0-S1-system-contract.md#5-ordering-conflict-idempotency-and-save-semantics
[docs-contract]: specifications/GB-T13-S1-documentation-release-contract.md#guide-ownership-and-claims
[security]: ../SECURITY.md
