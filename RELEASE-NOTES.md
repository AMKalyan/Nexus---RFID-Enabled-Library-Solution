# Release Notes

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

Known limitations: see `docs/09-demo/known-limitations.md`. These include DEF-008 (latency at 50 concurrent users with one API process) and HMAC-based licences (the site holds the verification key).
