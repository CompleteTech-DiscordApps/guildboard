# ADR 0001: Editor, Activity and VPS direction

Status: accepted direction for a controlled experiment. Stable issue ID: GB-T0.R1 ([#2](https://github.com/CompleteDotTech/guildboard/issues/2)).

## Question and constraints

Choose a bounded editor and hosting direction for a Discord Activity while preserving server authority and the mandatory GoDaddy Linux VPS deployment path. This decision does not complete the system specification or establish runtime feasibility.

## Evidence

The [feasibility research](../research/GB-T0-R1-feasibility.md), evaluated 2026-10-24 UTC, records primary sources, pinned candidate versions, static artifact evidence and limitations. It executes no package code and provides no browser, Discord, VPS, security or performance verification. The user/codeowner accepted the proposed direction in the [campaign decision record](https://github.com/CompleteTech-DiscordApps/guildboard/pull/477#issuecomment-6904122525). This records that acceptance; it is not a native GitHub self-approval or production authorization.

## Alternatives and decision

Accept a controlled experiment integrating Excalidraw inside a Discord Activity, with a server-authoritative API and collaboration service on the mandatory GoDaddy Linux VPS path. The evaluated packages remain candidates, not installed or approved distribution dependencies. The research records the evaluated versions and decision triggers.

A maintained Excalidraw fork could provide missing hooks at an upgrade and maintenance cost; a custom canvas offers control at substantial implementation cost. Revisit either if supported integration hooks cannot meet the required invariants. Full-scene last-write-wins is rejected because it cannot provide the required per-operation authorization, sequencing and conflict semantics. Managed Node hosting may be researched separately but does not replace the mandatory VPS path.

## Contracts and security implications

The client proposes bounded operations; it cannot establish identity, guild membership, roles or permission by assertion. The server must validate identity, tenant and board access, current grants and permission epoch, operation schema and resource limits for each mutation, including existing connections. Revocation must fence in-flight writes. The server sequences accepted operations and durably records them before acknowledgment; clients recover from accepted operations rather than overwrite an authoritative board with arbitrary snapshots. UI read-only controls are not authorization. Detailed concurrency, undo, recovery and protocol contracts remain for [system specification #3](https://github.com/CompleteDotTech/guildboard/issues/3) and downstream research.

## Consumer handoffs and acceptance

Owner acceptance of this direction is documented in the decision record above. [License policy #16](https://github.com/CompleteDotTech/guildboard/issues/16) and [verification #17](https://github.com/CompleteDotTech/guildboard/issues/17) remain mandatory gates for the installed dependency graph, shipped assets, notices and distribution packaging. No license clearance is granted here.

The linked feasibility research assigns real-browser editor, Discord client and GoDaddy VPS experiments to their downstream issues. Real-platform, security and performance validation remain necessary, including permission and revocation behavior, collaboration correctness, networking, recovery and measured capacity. Static evidence and this decision do not establish those results.

## Consequences and follow-up

Use the direction to develop reviewed contracts and plan the controlled experiment. Do not treat this ADR as package adoption, a complete specification, a passed runtime test, a deployment or a production readiness claim. Preserve the research pins and refresh their evidence when versions change; provision and deploy only under separate authorization and applicable gates.
