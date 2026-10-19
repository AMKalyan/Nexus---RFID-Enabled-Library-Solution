# Release Notes

## 1.0.3 (2026-10-19)

Feature release for public demonstrations. No schema change (revision `0004`).

- **Demo sign-in details on the login page** (off by default). With `DEMO_PUBLIC_ACCOUNTS=true` and a `DEMO_PUBLIC_PASSWORD`, the login page lists the Librarian, Circulation Clerk, Auditor and Patron `B00001` accounts with a **Use** button, served by `GET /api/v1/auth/demo-accounts`. Admin is never listed and keeps a random password.
- **New guide:** [hosting options](docs/07-deployment/hosting-options.md) for a public demonstration, explaining why Netlify or Vercel alone cannot host the API.
- The offline bundle for 1.0.3 was not rehearsed separately: the install, update and rollback scripts are unchanged since 1.0.2.

## 1.0.2 (2026-10-19)

Security and robustness release. No schema change (revision `0004`).

- **Client address cannot be spoofed (DEF-015).** nginx now overwrites `X-Forwarded-For`, so sign-in rate limits hold and the audit log records the real client address.
- **`/api/v1/health` returns 503 when a check fails (DEF-016).** The Docker health check and the update's automatic rollback now see a database failure.
- **The System health screen shows failing checks again (DEF-024).** It reads the 503 report instead of treating it as an error.
- **SIP2 listener (DEF-017):** an empty `SIP2_ALLOWED_HOSTS` refuses every connection.
- **SIP2 Patron Status (DEF-023)** carries initials instead of the member's full name.
- **Containers restart after a host or Docker restart (DEF-018).**
- **`ops/restore.sh` restarts the services when a restore fails (DEF-019).**
- **Installation (DEF-020):** `--licence-key-file` / `-LicenceKeyFile` installs a pre-issued licence with the key it was signed with. A newly installed licence takes effect immediately.
- **Migration commit reconciles the counts before it starts (DEF-021).** It returns `BATCH_NOT_BALANCED` when they don't balance.
- **Device simulator (DEF-022):** replays keep events refused with 401, 403 or 429.
- The 1.0.1 build note said administrators could "publish" a maintenance notice. The `maintenance_notice` setting is stored and returned by the settings API, but no screen displays it yet (production backlog).

Update from 1.0.1 with `ops/update.ps1 nexus-1.0.2.zip` (or `update.sh`); roll back with `ops/rollback.ps1`.

## 1.0.1 (2026-10-08)

Maintenance release used to prove the offline update and rollback path (AC 09).

- `/api/v1/version` reports `build_notes`.
- New administrator setting `maintenance_notice` (migration `0004`). The downgrade removes only this setting and the 1.0.1 release record.
- Update with `ops/update.ps1 nexus-1.0.1.zip` (or `update.sh`); roll back with `ops/rollback.ps1`.

Schema revision: `0004`.

## 1.0.0 (2026-10-08)

First release of the Nexus RFID library solution prototype. All acceptance scenarios AC 01–AC 10 are demonstrable against mocked devices and services.

- **Core library functions:** cataloguing, members, circulation with policy rules and fines, OPAC with full-text search and virtual bookshelf, dashboard and reports with CSV/PDF export, administration.
- **RFID middleware:** device event ingest, command bus, live feeds. Tagging, handheld inventory, security gate with mock CCTV and notifications, staff smart-card sign-in. Device simulator.
- **Interoperability:** NCIP 2.0 subset and SIP2 boundary (mock-tested; no conformance claimed).
- **Migration:** staged spreadsheet import with validation, duplicate detection, reconciliation and batch rollback.
- **Operations:**
  - verified backup and restore
  - legacy integrity fingerprints
  - offline bundle install, update with automatic rollback, and manual rollback
  - licence-file activation

Schema revision: `0003`.

Known limitations: see [`docs/09-limitations-and-backlog/known-limitations.md`](docs/09-limitations-and-backlog/known-limitations.md). These include DEF-008 (latency at 50 concurrent users with one API process) and HMAC-based licences (the site holds the verification key).
