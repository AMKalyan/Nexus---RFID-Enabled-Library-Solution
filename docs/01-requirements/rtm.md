# Requirements Traceability Matrix (RTM)

Version 0.5 (Stage 5 RFID middleware and integrations).

The RTM maps every SOP requirement to features, modules, tests and evidence. It is updated at every stage gate. Status values:

- **Planned**: accepted into scope, not yet built
- **In progress**: being built
- **Done**: implemented, with passing test evidence
- **Mock**: implemented against a documented adapter boundary with a working mock, because no real device or service is available
- **Partial**: a working subset exists; the rest is in the production backlog
- **Backlog**: out of the candidate exercise; recorded in the production-completion backlog

Module and test columns are filled in from Stage 2 (design) and Stage 7 (verification) onwards.

## 1. Functional requirements

| Req | Area | Requirement (summary) | Planned features | Module(s) | Acceptance link | Test ID(s) | Status |
|---|---|---|---|---|---|---|---|
| FR 01 | Core ILMS | Acquisition, cataloguing, serials, circulation, OPAC, barcode & spine-label workflows, reports | Cataloguing (bib/item CRUD + validation), circulation, OPAC, barcode lookup, spine-label PDF; acquisition & serials as minimal records | `services/catalog`, `services/circulation`, `api/opac` | AC 02, AC 03 | `test_catalog.py` (11), `test_members.py::test_fr04_patron_card_pdf` | Partial: cataloguing, circulation, OPAC, barcode, spine labels Done; acquisition captured as price/date only; serials Backlog |
| FR 02 | Web & search | Web interface, full-text search, search engine, real-time indexing, net cataloguing, virtual bookshelf | React UI, Postgres tsvector + GIN with trigger indexing, faceted OPAC, virtual bookshelf; net cataloguing = import of bib data from file | `frontend`, `services/search` | AC 02 | `test_opac.py` (9), `test_fr02_search_vector_maintained_by_trigger` | Done: web UI, full-text search, real-time indexing and virtual bookshelf; net cataloguing as bibliographic import through the migration importer (`test_ac01_migration.py`), as scoped in ADR-0004 |
| FR 03 | RFID interoperability | Staff station, handheld, gate, smart card, item tags via middleware; NCIP 2.0; SIP2 adapter boundary | Device-neutral command/event middleware, device simulator, NCIP 2.0 message subset, SIP2 adapter + mock | `middleware_rfid`, `interop/ncip`, `interop/sip2`, `device-sim` | AC 02, AC 03, AC 05, AC 06, AC 07 | `test_device_ingest.py` (10), `test_commands.py` (5), `test_live.py` (8), `test_ac03_*` (14), `test_sip2.py` (3), `device-sim/test_sim.py` (6) | Mock: device middleware, simulator, NCIP subset (4 messages) and SIP2 boundary (5 message pairs) Done; vendor SDKs and conformance testing in backlog |
| FR 04 | Circulation | Check-out, check-in, renewal, due-date enquiry, patron-card personalisation, reference restrictions, member blocking, configurable fine limits, role-based rights | Circulation service with policy engine (`circ_policy`), block rules, patron card print (PDF), RBAC on circulation endpoints | `services/circulation`, `services/fines`, `core/auth` | AC 03, AC 04 | `test_circulation.py` (11), `test_members.py` (8), `test_policy.py` (10), `test_ac04_*` (5) | Done |
| FR 05 | Tagging | Validate title/member before (re)tagging; associate tag with record; tag monitoring | Tagging workflow with pre-validation, tag history (retag retires old tag), tag status monitor | `services/tagging` | AC 02 | `test_ac02_tagging.py` (11) | Done |
| FR 06 | Inventory | Stock verification, shelf management, missing/misplaced items, bulk reading, audible/visible handheld confirmation | Inventory sessions, shelf map, bulk `TagsRead` processing, beep/light events + Web Audio UI | `services/inventory`, `frontend/inventory` | AC 05 | `test_ac05_inventory.py` (8) | Done |
| FR 07 | Security gate events | Detect unauthorised items, read security bit while LMS offline, record accession numbers, alarm/footfall/CCTV/email events | Gate event handler, security-bit offline decision, footfall counter, CCTV snapshot adapter, notification outbox | `services/gate`, `integrations/camera`, `integrations/notify` | AC 06 | `test_ac06_gate_event.py` (8), UJ-08..10 | Mock: gate, camera and offline replay Done against simulated devices |
| FR 08 | Dashboard & reports | Usage statistics; reports for tagged items, members, circulation, operator/RFID client activity, fines, gate events | Dashboard tiles/charts, filterable reports with CSV/PDF export | `services/reports`, `frontend/dashboard` | AC 08 | `test_ac08_reports.py` (14) | Done |
| FR 09 | Notifications | Configurable email, SMS, print notifications per user via provider-neutral adapters | `NotificationChannel` interface, mock email/SMS/print, per-user preferences, outbox worker with retry | `integrations/notify` | AC 06 | `test_outbox.py` (6), `test_ac06_*` | Mock: outbox, retrying worker, per-user preferences Done; real SMTP/SMS gateways in backlog |
| FR 10 | Data migration | Import ~20,000 spreadsheet records with validation, duplicates, error logs, reconciliation, rollback | Staging import, YAML validation rules, duplicate detection, dry-run, reconciliation report, batch rollback, restore | `migration/`, `services/migration/`, `nexus_ops/` | AC 01, AC 10 | `test_ac01_migration.py` (9), `test_migration_validate.py` (5), `migration/test_gen_sample.py` (5), `test_ac10_restore_integrity.py` (5) | Done |
| FR 11 | Administration | User & role management, configuration, audit logs, software-version reporting, system health | Admin UI + APIs, audit viewer, `/health` and `/version`, device registry | `api/admin`, `core/audit` | AC 07 | `test_admin.py` (11), `test_nfr07_*` | Done |
| FR 12 | Offline lifecycle | Offline activation, updates, upgrades, patches, security updates; installable update package with rollback instructions | Offline bundle (image archives + checksums + SBOM), install/update/rollback scripts, signed licence-file activation | `ops/` | AC 09 | — | Planned |

## 2. Non-functional requirements

| Req | Area | Requirement (summary) | How it is met | Evidence (planned) | Status |
|---|---|---|---|---|---|
| NFR 01 | Data integrity | Back up existing DB before integration; never modify/delete/corrupt existing records | `legacy_ilms` schema read-only via DB grants; mandatory backup before migration/update; checksum integrity tool | `ops/integrity.py` before/after report; AC 10 test; **Stage 3:** `test_nfr01_app_role_cannot_modify_legacy` (4 cases), `test_nfr01_mirror_copies_without_touching_legacy`; **Stage 6:** verified pre-commit backup, legacy fingerprints before and after every commit, `test_ac10_restore_integrity.py` (5), `docs/05-data-migration/restore-and-integrity-report.md` | Done |
| NFR 02 | Security & privacy | Least privilege, secure secrets, audit logging, input validation, encrypted transport | Engineering standards §2; RBAC; argon2; JWT; audit log; TLS proxy; masked logs | Security test suite, bandit/pip-audit reports; **Stage 3:** 18 auth, token, audit, masking and error tests (see `docs/06-testing/baseline-test-report.md`) | In progress |
| NFR 03 | Compatibility | Windows 11 clients, Windows Server 2022+, Ethernet, isolated-site deployment | Browser-based client; Docker Compose host; offline bundle; documented Windows Server notes | Deployment guide, environment checklist | Planned |
| NFR 04 | Licensing | Identify dependencies & licences; pin versions; document offline/redistribution restrictions | Lockfiles, SBOM, licence inventory | `docs/04-repository/sbom-and-licences.md`; **Stage 3:** exact pins in `requirements*.txt` and `package-lock.json`; pip-audit and npm audit clean | In progress |
| NFR 05 | Testability | Functional, integration, performance, migration, security, regression, UAT evidence | pytest suites per type, acceptance tests per AC, perf script, UAT checklist | `docs/06-testing/` | Planned |
| NFR 06 | Maintainability | Modular adapters, external config, structured logs, versioned migrations, documented builds, rollback | Adapter interfaces, `.env` config, JSON logs, Alembic, build docs, rollback scripts | Architecture package, ops scripts; **Stage 3:** adapter registry, `.env` configuration, JSON logs, Alembic 0001–0002 with downgrade, `test_adr0003_no_raw_sql_in_application_code` | In progress |
| NFR 07 | Supportability | Diagnostics, health checks, structured logs, runbooks | `/health`, `/version`, device heartbeat, JSON logs with correlation IDs, runbook | `docs/08-operations/runbook.md`; **Stage 3:** `/api/v1/health` (database check), `/api/v1/version` (migration revision), `test_nfr07_*` | In progress |
| NFR 08 | Documentation | Architecture, device config, IP/interface details, API docs, versions, install, admin, user, troubleshooting | Documentation packages D2, D7, D8 | `docs/` | Planned |
| NFR 09 | Delivery | Complete D0–D10; identify all remaining production work | SOP stage gates, production-completion backlog | `docs/09-demo/production-backlog.md` | Planned |

## 3. Priority acceptance scenarios

| AC | Scenario (summary) | Requirements covered | Acceptance test | Demo step | Status |
|---|---|---|---|---|---|
| AC 01 | Spreadsheet → staging, reject invalid, find duplicates, migrate valid, reconcile counts | FR 10, NFR 01 | `tests/acceptance/test_ac01_migration.py` | Demo §1 | Done |
| AC 02 | Create/locate bib item, validate, associate mock RFID tag, show relationship | FR 01, FR 02, FR 05 | `test_ac02_tagging.py` | Demo §2 | Done |
| AC 03 | Check out, renew, check in via mocked NCIP/SIP2 with auditable history | FR 03, FR 04, NFR 02 | `test_ac03_circulation_interop.py` | Demo §3 | Done |
| AC 04 | Block circulation: reference item, blocked member, fine over limit | FR 04 | `test_ac04_circulation_blocks.py` | Demo §4 | Done |
| AC 05 | Handheld mock inventories a shelf; missing/misplaced with visible + audible confirmation | FR 06, FR 03 | `test_ac05_inventory.py` | Demo §5 | Done |
| AC 06 | Gate unauthorised-removal event, accession number, mock CCTV image, queued email | FR 07, FR 09 | `test_ac06_gate_event.py` | Demo §6 | Done |
| AC 07 | Staff smart-card login via mock credential provider; RBAC enforced | FR 03, FR 11, NFR 02 | `test_ac07_smartcard_rbac.py` | Demo §7 | Done |
| AC 08 | Dashboard statistics + filterable reports (tagged items, members, circulation, operators, RFID clients, gate events) | FR 08 | `test_ac08_reports.py` | Demo §8 | Done |
| AC 09 | Install offline, apply offline update, documented rollback | FR 12, NFR 03 | `ops/tests/ac09_offline_lifecycle` | Demo §9 | Planned |
| AC 10 | Restore from backup after simulated failed migration/integration change; prove original data intact | NFR 01, FR 10 | `test_ac10_restore_integrity.py` | Demo §10 | Done |

## 4. Mandatory deliverables

| ID | Deliverable | Location | SOP stage | Status |
|---|---|---|---|---|
| D1 | Requirements package | `docs/01-requirements/` | 1–2 | Done |
| D2 | Architecture package | `docs/02-design/` | 2 | Done |
| D3 | Working prototype | `backend/`, `frontend/`, `device-sim/` | 3–5 | In progress |
| D4 | Source repository | repo root, `docs/04-repository/` | 1–7 | In progress |
| D5 | Database & migration | `backend/app/db/`, `migration/`, `docs/05-data-migration/` | 3, 6 | Done |
| D6 | Test package | `backend/tests/`, `docs/06-testing/` | 3–7 | In progress |
| D7 | Deployment package | `ops/`, `docs/07-deployment/` | Release | Planned |
| D8 | Operational documentation | `docs/08-operations/` | Release | Planned |
| D9 | Demonstration | `docs/09-demo/` | Release | Planned |

## 5. Change history

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-04 | Baseline built from the SOP during Stage 1 |
| 0.2 | 2026-10-04 | Design complete: module mapping confirmed; D1 and D2 done; acquisition/serials/net-cataloguing scope notes per ADR-0004 |
| 0.3 | 2026-10-05 | Foundation build: NFR 01, 02, 04, 06, 07 in progress with test evidence; D3–D6 in progress |
| 0.4 | 2026-10-07 | Core library functions: FR 04, FR 08, AC 04, AC 08 done; FR 01 and FR 02 partial with scope notes; FR 11 in progress |
| 0.5 | 2026-10-07 | RFID middleware and integrations: FR 05, FR 06, FR 11, AC 02, AC 03, AC 05, AC 06, AC 07 done; FR 03, FR 07, FR 09 done against mocks |
| 0.6 | 2026-10-07 | Migration and resilience: FR 02, FR 10, NFR 01, AC 01, AC 10 done; D5 done |
