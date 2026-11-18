# GB-T3.R1: pinned canvas research, partial evidence

Issue [#98](https://github.com/CompleteTech-DiscordApps/guildboard/issues/98), initially observed 2026-10-24 UTC with refreshes on 2026-10-25 and 2026-10-26 UTC. **Research is incomplete and not accepted.** This record and isolated fixture do not unblock #99, adopt dependencies into the application, or establish editor/server/platform correctness.

## Evaluated version and method

Excalidraw npm `@excalidraw/excalidraw@0.18.1`, source commit `a2ec2889babf7d2295469c6d90ebe77fae57df84`, matches the candidate inspected in PR #477. The source revision and published package are separately identified; source-to-package reproducible build is not proven. Fixture-only React/ReactDOM 18.3.1 satisfy the package's declared peer range. Esbuild 0.25.12 and Playwright 1.56.1 are research tooling, not proposed application tooling.

Read-only primary-source inspection plus a locked local fixture are provided. Node 24.22.1/npm 11.9.0 installed 264 packages with lifecycle scripts disabled. The exact editor tarball integrity is retained in the fixture lockfile and matches PR #477's pin. Neither this install nor a successful bundle establishes full transitive/license/security clearance. Do not distribute this research bundle as the application; #16/#17 retain license and shipped-file review.

### Fixture dependency remediation, 2026-10-25

The original lockfile reproduced 11 affected package entries in `npm audit` (2 high, 7 moderate, 2 low), including transitive propagation. The research fixture now applies the following exact overrides; only these four package entries changed in the lockfile. Excalidraw remains **0.18.1 with the same tarball integrity**, and React, ReactDOM, esbuild, Playwright and other resolved packages are unchanged.

| Consumer / dependency | Publisher declaration / prior resolution | Fixture resolution | Primary evidence |
| --- | --- | --- | --- |
| Excalidraw / Nano ID | `3.3.3` | `3.3.18` | [Maintainer overflow advisory](https://github.com/ai/nanoid/security/advisories/GHSA-xwg4-73v4-xw9w), [3.3.18 release](https://github.com/ai/nanoid/releases/tag/3.3.18) |
| mermaid-to-excalidraw / Nano ID | `4.0.2` | `5.1.16` | [Maintainer 5.1.16 negative-size fix](https://github.com/ai/nanoid/releases/tag/5.1.16) |
| Chevrotain consumers / lodash-es | `4.17.21` | `4.18.1` | Maintainer [template-import injection](https://github.com/lodash/lodash/security/advisories/GHSA-r5fr-rjxr-66jc) and [array-path prototype deletion](https://github.com/lodash/lodash/security/advisories/GHSA-f23m-r3pf-42rh) advisories identify 4.18.1 for lodash-es |
| Mermaid / KaTeX | `^0.16.47` / `0.16.47` | `0.18.2` | [Maintainer inherited-trust advisory](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7) |

These are **fixture runtime overrides, not the dependencies declared by the evaluated publisher tarball**. The Nano ID 4→5 and KaTeX 0.16→0.18 overrides cross the requested ranges. Named Nano ID generation APIs, KaTeX `renderToString`, valid lodash operations, the complete bundle and the bounded browser smoke pass on Node 24.18.0/npm 12.2.0. This does not establish every Mermaid/math/editor workflow's compatibility or authorize application adoption. No force update, editor downgrade, audit suppression or dependency removal was used.

Five new dependency regressions fail against the original lockfile and pass with the overrides: both consumer-resolved Nano ID copies handle zero/negative sizes without hanging; lodash rejects template import expressions and protects prototype properties from array-wrapped paths; KaTeX ignores inherited trust. Generator probes run in owned child processes with a three-second timeout. Together with the existing wrapper test, **6 unit tests pass**. A fresh full `npm audit --json` reports **zero vulnerabilities** on 2026-10-25; that dated registry result is not exhaustive security or license clearance. Exact pins, hashes, counts and historical evidence are retained in the evidence record.

## Findings and decision inputs

All source links below point to that immutable revision.

| Scope | Observable source review result | Consequence and unresolved question |
| --- | --- | --- |
| Element identity | [element/types.ts](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/element/types.ts#L39-L79) defines IDs, version, versionNonce, deletion state and customData; [newElement.ts](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/element/newElement.ts#L126-L152) preserves a supplied nonempty ID or generates one. | Preserve server-assigned IDs and tombstones; neither versionNonce nor arbitrary customData proves tenant ownership or accepted revision. The public [convertToExcalidrawElements helper](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/data/transform.ts#L494-L516) regenerates IDs unless `{regenerateIds:false}` is explicitly supplied; the fixture now wraps it with that option. Duplicate IDs, pasted binding remapping and concurrent deletion need adapter tests. |
| Controlled changes / echo | [App.tsx updateScene](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/components/App.tsx#L3885-L3950) replaces scene elements; the [update callback](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/components/App.tsx#L2875-L2885) invokes onChange outside loading, without a local/remote-origin argument. | Do not interpret every callback as local authorized intent. History capture control is not documented callback suppression. The local smoke observes one callback for one remote hydration; origin classification, echo suppression and proposed-write reconciliation remain unverified. |
| Undo | [store.ts](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/store.ts#L40-L71) distinguishes IMMEDIATELY/NEVER/EVENTUALLY; [updateScene](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/components/App.tsx#L3925-L3934) captures history or updates the snapshot; [history action](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/actions/actionHistory.tsx#L48-L75) operates on local history and excludes view mode. | NEVER is the candidate remote-hydration setting. It does not by itself enforce accepted-intent undo, permission changes, other-user revisions or restore epochs. Server-fenced inverse operations and rollback experiments remain necessary. |
| Assets / serialization | [BinaryFileData](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/types.ts#L91-L105) carries data URLs and file IDs; [JSON serialization](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/data/json.ts#L43-L66) selects local/database output. | Editor serialization is not the trusted server schema. Bound bytes, validate formats, separate private asset authorization and prohibit credential/ephemeral identity persistence. Asset roundtrips, broken images, unsafe imports and export-font embedding remain untested. |
| Accessibility | [Undo ToolButton](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/actions/actionHistory.tsx#L76-L85) has an aria-label and keyboard shortcut. | One accessible control is not an accessibility audit. Keyboard-only editing/navigation, focus after dialogs, screen-reader semantics, contrast and moderated-state announcements need real browser/assistive-technology checks. |
| Touch / stylus | [freehand element type](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/element/types.ts#L354-L370) retains pressures. | Data fields do not establish stylus hardware support or usable gesture behavior. Test pointer capture/cancel, pressure, palm rejection, pinch/pan and Activity clients on actual supported devices. |
| Moderated/read-only editing | [view-mode prop](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/types.ts#L538) and multiple UI guards exist; imperative updateScene does not check the prop. | Read-only is a UX control, never an authorization boundary. A privileged adapter can hydrate a viewer; a forged client must still be denied by the server with zero durable side effects. API mutability in view mode is not itself a defect. |
| Custom editing | Custom data and element composition exist, but the type union is not an arbitrary new-tool plugin contract. | Evaluate bounded text+rectangle grouping for sticky notes, ownership and atomic operations before adopting; do not promise unsupported custom element types. |

## Reproducible local fixture

`research-fixtures/canvas` is deliberately outside root workspaces. It does not change the application manifests. Its lockfile contains third-party research dependencies; generated bundle and node_modules are ignored.

From that directory:

```
npm ci --ignore-scripts --cache /tmp/guildboard-canvas-npm-cache
npm audit --json
npm test
npm run build
node --check probe.mjs
npm run probe
npm run probe:network
```

By default Playwright selects its managed browser, which must already be provisioned.
Set `CHROMIUM_PATH` only to use an explicit executable; neither probe downloads a
browser or disables Chromium sandboxing. The recorded Windows runs supply the
existing cached Chromium 156.0.8078.4 executable through that variable.

Build uses `--conditions=production`, required by this pinned package's conditional CSS export. The earlier build without the condition failed and was corrected; the final production-condition bundle builds. Output is an unminified research artifact (about 13.1 MiB JS and 160 KiB CSS), **not** a production payload/performance result.

The probe binds only loopback, allows intercepted network requests only to its exact fixture origin, enables Chromium sandboxing, records bounded callback metadata from synthetic elements and closes the browser/server. The file server resolves both root and requested file with `realpath` and checks `path.relative` containment before serving; an in-root symlink/junction cannot disclose a file outside that root. The named recorder retains the original event fields and fixed 200-entry cap. No production board data, credentials or screenshots are collected. These are local fixture controls, not application-server or authorization acceptance. They are not required CI gates; portable browser provisioning and the broader runtime matrix remain separate work.

### Actual result

The initial 2026-10-24 attempt using Chromium 155.0.8059.79 failed **before loading the fixture** with process-singleton `socket() failed: Operation not permitted` and crashpad-directory errors. Zero browser assertions ran then; that failure remains in `initial_observation` in the evidence record.

The authorized 2026-10-25 refresh on Windows used Node **24.18.0**, npm **12.2.0**, Playwright **1.56.1** and explicitly supplied cached Chromium **156.0.8078.4** through `CHROMIUM_PATH`. A clean scripts-disabled install, clean full audit, six unit tests, final bundle build, syntax check and planning validation passed. With the overrides installed, the unchanged original `probe.mjs` passed its **three bounded smoke checks**: preserved remote ID, a NEVER-captured remote baseline surviving one local undo, and unchanged content after view-mode pointer/unselected shortcut attempts. It recorded **one remote callback**, **zero blocked external requests** and no page errors. Chromium sandboxing stayed enabled. This browser/version pairing is observed local evidence, not a portable CI or Discord compatibility guarantee.

The 2026-10-26 review remediation passes **14 unit tests**, a clean full audit,
build/syntax/planning checks, **six editor smoke checks** and **four synthetic
network controls** on the same Node/npm/Chromium versions. Actual Windows junction
tests reproduce the former escape (HTTP 200 before the fix, 404 afterward), retain
an in-root junction as a 200 control, and reject encoded traversal and malformed
paths. Recorder tests preserve the event shape and prove recording stops at 200.

The editor probe now prepares an undoable local edit, selects existing content
through the editor API, and observes unchanged content after view-mode Delete,
undo and pointer attempts. Re-enabling editing and successfully undoing the
prepared edit is a positive control for retained history. It still records one
remote callback, no blocked editor requests and no page errors. This is bounded
local evidence; API-supplied selection is not a real user-selection workflow.

The routing probe observes successful `data:`/`blob:` text fetches and image
decoding, with **zero corresponding Playwright route interceptions**. The claim
that the hostname guard aborted those resources is not reproduced in this
scenario; no broad non-network allowlist was added. A request to another
`127.0.0.1` port is deliberately blocked, and its server receives zero requests.
The origin check prevents that real network boundary crossing. These controls
do not establish universal scheme behavior across browsers or a production CSP.

The historically named evidence JSON is an aggregate: its top-level fields name
the latest run, `initial_observation` retains the dated blocked attempt, and
`refresh_history` retains the prior successful refresh. Its top-level aggregate
note explains this without renaming the file or dropping history. The wrapper
unit test still only verifies the converter option and references; editor
conversion is exercised by the browser probe. The full matrix below remains open.

## Runtime matrix still required

1. Remote hydration with NEVER: preserve IDs/tombstones; observe callback counts/origin; prove repeated accepted state does not emit proposed writes.
2. Local edit A then remote edit B then undo/redo: preserve B, express only accepted A inverse, reject stale revisions and prevent forbidden resurrection. Current probe passes only a simpler remote baseline/local-history undo scenario; it does not test concurrent remote overwrites or server-fenced inverse intent.
3. Reject optimistic local change and rollback; repeat after role revocation/epoch change, reconnect and restore. The bounded local rollback below filters the hydration echo and reproduces a native undo/redo failure. Accepted-intent history and session-change paths remain open.
4. Viewer keyboard shortcuts, pointer drag, delete, paste, drop, text input, context menu and imperative hydration; navigation remains available, server denies every forged mutation. The earlier smoke supplies selected content through the API and retained history for Delete/undo controls, with a writable undo positive control. The 2026-11-18 fresh-page input matrix below adds pointer/keyboard selection, drag, Delete and existing-text trials; its local browser launch is blocked and observed results require the native fixture run. Paste/drop/context-menu, text creation and every server denial remain unverified.
5. Asset add/roundtrip/export, missing files, excessive data, malformed imports, external URL requests, fonts/CSP and private-file denial.
6. Keyboard-only/assistive technology, touch and real stylus; drag interruption, focus restoration and repeated controls.
7. Compound groups/arrows/text/sticky-note representation; deterministic IDs/bindings, multi-element atomicity and concurrent changes.
8. Actual Discord iframe/proxy/client matrix and agreed large-board latency/memory budgets. Local loopback cannot establish these or GoDaddy deployment behavior.

## Alternatives and recommendation

Continue a controlled adapter experiment, **not adoption**, because public interfaces expose candidate hooks without proving moderated consistency. Maintain an Excalidraw fork only if a documented invariant cannot use public interfaces, with upgrade/security/license cost explicitly accepted. A custom canvas trades control for substantial editing/accessibility maintenance. Full-scene last-write-wins synchronization is not an acceptable fallback for server-authoritative permission and revision requirements.

#98 remains open until missing experiments, functional/security/consumer review, merge and post-merge evidence are resolved. #99 must not treat this partial source review or build as an accepted Tier specification. Discord and GoDaddy provisioning remain out of scope for this fixture.

## Campaign recheck, 2026-11-13 UTC

Integrated current main `c108b552a660e12a3b3998e1e1ad944fbd7a894d` at
`89ed4a121f7624e90431cc212b3ab79333d366da`. On Arch Linux, Node 26.13.0,
npm 11.20.0 and sandbox-enabled system Chromium 155.0.8059.84, the documented
scripts-disabled install, 14 unit tests (zero skips), full dependency audit
(zero vulnerabilities), build, syntax and planning checks passed. All 13 stored
fixture source hashes match. Six editor checks and four network controls passed;
raw browser results are appended under `campaign_verifications` in the aggregate
evidence. This retains the previous dated observations and acceptance gaps.
The current-main integration changes only inherited workflow content; it does
not establish Discord/AT/hardware acceptance or complete #98/#99.


## Isolated Linux CI prerequisite, 2026-11-16

The repository workflow `.github/workflows/canvas-feasibility.yml` is intended to run on pull requests and pushes to main affecting the fixture or workflow. In `research-fixtures/canvas` it runs `npm ci --ignore-scripts`, `npm test`, `npm audit --audit-level=low`, `npx --no-install playwright install --with-deps chromium`, `npm run probe`, and `npm run probe:network` on Ubuntu with Node 24. The probes log the managed Chromium version; the workflow logs Node and npm versions. Native fixture run [43974670111](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43974670111) and planning 3-OS run [43974670128](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43974670128) passed at head b210e75 (merged as 57641db); earlier October and Windows/cached-Chromium observations remain historical.

This isolated Linux fixture and its network controls do not establish Discord, touch/stylus, screen-reader, authorization, concurrent production behavior, or licensing approval. Issue #98 remains incomplete, #99 remains blocked, and Copilot re-review of head b210e75 was requested but has not arrived and remains outstanding.

## Accepted experiment direction and runner correction, 2026-11-16

The accepted T0 direction in [ADR 0001](../adr/0001-editor-activity-vps-direction.md) and [ADR 0004](../adr/0004-editor-and-database-selection.md) already selects a controlled Excalidraw adapter experiment. The historical recommendation above and the aggregate artifact's absence-of-acceptance statements concern this partial research and production behavior; they do not revoke that accepted experiment direction or require another generic team decision. Issue #98's unresolved experiments and #99's native dependency remain open.

[The first native fixture run](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43971151212) on `24b8cdd589b606566b8014c268f020d956e19cb2` passed dependency installation, unit tests and the full audit, then failed browser installation because `ubuntu-latest` supplied Ubuntu 26.04, unsupported by pinned Playwright 1.56.1. The workflow now pins `ubuntu-24.04`, which that version's [platform classifier](https://github.com/microsoft/playwright/blob/v1.56.1/packages/playwright-core/src/server/utils/hostPlatform.ts) explicitly supports. Managed-browser installation and both probes require a successful successor run; no browser pass is claimed for the failed run. Browser sandboxing, dependency versions, audit policy and fixture controls are unchanged. The successor-run outcome is recorded in the [Isolated Linux CI prerequisite, 2026-11-16](#isolated-linux-ci-prerequisite-2026-11-16) section above.

### Sandbox-capable runner follow-through, 2026-11-16

[The Ubuntu 24.04 successor run](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43972072293) on `e266879ce55f7205d7ecbf17c1177b9184471557` installed managed Chromium and passed unit tests, full audit and bundle build, then failed browser launch with `No usable sandbox`. Its network controls were skipped. The job now uses `ubuntu-22.04`, listed by [GitHub's runner images](https://github.com/actions/runner-images#available-images) and the pinned Playwright platform classifier. This is a supported runner choice: it adds no privileged steps, AppArmor/sysctl changes, custom browser flags or sandbox bypass. `chromiumSandbox: true` remains required. A successful native successor run must establish actual launch and probe results; neither failed run establishes browser behavior. The successor-run outcome is recorded in the [Isolated Linux CI prerequisite, 2026-11-16](#isolated-linux-ci-prerequisite-2026-11-16) section above.

## Hydration echo experiment, 2026-11-17

The fixture adds a bounded comparison for synthetic rectangle scenes. The
browser probe registers an in-memory observer on the real Excalidraw 0.18.1
`onChange` callback, records an accepted projection before each
`updateScene` with `CaptureUpdateAction.NEVER`, and exercises an initial
snapshot, a replay with freshly converted objects, and a changed snapshot.
Each includes an explicit tombstone. The probe asserts the expected element
IDs, geometry and deletion flags after hydration and zero candidate writes.
A pointer-drawn rectangle is the positive control for a candidate observation.
The fixture counts candidates in memory and sends no mutations. The accepted
snapshots are synthetic, with no backing server, permissions or revisions.

From `research-fixtures/canvas`, run `npm ci --ignore-scripts --no-audit`,
`npm test`, `CHROMIUM_PATH=/usr/bin/chromium npm run probe` and
`CHROMIUM_PATH=/usr/bin/chromium npm run probe:network` for the Linux run.
Omit `CHROMIUM_PATH` when using provisioned Playwright Chromium.

On Arch Linux with Node 26.13.0, npm 11.20.0, Playwright 1.56.1 and
sandbox-enabled Chromium 155.0.8059.84, the build and editor probe passed.
Initial, replayed and changed hydration each delivered one real callback and
zero in-memory candidates, preserving the two IDs, geometry and tombstone.
The pointer gesture added a rectangle and delivered nine callbacks and six
candidate observations in this run. Candidate counts can vary during drawing
and require aggregation before they can represent a gesture. The earlier six
editor checks and four isolated network controls also passed. The editor
probe reported zero blocked requests and no page errors. The historical aggregate keeps the source hashes and results
for its earlier runs.

All three new unit tests passed. The full fixture suite passed 15 of 17 tests
on this host, including when run serially with Node 24.18.0. Two existing
lodash-es dependency probes hit their three-second timeouts. Running the
unmodified base revision's dependency test file with the same locked
dependencies reproduced both timeouts. Planning validation and JavaScript
syntax checks passed.

The observer compares a projection of IDs, scene order, type, rectangle
geometry and deletion flags with the current accepted and most recently
observed projections. Node tests use synthetic observations to check
duplicate suppression and demonstrate two limits: removing or reviving a
tombstone changes the projection, and a delayed older callback yields a
candidate after a newer accepted scene has been observed. Candidate detection
can only justify further validation. The experiment omits bindings, text,
styles, assets and any other element types, and does not model interleaved local
and remote state, stale or reordered hydration, rollback, or accepted-intent
undo.

For #99, the contract should require a revision and restore-epoch fence on
accepted hydration, explicit local intent, and server validation before any
mutation. The local rejection probe below adds a bounded callback sequence.
Research still needs callback evidence for revocation, reconnect and concurrent
overwrites. Collect
Discord iframe/proxy behavior in supported clients, screen-reader and
touch/stylus results with actual assistive technology and hardware, and
applicable GoDaddy staging evidence separately. The partial fixture provides
no external acceptance. #98 remains open and #99 remains blocked.

## Rejected optimistic edit rollback, 2026-11-17

The local probe clears the earlier smoke-test history, draws a rectangle
with a real pointer gesture, and records the new ID. It then simulates
a rejected mutation by restoring the existing accepted snapshot via
`updateScene` with `CaptureUpdateAction.NEVER`. The rollback asserts
the same IDs, geometry, scene order and deletion flags as the accepted
snapshot. The probe next runs native keyboard undo and redo against the
writable editor, following the pinned [history action](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/actions/actionHistory.tsx#L48-L75).

From `research-fixtures/canvas` with the existing locked dependencies and
provisioned Chromium, run `CHROMIUM_PATH=/usr/bin/chromium npm run probe`.
On Arch Linux with Node 26.13.0, Playwright 1.56.1, Excalidraw 0.18.1 and
sandbox-enabled Chromium 155.0.8059.84, restoration delivered one real
callback and zero further in-memory candidates. Native undo then introduced
the rejected ID as a tombstone. Native redo restored the rejected rectangle
as a live element under the same ID. Each shortcut delivered three callbacks
and one candidate in this run. The probe asserts the history effects and
candidate presence. Counts describe the observed run.

The rejection and accepted snapshot are simulated. The pointer input,
imperative rollback, editor scene and native keyboard history effects are
measured in Chromium. The observer sends no writes. For #99, restore the
accepted scene on rejection and fence native history from the mutation
path. A proposed inverse needs accepted local intent, the current board
revision and restore epoch, and server-side validation. Native redo in
this scenario can reintroduce a rejected edit even after an echo-free
rollback. Preserving accepted undo history through rollback and handling
revocation, reconnect, restore and concurrent changes remain unresolved.

## Undo button keyboard probe, 2026-11-17

From `research-fixtures/canvas`, with the existing bundle and locked dependencies,
run `CHROMIUM_PATH=/usr/bin/chromium node probe.mjs`. Use `npm run probe` with
the same environment variable to rebuild first. On Arch Linux with Node
26.13.0, Playwright 1.56.1, Excalidraw 0.18.1 and sandbox-enabled headless
Chromium 155.0.8059.84, Playwright located an enabled, visible button by the
accessible name Undo. After the probe programmatically focused that button,
pressing Enter moved focus away and left the prepared edit visible.
After a pointer click returned focus to the editor, Control+Z removed the
same prepared edit in the positive control.

This scenario exercises an editor-provided control with an API-prepared edit
and programmatic focus. It leaves keyboard-only tab order, focus destination
and restoration, Space activation, screen readers, hardware input and
Discord Activity clients unverified. For #99, verify keyboard activation and
focus behavior for the user-facing accepted-intent history controls.

## Opaque image file reference probe, 2026-11-17

From `research-fixtures/canvas` with a built bundle and locked dependencies,
run `CHROMIUM_PATH=/usr/bin/chromium node probe.mjs`. On Arch Linux with Node
26.13.0, Playwright 1.56.1, Excalidraw 0.18.1 and sandbox-enabled Chromium
155.0.8059.84, `updateScene` preserved the image element's synthetic file ID
while `getFiles` returned no data for the missing reference. Supplying a
one-pixel GIF through `addFiles` made `getFiles` return the same ID, MIME
type, data URL and creation timestamp. The scene retained its file reference.
No requests attempted to cross the loopback origin boundary during the probe.
The initial browser run closed before the scene loaded while the default
temporary volume was over quota. The successful run supplied a writable
local `TMPDIR` and kept Chromium sandboxing enabled.

This measures in-memory file registration and retrieval through the pinned
editor's [public API](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/types.ts).
It leaves rendered pixels, serialized export/import, validation of malformed
or oversized content, private asset authorization, and Discord/VPS delivery
unverified. For #99, treat asset references and file data as distinct contract
inputs and define the outcome when the reference cannot be resolved.

## Compound note projection and rollback, 2026-11-17

From `research-fixtures/canvas` with a built bundle and locked dependencies,
run `CHROMIUM_PATH=/usr/bin/chromium node probe.mjs`. Use a writable local
`TMPDIR` if the default temporary volume is over quota.

The fixture converts a synthetic rectangle and text element with distinct IDs,
gives them the same group ID, and stages both in one `updateScene` call with
`CaptureUpdateAction.NEVER`. After a simulated denial, it replaces the scene
with the earlier accepted snapshot in another `NEVER` update. Assertions
require the staging callback to include both live members with the shared
group ID, the rollback callback to include neither member, and the final
scene to match the accepted snapshot. The probe checks each observed callback
within the fixture's two-frame window after each update.

On Arch Linux with Node 26.13.0, Playwright 1.56.1, Excalidraw 0.18.1
and sandbox-enabled Chromium 155.0.8059.84, the probe observed one staging
callback with both members, one rollback callback with neither member,
and zero partial callbacks. The accepted snapshot matched after rollback.
This exercises grouping and scene projection in a local browser. The denial is injected by the fixture. The result leaves actual
moderation, database atomicity, concurrent edits, bound-text behavior and
client delivery unverified. For #99, use stable member IDs and define a
single operation with server-side validation of every member before
publishing or rolling back a compound change.


## Ordinary keyboard navigation to Undo, 2026-11-17

Run `npm run probe` from `research-fixtures/canvas` after the locked install.
The [navigation probe](../../research-fixtures/canvas/keyboard-undo-probe.mjs)
seeds a baseline and one undoable synthetic edit. Each of the four combinations
starts in a fresh browser page with a 1200×800 viewport. Keyboard traversal and
activation use ordinary key presses. The probe records any scene and focus
change and checks that the same synthetic history can be undone with a separate
Tab-to-editor and Control+Z control.

| Route from the document body | Presses to Undo | Enter on a fresh edit | Space on a separate fresh edit |
| --- | ---: | --- | --- |
| Tab | 10 | Removed the edit and focused the body | Retained the visible scene and Undo focus |
| Shift+Tab | 2 | Removed the edit and focused the body | Retained the visible scene and Undo focus |

Local evidence used Node 24.22.3, sandboxed Chromium 155.0.8059.84 and pinned
Excalidraw 0.18.1. The shortcut control preserved the baseline and removed the
edit after one Tab from the body to the editor. The browser recorded zero page
errors and zero blocked requests. The earlier programmatic-focus experiment had
a different Enter result under its separate setup. The combined evidence informs
#99's keyboard and focus-restoration requirements. Screen-reader announcements,
actual participant accessibility, physical input and Discord clients need their
own evidence.

## Synthetic asset serialization, 2026-11-17

The [asset fixture](../../research-fixtures/canvas/asset-probe.mjs) passes a
one-pixel synthetic GIF through the editor's `serializeAsJSON` and `loadFromBlob`.
Each import receives no supplemental live editor state. Local JSON round trips
preserved the registered file's ID, MIME type, bytes and timestamp. Local JSON
before file registration and database-mode JSON after registration both
preserved the scene's file reference with no bytes. A separate network control
confirmed that the secondary loopback server received zero requests.

The two browser commands `npm run probe` and `npm run probe:network` passed
after a clean locked install using sandboxed Chromium 155.0.8059.84. #99 can use
these results to distinguish its scene contract from authorized file delivery.
Decoded rendering, malformed or oversized content, private authorization, and
real delivery remain open.

## Fresh-page viewer input matrix, 2026-11-18

The [input probe](../../research-fixtures/canvas/viewer-input-probe.mjs), invoked
by `npm run probe`, adds four matching writable/viewer trials. Every trial uses
a fresh isolated page, a 1200×800 viewport, two live synthetic elements
(`input-rectangle` and `input-text`) and an explicit deleted element
(`input-tombstone`). API calls seed the scene and set view mode; selection and
editing use actual Playwright pointer and keyboard events. No selected IDs or
active tools are supplied through the API in these trials. Existing smoke,
hydration, undo, asset and compound checks remain intact.

| Trial on independent writable and viewer pages | Writable positive control asserted | Viewer invariant asserted |
| --- | --- | --- |
| Click rectangle edge, then Delete | Pointer selection contains the rectangle ID; Delete tombstones it | Complete scene stays identical, including all IDs and deletion flags |
| Control+A, then Delete | Both live IDs selected; both become tombstones | Complete scene stays identical |
| Drag rectangle edge by (80, 40) | Same rectangle ID moves by exactly that delta | Complete scene stays identical; viewport observations are separate |
| Double-click existing text, Control+A, type, Escape | Text editor opens and the same text ID contains the replacement string | Complete scene stays identical |

Two additional fresh-page wheel trials require navigation in both modes while
preserving the full scene. Each trial records before/after scenes with complete
element fields, selection IDs, text-editor presence, active tool and viewport.
Every callback is copied immediately with complete elements, selection IDs and
view mode; a 200-callback cap fails explicitly instead of silently truncating.
Viewer assertions cover every recorded callback as well as the final scene.
Failure diagnostics retain the observed scene and callback sequence. Frame
settling is bounded to two animation frames with a five-second timeout; page
actions and predicate waits have a ten-second default timeout. These are bounded
observation windows, not a proof that delayed effects cannot occur.

The source baseline for this addition is
`17d97f4d1b5bcf97e8a8494d25db17480efe21e9`. The evaluated editor remains
Excalidraw **0.18.1**, separately identified upstream source commit
`a2ec2889babf7d2295469c6d90ebe77fae57df84`; fixture React/ReactDOM remain
18.3.1, esbuild 0.25.12 and Playwright 1.56.1. No dependency, override, launch
option or network-origin rule changes. The public API/source links above remain
the evaluated primary references; no newer release was evaluated.

Local attempted verification used Debian GNU/Linux 13.6, Node **24.22.3**,
npm **11.9.0** and installed Chromium **156.0.8078.79**:

| Exact command | Exit and observed result |
| --- | --- |
| `npm ci --ignore-scripts --offline --no-audit` (fixture directory) | 1; cache lacked the locked zustand 4.5.7 tarball |
| `npm ci --ignore-scripts --no-audit` (fixture directory) | 0; 252 locked packages installed via public dependency retrieval, lifecycle scripts disabled |
| `npm test` (fixture directory) | 0; 17 tests passed, zero skips |
| `CHROMIUM_PATH=/usr/bin/chromium npm run probe` (fixture directory) | 1; bundle succeeded, then browser launch aborted before any editor page/input trial |
| `CHROMIUM_PATH=/usr/bin/chromium npm run probe:network` (fixture directory) | 1; same pre-page browser-launch failure; network controls did not execute |
| `node --check research-fixtures/canvas/viewer-input-probe.mjs` (repository root) | 0; syntax only |
| `python3 -B scripts/github-bootstrap/validate.py` (repository root) | 0; 471 manifest items, no errors |
| `git diff --check` (repository root) | 0 |

Both browser commands retained `chromiumSandbox: true`. Chromium aborted with
`process_singleton_posix.cc:297` / `socket() failed: Operation not permitted`;
its subsequent crash handler also reported a denied ptrace. No browser input,
new selection behavior, callback count or viewer success is claimed for this
attempt. The existing path-triggered Canvas feasibility fixture workflow runs
the expanded `npm run probe` on Ubuntu 22.04 / Node 24 with managed Chromium.
Its actual PR-head outcome and emitted browser version must be read before
accepting the new matrix as runtime evidence. The local syntax/unit/planning
passes do not substitute for that browser result.

The [first native candidate run](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/44359238646)
at head `9d2634a247475018413c9459c7ac4c3b7dafdf98` installed dependencies,
passed all 17 unit tests and the full audit, built the bundle and executed
browser input. It stopped in the first viewer trial because the new callback
recorder's JSON copy omitted `customData: undefined`, while Playwright's direct
scene copy retained that key. The assertion diff shows that representation
mismatch on all three otherwise matching elements. Later viewer/navigation
trials and network controls did not complete in that run. The recorder now uses
`structuredClone` to preserve the complete element fields on both sides of the
same strict comparison; no scene field or invariant was removed. A successor
native run is required.

For #99, matching writable controls distinguish an ignored event from an
effective editing path, and complete deleted-element/callback observations
avoid relying only on visible-element counts. This experiment is local UI
research, with synthetic data and no application server, durable writes or
permissions. It does not establish server denial, revocation, concurrency,
paste/drop/context-menu behavior, text creation, touch/stylus, assistive
technology, Discord iframe/proxy/client behavior, GoDaddy behavior, performance
budgets or license/security acceptance. #98 remains open and #99 remains blocked.
