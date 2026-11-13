# GB-T7.R1: Activity viewport and accessible canvas research v1

Status: **proposed research; no client support or accessibility acceptance**.
Refs [#228](https://github.com/CompleteTech-DiscordApps/guildboard/issues/228).
Observed 2026-10-26 UTC (2026-10-25 America/New_York session), baseline
`c108b552a660e12a3b3998e1e1ad944fbd7a894d`. This is a proposed test matrix and
separate local semantic editing fixture, not the Guildboard UI or accepted T7
specification. No registered Discord app, real client or assistive technology
session was available. No production deployment or purchase was performed.

## Scope and existing canvas input

Live #228 OPEN/unassigned with no prior claim or competing focused T7 PR;
GraphQL native blockedBy count was zero. Supervisor triage identifies Ready
research. Live #229 remains OPEN with native blocker #228 OPEN. No relationship,
readiness or acceptance checkbox was changed. Read T7, architecture, CONTRIBUTING
and SECURITY; application implementation still waits for accepted contracts.

Read-only input: [PR #483](https://github.com/CompleteTech-DiscordApps/guildboard/pull/483)
at `0f9ab82a17ed133f0564f7391c440765e3ee6576`, including the actual
`research-fixtures/canvas/src.jsx`, `probe.mjs` and refreshed research record.
That fixture evaluates Excalidraw **0.18.1**, source
`a2ec2889babf7d2295469c6d90ebe77fae57df84`; fixture React 18.3.1, esbuild
0.25.12 and Playwright 1.56.1 are its research dependencies, not application
adoption. Its wrapper renders Excalidraw with view mode and bounded onChange
metadata; it adds no separate semantic object outline. This does not establish
the absence or completeness of the editor's internal accessibility.

The current #483 record reports three bounded browser smoke checks on Chromium
156.0.8078.4 after dependency remediation. Its earlier zero-assertion launch
failure is historical, not its current result. Those checks cover ID preservation,
a remote baseline/local-history undo case and view-mode smoke, **not** screen
reader, comprehensive keyboard, touch/stylus or human acceptance. No #483 file
was mutated, executed, copied into this fixture or adopted. T3 retains ownership.

## Current primary sources and evaluated versions

[Source response metadata](t7-source-observations.json) records 14 historical
official-document GETs from 2026-10-26, with their original dates, final URLs
and SHA-256 hashes. Its separate `refreshes` entry records the E1 link check on
2026-11-13; those responses do not replace or relabel the historical captures. Rolling Discord and
Excalidraw pages may differ from pinned packages. WCAG 2.2 is pinned to the W3C
Recommendation dated **2024-12-12**; Understanding/APG pages are explanatory
guidance, not additional normative requirements. Response hashes do not recreate
bodies or prove application conformance.

| ID / primary source | Observed constraint / research implication |
| --- | --- |
| D1 [Discord layout](https://docs.discord.com/developers/activities/development-guides/layout) | Focused, PIP and grid modes; orientation and layout updates differ across client generations. No fixed Activity pixel dimensions are promised. |
| D2 [Discord mobile](https://docs.discord.com/developers/activities/development-guides/mobile) | Web/desktop, iOS and Android platform toggles; mobile safe-area variables, orientation/thermal/device behavior need real testing. |
| D3 [Discord production readiness](https://docs.discord.com/developers/activities/development-guides/production-readiness) | Older clients can reject newer commands; safe fallback and actual client/build records are needed. |
| E1 [Historical Excalidraw props URL](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props/) | The 2026-10-26 E1 observation belongs to this original URL and response hash. On 2026-11-13 it redirects to the SDK introduction, which does not document the cited props. |
| E1-current [Current Excalidraw props](https://plus.excalidraw.com/docs/sdk/excalidraw/api/props) | Separately fetched on 2026-11-13: documents `viewModeEnabled`, `handleKeyboardGlobally`, `autoFocus` and `onChange`. These remain candidate integration controls; UI read-only does not enforce server permissions. Rolling documentation is not proof of 0.18.1 behavior. |
| E2 [Excalidraw imperative API](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props/excalidraw-api) | Scene reads/updates and scrolling expose adapter inputs; scrolling options include animation controls. Verify against 0.18.1 and accepted operations before use. |
| W1 [WCAG 2.2 Recommendation](https://www.w3.org/TR/2024/REC-WCAG22-20241212/) | Proposed acceptance target: applicable Level A/AA criteria, including keyboard, focus, names/roles, errors and status; no conformance claim here. |
| W2 [W3C APG modal dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | Initial focus, contained Tab order, Escape and trigger focus restoration are concrete dialog checks. |
| W3 [Dragging movements](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html) | AA 2.5.7 requires a single-pointer alternative to dragging, subject to its exceptions. Keyboard alone does not meet that separate pointer requirement. |
| W4 [Target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | AA 2.5.8 uses 24×24 CSS pixels with defined exceptions. The fixture's 44×44 outer controls are a proposed design goal, not a Discord requirement. |
| W5 [Status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Programmatically identifiable updates can be presented without moving focus; avoid unnecessary interruption. |
| W6 [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | 320 CSS-pixel equivalent width is relevant; essential two-dimensional content has an exception. Surrounding forms/navigation must still work. |
| W7 [Text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Applicable text targets include 4.5:1 normal and 3:1 large text, with criterion exceptions. Test actual states/backgrounds, not a theme label. |
| W8 [Non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | Applicable component/state graphics need 3:1 against adjacent colors, subject to exceptions. |
| W9 [Animation from interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) | 2.3.3 is AAA; respecting reduced motion is an additional proposed product behavior, not misrepresented as an AA requirement. |

## Proposed supported-client and viewport matrix

Every row is a **candidate support target pending actual acceptance**, not a
statement that Guildboard currently works in that client. Record OS, Discord
build/release channel, browser/WebView, SDK/package hash, device, input/AT version,
CSS viewport, DPR, zoom/text scaling, layout mode, orientation and privacy settings.
No minimum Discord/browser/OS version is established by this research.

| Candidate client / input family | Required real scenario coverage |
| --- | --- |
| Windows Discord desktop + keyboard/mouse | Focused/PIP/grid transitions, Discord shortcut conflicts, focus entry/exit from iframe and dialogs, role/reconnect states, NVDA pairing where usable |
| macOS Discord desktop + keyboard/trackpad | Same lifecycle and focus checks; VoiceOver/keyboard navigation and platform shortcut conflicts |
| Browser-hosted Discord on intended Chrome/Edge/Firefox | Record exact supported browser/OS pair, privacy settings, iframe focus, zoom, cookies and screen reader pairing; support is conditional on actual Discord compatibility, not engine emulation |
| Safari/VoiceOver browser candidate | First establish real Discord/app compatibility; then test keyboard/reading order, form controls, statuses and modal focus. Do not infer support from a Chromium pass |
| iOS Discord + touch/VoiceOver | Portal enabled, safe areas, virtual keyboard, orientation, pinch/scroll, background/resume, modal and announcement order on an actual device |
| Android Discord + touch/TalkBack | Record Android/WebView/device, same lifecycle/safe-area/keyboard checks; test switch/voice input where in support scope |
| Stylus-capable device | Real pointer capture/cancel, pen versus touch, pressure if supported, palm rejection, interrupted drag, zoom/pan and non-drag alternatives; emulated touch cannot establish hardware behavior |
| Older/unsupported client or tiny PIP/grid tile | Unsupported command/context gives safe feedback and preserved work. Navigation/status summary remains usable; an explicit expand-to-edit affordance may be needed after product review |

Synthetic component stress cells used locally: **320×640, 360×640, 390×844,
768×1024, 1024×768, 1280×720, 320×256 and 568×320 CSS pixels**. These are chosen
research inputs, not measured Discord/device viewport sizes or product minimums.
Real acceptance additionally needs continuous resize, 200% text enlargement,
400% browser zoom/reflow, keyboard occlusion, safe-area insets and PIP/grid
transitions. Shrinking a viewport is not testing zoom, a device or the Discord
iframe. Allow essential canvas pan/zoom without making navigation/forms require
two-dimensional scrolling or hiding the current role/save/reconnect state.

## Practical accessible alternatives

| Approach | Useful coverage / limitation | Recommendation |
| --- | --- | --- |
| Canvas toolbar shortcuts only | Helps known sighted keyboard workflows but does not convey the board's objects, relations or reading order nonvisually | Necessary input route, insufficient as the only alternative |
| Read-only text export/summary | Useful overview and sharing; not equivalent authoring, moderation or object manipulation | Add as a complementary view, never call it complete editing parity |
| Semantic object outline + native edit forms | Named objects/groups, text and numeric movement/size, reading order and action descriptions can support keyboard, single-pointer and AT interaction | Preferred controlled integration experiment; share accepted state/IDs and command pipeline with canvas |
| Complex ARIA application/grid mirroring the entire canvas | Can model richer interaction but creates substantial keyboard, focus, announcement and screen-reader compatibility obligations | Defer until real user tasks show native lists/forms insufficient; do not blanket `role=application` over the shell |
| Separate textual/structured collaboration mode | Can support tasks that need no spatial editor; conversion may lose layout or freehand meaning | Evaluate explicit equivalent tasks and limitations with users rather than promising automatic visual understanding |

The outline should expose stable object identity, type/name, authorized text,
group/parent, authored description, reading order and relevant relations. Spatial
coordinates alone do not explain a diagram. Arrows need named endpoints/meaning;
images/freehand need meaningful authored descriptions and supported alternative
tasks. Do not invent semantic equivalence through auto-generated labels or claim
that every freehand/geometry task is solved by an object list. Unsupported object
types need explicit limitations and an accepted task alternative or remain a
blocking accessibility gap.

Future adapter: derive canvas and outline from the same **server-accepted**
authorized canonical state; keep pending/rejected drafts distinct. Raw onChange
or scene reads may include tentative local content and are not durable acceptance.
Use the accepted T3/T4/T8 operation/identity/undo contracts, not a second save or
permission system. List counts, labels, hidden objects, participant names and
announcements must obey the same tenant/board/object visibility as the canvas.

Keyboard/focus proposal: native controls and logical landmarks first, skip-to-
outline/navigation, explicit focus return after modal actions, no automatic
canvas focus on startup, and shortcuts scoped to the active editor with a visible
discoverable alternative. Do not intercept Discord/browser shortcuts globally.
Deleting an object or changing board should choose a documented next focus target;
remote updates/revocation/status must not steal focus. A modal may contain focus
while open but must allow Escape/close. Preserve navigation/selection for viewers;
disable only prohibited mutations with an accessible explanation, not the whole UI.

Touch/stylus proposal: single-tap select plus labeled forms/buttons for moving,
resizing and ordering; provide a single-pointer non-drag path as well as keyboard
commands. Maintain comfortable target spacing, discoverable gestures, pointer
cancel recovery and visible non-color-only selection. Test actual hardware; fields
or event types in an element schema do not establish pressure/palm rejection.

Reduced-motion/contrast proposal: default to restrained/no nonessential animation;
honor reduced motion in canvas follow/scroll transitions, preserve orientation and
avoid unexpected zoom. Test light/dark, forced colors, focus ring, selection,
disabled/loading/error states and user text settings. Color alone cannot signal
writer status or save outcome. The local fixture tests media branches/outer
control dimensions; it performs no comprehensive contrast or WCAG audit.

## Permission, reconnect and save feedback

Expose distinct states: editing unavailable/verification pending; local draft;
queued/unconfirmed; accepted revision only from a verified durable receipt;
rejected with preserved draft; offline/reconnecting; and unknown outcome awaiting
reconciliation. Never turn a timeout, reconnect or optimistic grant into “saved”
or writer authority. Scope an historical receipt to its original lineage; it must
not mark restored active content saved. T1/T2/T4/T5/T8 supply those trusted facts.

Use concise polite status updates for meaningful transitions, an appropriate error
region for actionable failures, explicit request/grant/revoke/expiry text and no
per-pointer/per-element live-region chatter. Preserve a user's draft/focus and
offer deliberate retry/discard/reconcile. Test announcement order and verbosity
with real screen readers; DOM role attributes are only part of that evidence.

## Local prototype, browser checks and observed results

[Standalone prototype](t7-outline-prototype.html) contains two synthetic text
objects, native outline/form controls, numeric non-drag positioning, a keyboard
guide modal and explicit local simulation controls. It loads no Excalidraw, SDK,
external font or network resource. It neither integrates nor adopts #483. Its
simulated role/receipt controls are **not backend enforcement or durable saves**.
[Screenshot](t7-fixture.png) was inspected for visible layout/focus/error feedback;
this is agent visual inspection, not human accessibility review.

```sh
python scripts/research/t7-browser-probe.py --output docs/research/t7-browser-evidence.json
python scripts/github-bootstrap/validate.py
git diff --check
```

The [probe](../../scripts/research/t7-browser-probe.py) uses an already-cached
immutable `mcp/playwright` image through its own Docker MCP stdio session, not a
shared browser, local package install or HTTP service. It has network=none,
no host mounts/volumes/ports, one CPU, 768 MiB and 256 PIDs. It stops only its
own process/container, checks its invocation label before forced cleanup if
needed, and reads back absence. Existing workloads and WSL were not targets.
No image pull is performed; a missing image is an explicit local blocker.

Environment: Windows PowerShell/Python **3.14.3**; MCP server
**1.61.0-alpha-1781023400000**; cached Chromium **149.0.7827.22**. The cached image's
entrypoint explicitly uses `--no-sandbox`, recorded in evidence; this is bounded
local browser automation, not production isolation or the sandbox-enabled #483
browser configuration. Exact image/source/screenshot hashes are in the report.

[Current evidence](t7-browser-evidence.json): **23 assertions passed** covering
keyboard skip/selection/form submission, modal focus/Tab/Escape restoration,
semantic pending status without focus theft, no promotion before simulated ACK,
revoke/reconnect/rejection draft preservation, accepted local text/position,
invalid/corrected input, eight reflow/44×44 outer-control viewport checks and
reduced-motion/forced-color media emulation. Width checks establish no horizontal
page overflow in those cells, not full zoom/layout/contrast/AT acceptance.

[Initial failure](t7-browser-initial-evidence.json) is retained: the one-button
dialog failed the contained-Tab assertion. Added explicit Tab handling for that
single-control research dialog; the rerun passed. Screenshot inspection then
found an error remaining after corrected input; it now clears on valid input and
reports draft/unaccepted state. The harness's automatic-remove race was fixed
with absence readback; all owned containers were confirmed absent. No test was
weakened to pass. These are research fixture fixes, not Guildboard feature fixes.

Local verification also passed JS syntax checking, all 14 source metadata entries,
prototype/test/screenshot hash agreement and planning validation (471 items,
457 expected native relationships, 600 expected dependencies, zero errors).
The validator's unrelated CRLF-only audit rewrite was restored; final whitespace
validation passed. Hosted workflows are unchanged and do not execute this browser
probe. The publication handoff records the exact SHA and hosted planning result.

## Acceptance handoff and unavailable evidence

| #228 scope | Observable local/source evidence | Still-required acceptance |
| --- | --- | --- |
| Supported viewport/client matrix | D1–D3, concrete candidate matrix and eight synthetic cells | Real registered-app client/build/OS/browser/device/zoom/PIP/safe-area matrix and approved minimum support policy |
| Practical keyboard/nonvisual alternatives | E1/E2/W1–W6; separate object/form prototype and focus/edit checks | T3/T7 accepted semantics/operation bridge; real keyboard, screen-reader and user tasks including groups/arrows/freehand/images/large boards |
| Touch/stylus/reduced motion/contrast | W3/W4/W7–W9; 44×44 outer controls/media emulation | Real touch/stylus/switch input, gesture cancellation, perceived contrast/focus and assistive-technology feedback |
| Permission/reconnect/status feedback | W5 and explicit local draft/pending/accepted/rejected states | Actual authorization/revocation/socket/receipt/lineage integration with no false save status or data leaks |
| Sources/versions/alternatives/uncertainty | 14 dated source observations, exact #483 input, local browser hashes/results and screenshot | Actual UX & Accessibility/security/consumer/CODEOWNER review and accepted #229 specification |

No actual screen reader, disabled participant/user study, mobile/stylus device or
Discord client was exercised; browser automation/DOM semantics do not prove
speech output, usability or WCAG conformance. Registered test app/portal/client
access and approved mappings remain unestablished as recorded in #491. Real
GoDaddy HTTPS/WSS/proxy behavior and release acceptance remain separate.

#229 consumes this proposed responsive/focus/feedback specification. T3 owns
canvas adapter semantics, T1/T2 identity/permissions, T4/T5/T8 accepted state,
T9 privacy/tenant review and T12/T13 real verification/release gates. #228/#229
native blockers and required current-head Copilot/independent Sol MAX, actual
functional/security/consumer/CODEOWNER review, hosted CI, merge and post-merge
checks remain pending; no architecture adoption or issue closure is implied.

## Campaign harness recheck, 2026-11-13 UTC

At `07f3e25575b9a3a89704a9f7835a846ba3664bce`, the harness now
persists a blocked report when Docker discovery, cached-image inspection or
process startup fails, including the error and environment. Three negative
startup controls passed. Previously those failures escaped before any output
report was written. No preflight failure is counted as browser coverage.

The exact Docker probe is blocked on this host by Docker socket permission
denial; no container was started and no Docker permissions were changed.
Separately, all 23 unchanged browser assertions passed with Playwright 1.56.1,
Node 26.13.0 and sandbox-enabled system Chromium 155.0.8059.84 on Arch Linux.
The fallback loaded the standalone fixture with `setContent`; it did not run
the original Docker/MCP environment. Agent inspection of its screenshot found
the expected selected object, field focus, cleared error and draft status.
The original historical evidence and screenshot remain unchanged; separate
results are appended under `campaign_verifications` in the evidence JSON.
These local checks do not satisfy the remaining client/AT/hardware/consumer
review gates or unblock #229.
