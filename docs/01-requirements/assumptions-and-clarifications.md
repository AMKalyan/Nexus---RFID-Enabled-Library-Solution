# Assumptions and Clarification Log

Owner: Moksh · Opened: 2026-10-04 (SOP Stage 1)

No client contact is available during the candidate exercise. Each question below is answered with a documented working assumption. The assumption becomes a decision at the Stage 2 design review, and can be reopened if the evaluator clarifies.

## 1. Assumptions

| ID | Assumption | Rationale | Impact if wrong |
|---|---|---|---|
| A-01 | The "existing ILMS" is simulated by a synthetic PostgreSQL schema `legacy_ilms`, seeded with representative bibliographic, item and member records. | No existing schema or database access is provided (SOP §3 excludes production access). | The `LegacyIlmsConnector` adapter is replaced by a vendor-specific connector; the core is unchanged. |
| A-02 | "Without changing existing records" means Nexus never issues UPDATE/DELETE against legacy data. New data (tags, loans via Nexus, gate events) lives in the `nexus` schema and references legacy rows by key. | Strictest reading of §1 and NFR 01. | Write-back to a real ILMS would go through the NCIP/SIP2 adapters, which the ILMS controls. |
| A-03 | The ~20,000-record source spreadsheet is not supplied. A synthetic generator produces a realistic `.xlsx` with known injected defects (≈3% invalid, ≈2% duplicate rows). | AC 01 refers to a "supplied" spreadsheet that is not attached. | The importer is driven by a column-mapping YAML; a real file needs only a new mapping. |
| A-04 | Source spreadsheet columns: accession_no, barcode, title, author, isbn, publisher, year, edition, subjects, call_no, shelf_location, item_type (lending/reference), price, acquired_on. | Common Indian academic library export layout. | Mapping YAML is updated; validation rules are reused. |
| A-05 | RFID tags follow ISO 28560-style data model concepts (item ID + security/AFI bit), simulated as EPC strings. Tag encoding is not certified. | §3 forbids certification claims without evidence. | A vendor SDK adapter implements the same `WriteTag`/`ReadTags` commands. |
| A-06 | NCIP 2.0 support is a documented subset (LookupUser, CheckOutItem, CheckInItem, RenewItem) over HTTP/XML. SIP2 is an adapter boundary with a mock handler for messages 09/10, 11/12, 23/24, 29/30. | FR 03 asks for NCIP 2.0 support and an SIP2 *boundary*. | Remaining messages are listed in the production backlog. |
| A-07 | Email, SMS and print are mocked: messages are written to an outbox table and folder, and shown in the UI. No real provider is contacted. | §3: no live services. | Real SMTP/SMS-gateway adapters implement `NotificationChannel`. |
| A-08 | CCTV integration returns a synthetic image from a `CameraProvider` mock when a gate alarm fires. | No camera or VMS API available. | An ONVIF/VMS adapter implements `CameraProvider`. |
| A-09 | Smart cards are identified by a UID read by a mock reader. The UID maps to a staff user through a `CredentialProvider` mock. A PIN is optional and disabled for the demo. | AC 07. | A real PC/SC or vendor reader adapter replaces the mock. |
| A-10 | The deployment target is a single on-premises server (Windows Server 2022 running Docker with Linux containers, or a Linux VM) on an isolated Ethernet LAN; clients are Windows 11 browsers. | NFR 03 + offline requirement. | A native Windows-service packaging path is listed in the backlog. |
| A-11 | Fines accrue per overdue day at a rate set in each member category's circulation policy. The "fine limit" is a per-category threshold above which check-out is blocked. | FR 04, AC 04. | Policy table already parameterised. |
| A-12 | Offline activation uses an HMAC-signed licence file that is validated locally. A real PKI/licensing server is out of scope. | FR 12; no licensing service available. | A PKI-signed licence replaces the HMAC check. |
| A-13 | The prototype supports English only and a single library branch. | Time-boxed exercise. | Multi-branch and i18n go into the backlog. |
| A-14 | "Real-time indexing" means that catalogue changes are searchable immediately after commit, via trigger-maintained Postgres full-text vectors. | FR 02. | An external search engine (e.g. OpenSearch) can be added behind the `search` service. |

## 2. Clarification log

| ID | Question | Raised | Working answer | Status |
|---|---|---|---|---|
| Q-01 | SOP §7 numbers deliverables D1–D9, while §9 uses D0–D10 for delivery stages. Are these separate sequences? | 2026-10-04 | Yes. "Dx" in §9 is read as a delivery *milestone/day*, and D1–D9 in §7 as *deliverables*. This repository uses "Stage N" for §9 and "D1–D9" for deliverables only. | Assumed |
| Q-02 | §9 defines stages up to D8. What covers D9–D10? | 2026-10-04 | Treated as "Release & handover": deployment package (D7), operational docs (D8) and demonstration (D9), closed by the `v1.0.0-eval` tag. | Assumed |
| Q-03 | Is a specific existing ILMS product (e.g. Koha, SOUL, LibSys) assumed? | 2026-10-04 | No. Integration is through the product-neutral `LegacyIlmsConnector` plus NCIP/SIP2 boundaries (A-01). | Assumed |
| Q-04 | Which roles hold which circulation rights? | 2026-10-04 | Admin: all. Librarian: catalogue, tagging, circulation, inventory, reports. Circulation Clerk: circulation and member lookup. Auditor: read-only reports and audit log. Patron: own account and OPAC. Detailed in the Stage 2 RBAC matrix. | Assumed |
| Q-05 | Must the SIP2 adapter listen on a real TCP socket? | 2026-10-04 | A parser plus a toggleable socket handler, tested in-process; the socket is disabled by default. | Assumed |
| Q-06 | Is an issue tracker on a hosted platform required? | 2026-10-04 | The repository is local for the exercise. The tracker is kept in `docs/00-project-control/issue-tracker.md` and can be imported into GitHub/GitLab Issues when a remote is created. | Assumed |
| Q-07 | Does "read the security bit while the LMS is offline" require gate hardware logic? | 2026-10-04 | The gate decision is based only on the tag's security bit (set on check-in, cleared on check-out). The gate simulator keeps working and queues events while the API is unreachable, then replays them. | Assumed |
| Q-08 | What performance targets apply? | 2026-10-04 | No targets given. Prototype goals: 20k-row migration < 5 min; search p95 < 500 ms and check-out p95 < 300 ms on 50 concurrent users, measured on the demo host. Reported as observations, not certified figures. | Assumed |
