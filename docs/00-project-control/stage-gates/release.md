# Release Record: Release and Handover (D7–D10)

| Field | Value |
|---|---|
| SOP reference | Deliverables D7–D10 (no SOP §9 stage; recorded as "release and handover" in the clarification log) |
| Branch | `release/1.0.0` |
| Release | 1.0.2 (tag `v1.0.2`; evaluation release tag `v1.0.0-eval`) |
| Date | 2026-10-19 |
| Outcome | Released |

## Deliverables

| Deliverable | Output | Location | Done |
|---|---|---|---|
| D4 Source repository | Branch strategy; SBOM and licence inventory generated from the shipped images | [`docs/04-repository/`](../../04-repository/) | ☑ |
| D7 Deployment package | Offline bundles with checksums and SBOM; install, update, rollback, backup and restore scripts (PowerShell and shell); environment checklist; installation, configuration, backup/restore and update/rollback guides | `ops/`, [`docs/07-deployment/`](../../07-deployment/) | ☑ |
| D8 Operational documentation | Administrator, user, API, device-configuration and training guides; troubleshooting runbook; `openapi.json` | [`docs/08-operations/`](../../08-operations/) | ☑ |
| D9 Demonstration | Known limitations and production backlog. The demo script and presentation outline are kept outside the repository | [`docs/09-limitations-and-backlog/`](../../09-limitations-and-backlog/) | ☑ |

## Release 1.0.2

Writing the deployment and operations guides meant checking every documented behaviour against the code. That review found ten defects (DEF-015 to DEF-024). All were fixed test-first on `fix/` branches and released as 1.0.2:

| Defect | Severity | Fix |
|---|---|---|
| DEF-015 | S2 | nginx overwrites `X-Forwarded-For`: rate limits hold and the audit log records the real client address |
| DEF-016 | S2 | `/health` returns 503 when a check fails, so health checks and the update roll-back see a database failure |
| DEF-017 | S2 | An empty SIP2 allow-list refuses every connection |
| DEF-018 | S3 | `restart: unless-stopped` on all services |
| DEF-019 | S3 | `restore.sh` restarts the services when a restore fails |
| DEF-020 | S3 | A pre-issued licence can be installed with its key |
| DEF-021 | S3 | Migration commit reconciles the counts before it starts |
| DEF-022 | S3 | The simulator keeps events refused for retryable reasons |
| DEF-023 | S3 | SIP2 Patron Status carries initials, not the full name |
| DEF-024 | S3 | The System health screen shows failing checks (regression from DEF-016, found in review) |

## Evidence

- **Run of record** (`bash ops/ci-local.sh`, exit 0):
  - backend: 247 tests, 92% line coverage
  - acceptance: 85
  - simulator: 8
  - migration tools: 5
  - frontend: 11
  - tooling lint: clean

  The traceability matrix covers 260 cases, all passing ([test results](../../06-testing/test-results.md)).
- **1.0.2 bundle test:** builds, verifies, and refuses a corrupted archive.
- **1.0.2 rehearsal** ([AC 09 record](../../../ops/tests/ac09_offline_lifecycle.md)):
  - update from 1.0.1 to 1.0.2, then roll back: legacy data IDENTICAL
  - fresh 1.0.2 install with a pre-issued licence: licence valid
  - 19 of 19 security smoke checks pass
  - `/health` returns 503 with the database stopped, and 200 after
- **Repository checks:** a single author and no tool references in any commit; no secrets, `.env` files or tool files tracked.

## Open items

- **DEF-008:** latency at 50 users with one API process. Known limitation; backlog NX-063.
- **DEF-012:** one unexplained test stall. Monitoring; the test database fails fast on lock waits; backlog NX-064.
- **NFR 03 is partial:** Windows Server 2022 was not rehearsed.

Everything else open is listed in [known limitations](../../09-limitations-and-backlog/known-limitations.md) and the [production backlog](../../09-limitations-and-backlog/production-backlog.md).
