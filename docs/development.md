# Development setup

Current tooling needs Git, Python 3.11+ and GitHub CLI. The configuration diagnostics package can be built/tested with Node 24 and npm; see [packages/config](../packages/config/README.md). The Node application build, runtime dependencies and database implementation remain backlog work. Do not expect `npm start` to launch Guildboard.

1. Clone the repository and inspect the Project's Ready to implement view.
2. Run `python3 scripts/github-bootstrap/validate.py` for local planning integrity.
3. For read-only remote checks authenticate GitHub CLI and run `python3 scripts/github-bootstrap/audit.py`.
4. Before runtime implementation, accept the relevant research/specification issues and pin a supported Node LTS, dependency versions and lockfile.
5. Keep local `.env` files ignored; use separate development/staging/production secrets and databases.

The configuration-validation issue defines strict PORT, DATABASE_URL, DISCORD_CLIENT_ID and SESSION_SECRET behavior. Its small subtasks can be implemented independently from unresolved runtime architecture.
