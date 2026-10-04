# Architecture Package (D2)

| Design | Document |
|---|---|
| Context, component, deployment views; layer mapping (SOP §6); technology choices | [architecture.md](architecture.md) |
| Database design: ER, roles and grants, indexing, migrations, backup and integrity | [database-design.md](database-design.md) |
| Interface design: REST API, RFID event/command contract, NCIP 2.0, SIP2, integration adapters, device/IP table | [interface-design.md](interface-design.md) |
| Security design: threats, RBAC matrix, authentication, data protection, transport | [security-design.md](security-design.md) |
| Architecture decision records | [adr/](adr/) |
| Design review minutes | [design-review.md](design-review.md) |

Related requirement documents: [use cases and acceptance criteria](../01-requirements/use-cases.md), [data dictionary](../01-requirements/data-dictionary.md), [RTM](../01-requirements/rtm.md).

## Design summary

- **Shape.** Nexus is a modular FastAPI backend with a React frontend, deployed with Docker Compose on one isolated server. PostgreSQL holds three schemas:
  - `legacy_ilms`: the existing records, read-only to the app
  - `nexus`: application data
  - `staging`: migration
- **Mocked boundaries.** Every external device and service sits behind an adapter interface with a working mock. A separate device simulator speaks the real HTTP/WebSocket event contract.
- **Circulation.** There is a single circulation service shared by the UI, NCIP and SIP2, so the rules and the audit trail are the same on every channel.
- **Integrity.** It is enforced by database grants and proven by checksums. Every change to the database is preceded by a backup.
- **Offline releases.** Releases ship as checksummed bundles of image archives with scripted install, update and rollback.
