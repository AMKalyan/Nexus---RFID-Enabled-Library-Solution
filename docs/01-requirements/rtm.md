# Requirements Traceability Matrix (RTM)

Version 0.1 (Stage 1 baseline).

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
| FR 01 | Core ILMS | Acquisition, cataloguing, serials, circulation, OPAC, barcode & spine-label workflows, reports | Cataloguing (bib/item CRUD + validation), circulation, OPAC, barcode lookup, spine-label PDF; acquisition & serials as minimal records | `services/catalog`, `services/circulation`, `api/opac` | AC 02, AC 03 | — | Planned (acquisition/serials: Partial) |
| FR 02 | Web & search | Web interface, full-text search, search engine, real-time indexing, net cataloguing, virtual bookshelf | React UI, Postgres tsvector + GIN with trigger indexing, faceted OPAC, virtual bookshelf; net cataloguing = import of bib data from file | `frontend`, `services/search` | AC 02 | — | Planned (net cataloguing: Partial) |
| FR 03 | RFID interoperability | Staff station, handheld, gate, smart card, item tags via middleware; NCIP 2.0; SIP2 adapter boundary | Device-neutral command/event middleware, device simulator, NCIP 2.0 message subset, SIP2 adapter + mock | `middleware_rfid`, `interop/ncip`, `interop/sip2`, `device-sim` | AC 02, AC 03, AC 05, AC 06, AC 07 | — | Planned (Mock) |
| FR 04 | Circulation | Check-out, check-in, renewal, due-date enquiry, patron-card personalisation, reference restrictions, member blocking, configurable fine limits, role-based rights | Circulation service with policy engine (`circ_policy`), block rules, patron card print (PDF), RBAC on circulation endpoints | `services/circulation`, `services/fines`, `core/auth` | AC 03, AC 04 | — | Planned |
| FR 05 | Tagging | Validate title/member before (re)tagging; associate tag with record; tag monitoring | Tagging workflow with pre-validation, tag history (retag retires old tag), tag status monitor | `services/tagging` | AC 02 | — | Planned |
| FR 06 | Inventory | Stock verification, shelf management, missing/misplaced items, bulk reading, audible/visible handheld confirmation | Inventory sessions, shelf map, bulk `TagsRead` processing, beep/light events + Web Audio UI | `services/inventory`, `frontend/inventory` | AC 05 | — | Planned |
| FR 07 | Security gate events | Detect unauthorised items, read security bit while LMS offline, record accession numbers, alarm/footfall/CCTV/email events | Gate event handler, security-bit offline decision, footfall counter, CCTV snapshot adapter, notification outbox | `services/gate`, `integrations/camera`, `integrations/notify` | AC 06 | — | Planned (Mock devices) |
| FR 08 | Dashboard & reports | Usage statistics; reports for tagged items, members, circulation, operator/RFID client activity, fines, gate events | Dashboard tiles/charts, filterable reports with CSV/PDF export | `services/reports`, `frontend/dashboard` | AC 08 | — | Planned |
| FR 09 | Notifications | Configurable email, SMS, print notifications per user via provider-neutral adapters | `NotificationChannel` interface, mock email/SMS/print, per-user preferences, outbox worker with retry | `integrations/notify` | AC 06 | — | Planned (Mock) |
| FR 10 | Data migration | Import ~20,000 spreadsheet records with validation, duplicates, error logs, reconciliation, rollback | Staging import, YAML validation rules, duplicate detection, dry-run, reconciliation report, batch rollback, restore | `migration/` | AC 01, AC 10 | — | Planned |
| FR 11 | Administration | User & role management, configuration, audit logs, software-version reporting, system health | Admin UI + APIs, audit viewer, `/health` and `/version`, device registry | `api/admin`, `core/audit` | AC 07 | — | Planned |
| FR 12 | Offline lifecycle | Offline activation, updates, upgrades, patches, security updates; installable update package with rollback instructions | Offline bundle (image archives + checksums + SBOM), install/update/rollback scripts, signed licence-file activation | `ops/` | AC 09 | — | Planned |

## 2. Non-functional requirements

| Req | Area | Requirement (summary) | How it is met | Evidence (planned) | Status |
|---|---|---|---|---|---|
| NFR 01 | Data integrity | Back up existing DB before integration; never modify/delete/corrupt existing records | `legacy_ilms` schema read-only via DB grants; mandatory backup before migration/update; checksum integrity tool | `ops/integrity.py` before/after report; AC 10 test | Planned |
| NFR 02 | Security & privacy | Least privilege, secure secrets, audit logging, input validation, encrypted transport | Engineering standards §2; RBAC; argon2; JWT; audit log; TLS proxy; masked logs | Security test suite, bandit/pip-audit reports | Planned |
| NFR 03 | Compatibility | Windows 11 clients, Windows Server 2022+, Ethernet, isolated-site deployment | Browser-based client; Docker Compose host; offline bundle; documented Windows Server notes | Deployment guide, environment checklist | Planned |
| NFR 04 | Licensing | Identify dependencies & licences; pin versions; document offline/redistribution restrictions | Lockfiles, SBOM, licence inventory | `docs/04-repository/sbom-and-licences.md` | Planned |
| NFR 05 | Testability | Functional, integration, performance, migration, security, regression, UAT evidence | pytest suites per type, acceptance tests per AC, perf script, UAT checklist | `docs/06-testing/` | Planned |
| NFR 06 | Maintainability | Modular adapters, external config, structured logs, versioned migrations, documented builds, rollback | Adapter interfaces, `.env` config, JSON logs, Alembic, build docs, rollback scripts | Architecture package, ops scripts | Planned |
| NFR 07 | Supportability | Diagnostics, health checks, structured logs, runbooks | `/health`, `/version`, device heartbeat, JSON logs with correlation IDs, runbook | `docs/08-operations/runbook.md` | Planned |
| NFR 08 | Documentation | Architecture, device config, IP/interface details, API docs, versions, install, admin, user, troubleshooting | Documentation packages D2, D7, D8 | `docs/` | Planned |
| NFR 09 | Delivery | Complete D0–D10; identify all remaining production work | SOP stage gates, production-completion backlog | `docs/09-demo/production-backlog.md` | Planned |

## 3. Priority acceptance scenarios

| AC | Scenario (summary) | Requirements covered | Acceptance test | Demo step | Status |
|---|---|---|---|---|---|
| AC 01 | Spreadsheet → staging, reject invalid, find duplicates, migrate valid, reconcile counts | FR 10, NFR 01 | `tests/acceptance/test_ac01_migration.py` | Demo §1 | Planned |
| AC 02 | Create/locate bib item, validate, associate mock RFID tag, show relationship | FR 01, FR 02, FR 05 | `test_ac02_tagging.py` | Demo §2 | Planned |
| AC 03 | Check out, renew, check in via mocked NCIP/SIP2 with auditable history | FR 03, FR 04, NFR 02 | `test_ac03_circulation_interop.py` | Demo §3 | Planned |
| AC 04 | Block circulation: reference item, blocked member, fine over limit | FR 04 | `test_ac04_circulation_blocks.py` | Demo §4 | Planned |
| AC 05 | Handheld mock inventories a shelf; missing/misplaced with visible + audible confirmation | FR 06, FR 03 | `test_ac05_inventory.py` | Demo §5 | Planned |
| AC 06 | Gate unauthorised-removal event, accession number, mock CCTV image, queued email | FR 07, FR 09 | `test_ac06_gate_event.py` | Demo §6 | Planned |
| AC 07 | Staff smart-card login via mock credential provider; RBAC enforced | FR 03, FR 11, NFR 02 | `test_ac07_smartcard_rbac.py` | Demo §7 | Planned |
| AC 08 | Dashboard statistics + filterable reports (tagged items, members, circulation, operators, RFID clients, gate events) | FR 08 | `test_ac08_reports.py` | Demo §8 | Planned |
| AC 09 | Install offline, apply offline update, documented rollback | FR 12, NFR 03 | `ops/tests/ac09_offline_lifecycle` | Demo §9 | Planned |
| AC 10 | Restore from backup after simulated failed migration/integration change; prove original data intact | NFR 01, FR 10 | `test_ac10_restore_integrity.py` | Demo §10 | Planned |

## 4. Mandatory deliverables

| ID | Deliverable | Location | SOP stage | Status |
|---|---|---|---|---|
| D1 | Requirements package | `docs/01-requirements/` | 1–2 | In progress |
| D2 | Architecture package | `docs/02-design/` | 2 | Planned |
| D3 | Working prototype | `backend/`, `frontend/`, `device-sim/` | 3–5 | Planned |
| D4 | Source repository | repo root, `docs/04-repository/` | 1–7 | In progress |
| D5 | Database & migration | `backend/app/db/`, `migration/`, `docs/05-data-migration/` | 3, 6 | Planned |
| D6 | Test package | `backend/tests/`, `docs/06-testing/` | 3–7 | Planned |
| D7 | Deployment package | `ops/`, `docs/07-deployment/` | Release | Planned |
| D8 | Operational documentation | `docs/08-operations/` | Release | Planned |
| D9 | Demonstration | `docs/09-demo/` | Release | Planned |

## 5. Change history

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-04 | Baseline built from the SOP during Stage 1 |
