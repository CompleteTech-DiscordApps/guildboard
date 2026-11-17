# Platform evidence starting points

These primary pages were inspected during bootstrap. They establish where to begin research, **not** tested Guildboard compatibility or accepted architecture decisions. Each research issue must collect its own versioned evidence and experiments.

- [Discord Activities overview](https://docs.discord.com/developers/activities/overview): Activity iframe/Embedded App SDK model and links to networking/mobile/production guides. Guildboard client behavior and permissions remain unverified.
- [GoDaddy VPS Hosting](https://www.godaddy.com/hosting/vps-hosting): vendor VPS offering. No plan was bought, provisioned, sized or benchmarked. Linux image, limits and real deployment verification belong to T10.
- [GitHub Project copying](https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/copying-an-existing-project): copied fields/views/workflows/Insights exclude original items, collaborators and repository links; auto-add integration must be recreated.
- [GitHub Project item REST API](https://docs.github.com/en/rest/projects/items): supports multi-field item PATCH using numeric IDs resolved from live state. User-owned Project endpoints do not support installation/fine-grained tokens; scheduled full Project reads need a supported dedicated credential.
- [Project filtering](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects): filter field values independently and combine same-field alternatives with commas. Live GitHub autocomplete verified `work-type:`, `dependency-status:` and `release-target:` qualifiers.

Accessed during the 2026-10-23 America/New_York bootstrap session (2026-10-24 UTC). Platform docs may change; refresh evidence before implementation.

Focused research: [GB-T0.R1](research/GB-T0-R1-feasibility.md) adds version-pinned static package evidence and dated platform-source hashes. Its runtime and license-distribution limitations remain explicit.
