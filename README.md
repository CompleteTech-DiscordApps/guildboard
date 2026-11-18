# Guildboard

Guildboard is an open-source project for a moderated, collaborative whiteboard inside Discord.

<a id="foundation-status"></a>
## Repository status

The current foundation provides a lockfile-based workspace build, import-boundary checks, a pure configuration parser and local verification fixtures. The Activity, API and bot workspaces are scaffolds. There is no runnable Guildboard application, public website, Discord installation link or production deployment.

Follow the [development setup](docs/development.md) to build and test the foundation on Linux. It requires Git, Node.js 24 with npm, and Python 3.11 or later.

<a id="planned-system"></a>
## Planned system

The planned React/TypeScript Activity sends board requests over HTTPS/WSS. The server verifies Discord and session evidence, derives tenant scope and enforces current access policy. The API and bot route authorized board and moderation intent through the shared command service. Board state, revisions and receipts use private SQL, and assets use private persistent storage. The production target is a GoDaddy Linux VPS with Nginx HTTPS/WSS.

- [Architecture and interaction flows](docs/architecture.md)
- [Accepted T0 boundaries and foundation evidence](docs/workstreams/T0.md#t0-integration-and-handoff)
- [MVP acceptance traceability](planning/MVP-ACCEPTANCE.md)

## Contribute

- [Contribution process](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Engineering & Delivery Project](https://github.com/users/CompleteDotTech/projects/7)
- [Canonical backlog](planning/guildboard-backlog.json)
- [Verified bootstrap report](planning/BOOTSTRAP-REPORT.md)
- [Live audit artifacts](planning/audit/)

## License

Original repository content is available under the [MIT license](LICENSE). Review dependency, asset and redistribution terms before adoption.
