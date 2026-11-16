# Development setup

Current tooling needs Git, Python 3.11+ and GitHub CLI. The configuration diagnostics package can be built/tested with Node 24 and npm; see [packages/config](../packages/config/README.md). The Node application build, runtime dependencies and database implementation remain backlog work. Do not expect `npm start` to launch Guildboard.

1. Clone the repository and inspect the Project's Ready to implement view.
2. Run `python3 scripts/github-bootstrap/validate.py` for local planning integrity.
3. For read-only remote checks authenticate GitHub CLI and run `python3 scripts/github-bootstrap/audit.py`.
4. Before runtime implementation, accept the relevant research/specification issues and pin a supported Node LTS, dependency versions and lockfile.
5. Keep local `.env` files ignored; use separate development/staging/production secrets and databases.

The configuration-validation issue defines strict PORT, DATABASE_URL, DISCORD_CLIENT_ID and SESSION_SECRET behavior. Its small subtasks can be implemented independently from unresolved runtime architecture.

## Engineering conventions

Use Node 24 and `npm ci --ignore-scripts` with the committed lockfile. Run `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run boundaries`, `npm run test:engineering`, `npm run build`, and `npm run test:config`. The existing planning commands remain independent. CI runs these commands with read-only repository contents permission.

The dependency graph permits activity → contracts/canvas; canvas → contracts; auth → contracts; collaboration → contracts/auth; API and bot → contracts/config/auth/collaboration. Apps cannot import each other. Config is server-only; activity, canvas and contracts cannot import Node builtins. The AST checker includes source and test JavaScript and TypeScript under each workspace, including type imports and aliases. It excludes generated dist and node_modules and rejects symlinks in workspace trees, unknown workspaces, unresolved local imports, indirect require, dynamic module specifiers and malformed syntax. A server builtin name matched by a TypeScript paths pattern is resolved as a local workspace dependency and checked against the graph; an unresolved or non-workspace match is rejected rather than exempted as a builtin. Unmatched server builtins remain allowed. These are repository conventions, not a sandbox against hostile code or arbitrary external packages.

Builds clean each workspace dist first, then compile in dependency order. The config project deliberately compiles its tests into dist because its existing test command executes them; other projects compile their configured source. `engineering-build/manifest.json` records versions and hashes of workspace inputs, root configuration and outputs only after every compilation succeeds. A failed or interrupted build can leave partial dist files; absence of the completion manifest means those files must not be treated as a completed build. The interruption fixture tests publication only, not atomic application deployment. Changes to dependency versions require regenerating the lock using npm; do not hand-edit integrity fields.
