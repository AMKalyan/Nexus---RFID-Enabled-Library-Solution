# Production-Completion Backlog

Work remaining between the 1.0.2 prototype and a production deployment (SOP NFR 09). Each item removes a limitation listed in [known-limitations.md](known-limitations.md).

New items are numbered NX-101 onwards so they do not clash with the [issue tracker](../00-project-control/issue-tracker.md) (NX-001 to NX-070). NX-063 and NX-064 are existing tracker items and keep their numbers.

## Scales

| Priority | Meaning |
|---|---|
| P1 | Needed before a production go-live |
| P2 | Needed for the full SOP scope or shortly after go-live |
| P3 | Improvement; schedule when demand appears |

| Size | Rough effort for one developer, including tests and documentation |
|---|---|
| S | Up to 1 week |
| M | 1 to 3 weeks |
| L | 3 to 6 weeks |
| XL | More than 6 weeks |

Sizes are planning estimates, not commitments. Items that depend on a vendor (SDKs, gateways, the site's ILMS) also depend on access to that vendor's documentation and test equipment.

## Summary

| ID | Item | Area | Priority | Size | Source |
|---|---|---|---|---|---|
| [NX-063](#nx-063) | Scale the API beyond one process | Performance | P1 | L | DEF-008 |
| [NX-064](#nx-064) | Root cause of the intermittent test stall | Testability | P2 | S | DEF-012 |
| [NX-101](#nx-101) | Vendor SDK adapters for RFID readers, handhelds and gates | RFID | P1 | L | FR 03 Mock |
| [NX-102](#nx-102) | CCTV / VMS adapter | Integration | P2 | M | FR 07 Mock |
| [NX-103](#nx-103) | SMS gateway adapter | Integration | P2 | S | FR 09 Mock |
| [NX-104](#nx-104) | SMTP email adapter | Integration | P1 | S | FR 09 Mock |
| [NX-105](#nx-105) | Print adapter for site printers | Integration | P3 | S | FR 09 Mock |
| [NX-106](#nx-106) | Real smart-card credential provider | Security | P1 | M | AC 07 mock provider |
| [NX-107](#nx-107) | Connector for the site's legacy ILMS | Integration | P1 | L | ADR-0005 |
| [NX-108](#nx-108) | Legacy ILMS re-sync job | Integration | P1 | M | ADR-0005 |
| [NX-109](#nx-109) | Full NCIP 2.0 coverage and conformance testing | Interoperability | P2 | L | FR 03 |
| [NX-110](#nx-110) | Full SIP2 coverage, conformance testing and transport security | Interoperability | P2 | M | FR 03 |
| [NX-111](#nx-111) | NCIP agency administration | Administration | P1 | S | Demo preparation |
| [NX-112](#nx-112) | ISO 28560 tag encoding | RFID | P1 | M | Assumption A-05 |
| [NX-113](#nx-113) | Acquisition module | Core ILMS | P2 | L | FR 01 Partial |
| [NX-114](#nx-114) | Serials module | Core ILMS | P2 | L | FR 01 Partial |
| [NX-115](#nx-115) | Multi-branch support | Core ILMS | P3 | L | Assumption A-13 |
| [NX-116](#nx-116) | Internationalisation (i18n) | User interface | P3 | M | Assumption A-13 |
| [NX-117](#nx-117) | High availability and database replication | Operations | P2 | L | Excluded work |
| [NX-118](#nx-118) | Native Windows service packaging | Operations | P3 | M | NFR 03 Partial |
| [NX-119](#nx-119) | Asymmetric (PKI) licence signatures | Operations | P2 | S | FR 12 design choice |
| [NX-120](#nx-120) | SSO and LDAP / Active Directory sign-in | Security | P2 | M | NFR 02 |
| [NX-121](#nx-121) | Independent penetration test | Security | P1 | M | NFR 02 |
| [NX-122](#nx-122) | Accessibility audit and fixes | User interface | P2 | M | — |
| [NX-123](#nx-123) | Data retention policy and purge jobs | Data protection | P1 | M | NFR 02 |
| [NX-124](#nx-124) | Authenticate device requests before body validation | Security | P3 | S | Security checks §5 |
| [NX-125](#nx-125) | Site TLS certificate management | Security | P1 | S | Self-signed certificate |
| [NX-126](#nx-126) | Verification on Windows Server 2022 | Compatibility | P1 | S | NFR 03 Partial |
| [NX-127](#nx-127) | Rehearse the remaining offline-lifecycle paths | Operations | P2 | S | AC 09 rehearsal |
| [NX-128](#nx-128) | Display the maintenance notice and UI banner | User interface | P3 | S | Release 1.0.2 review |
| [NX-129](#nx-129) | Show a failing health check on the System health screen | Operations | Done | S | Fixed in 1.0.2 (DEF-024) |

P1 total: 12 items. A suggested order for them is in [Sequencing](#sequencing).

## Items

| ID | Item | Priority / size | Scope and done criteria |
|---|---|---|---|
| <a id="nx-063"></a>NX-063 | Scale the API beyond one process | P1 / L | Move the command bus, live hub, smart-card challenges and rate-limit counters from process memory to shared storage (PostgreSQL LISTEN/NOTIFY and tables). Run the outbox worker and SIP2 listener as their own service. Then run several API workers. Done when the 50-user run of `perf_async.py` meets Q-08 (search p95 < 500 ms, check-out p95 < 300 ms) with no errors and all suites pass with more than one worker. The 4-worker diagnostic (162 req/s, search p95 400 ms) shows the expected gain ([performance results](../06-testing/performance-results.md)). Existing tracker item |
| <a id="nx-064"></a>NX-064 | Root cause of the intermittent test stall | P2 / S | One run stalled for about 15 minutes in `POST /api/v1/bibs` (DEF-012). Keep the 30 s `lock_timeout`, capture `pg_stat_activity` automatically when a test exceeds a time budget, and close the defect with a root cause or after an agreed number of clean runs. Existing tracker item |
| <a id="nx-101"></a>NX-101 | Vendor SDK adapters for RFID readers, handhelds and gates | P1 / L | A device bridge per chosen vendor that turns SDK callbacks into the documented event envelope and executes the command set (`WriteTag`, `ReadTags`, beep and light). Covers staff station, handheld and gate, including the gate's own security-bit decision while Nexus is unreachable. Done when the AC 02, AC 05 and AC 06 scenarios pass on real hardware |
| <a id="nx-102"></a>NX-102 | CCTV / VMS adapter | P2 / M | A `CameraProvider` that fetches the frame or clip reference for the alarm time from the site's VMS. Keep the current rule that a camera fault never loses the alarm |
| <a id="nx-103"></a>NX-103 | SMS gateway adapter | P2 / S | A `NotificationChannel` for the site's SMS gateway with delivery receipts, retries through the existing outbox, and masked numbers in logs |
| <a id="nx-104"></a>NX-104 | SMTP email adapter | P1 / S | A `NotificationChannel` for SMTP with TLS and authentication from `.env`. Gate alerts and overdue notices go through the existing outbox and retry policy |
| <a id="nx-105"></a>NX-105 | Print adapter for site printers | P3 / S | Send print notifications, receipts, spine labels and patron cards to network printers (device `PRN-01` in the registry) instead of PDF download only |
| <a id="nx-106"></a>NX-106 | Real smart-card credential provider | P1 / M | Replace the UID look-up with the institution's card authentication (for example, a cryptographic challenge to the card, or a PIN at the reader), plus card revocation. Keep the reader-bound, single-use challenge already in place |
| <a id="nx-107"></a>NX-107 | Connector for the site's legacy ILMS | P1 / L | Implement `LegacyIlmsConnector` for the ILMS product in use, read-only, through its API or a read-only database role. Re-run the AC 10 integrity proof against the real source |
| <a id="nx-108"></a>NX-108 | Legacy ILMS re-sync job | P1 / M | Scheduled, audited job that brings new and changed legacy records into the `nexus` mirror without writing to the source ([ADR-0005](../02-design/adr/0005-legacy-integration.md)). Reports drift and conflicts |
| <a id="nx-109"></a>NX-109 | Full NCIP 2.0 coverage and conformance testing | P2 / L | Add the NCIP services the site's partners need beyond LookupUser, CheckOutItem, RenewItem and CheckInItem (for example LookupItem, RequestItem, CancelRequestItem, AcceptItem). Test against partner systems or an NCIP test harness. A conformance statement is made only with that evidence (SOP §3) |
| <a id="nx-110"></a>NX-110 | Full SIP2 coverage, conformance testing and transport security | P2 / M | Add the SIP2 messages the self-check vendor requires beyond 99, 23, 11, 29 and 09 (for example 63/64 patron information, 17/18 item information, 93/94 login). Protect the transport (TLS wrapper or VPN between kiosk and server) and test with the vendor's kiosk |
| <a id="nx-111"></a>NX-111 | NCIP agency administration | P1 / S | Admin API and Administration screen to register NCIP agencies, show their key once, rotate and revoke keys, with audit entries. Today an agency can be created only directly in the database |
| <a id="nx-112"></a>NX-112 | ISO 28560 tag encoding | P1 / M | Encode and decode tags to the ISO 28560 data model chosen by the site (part 2 or part 3), including AFI or EAS security handling, through the vendor adapter (NX-101). Verify with the tag supplier; no certification is claimed without it |
| <a id="nx-113"></a>NX-113 | Acquisition module | P2 / L | Orders, vendors, budgets, receiving and invoicing, linked to cataloguing. Today only price and acquisition date are recorded on the item |
| <a id="nx-114"></a>NX-114 | Serials module | P2 / L | Subscriptions, prediction patterns, issue check-in and claims, with items created on receipt |
| <a id="nx-115"></a>NX-115 | Multi-branch support | P3 / L | Branch on shelves, devices, staff and policies; transfers between branches; branch filters on the dashboard and reports |
| <a id="nx-116"></a>NX-116 | Internationalisation (i18n) | P3 / M | Externalise UI strings and refusal texts, locale-aware dates and currency, and at least one additional language |
| <a id="nx-117"></a>NX-117 | High availability and database replication | P2 / L | PostgreSQL streaming replication with a documented failover, more than one API instance behind nginx (needs NX-063), and backup shipping to a second store |
| <a id="nx-118"></a>NX-118 | Native Windows service packaging | P3 / M | An installer that runs Nexus as Windows services without Linux containers, for sites that cannot run Docker on Windows Server ([environment checklist](../07-deployment/environment-checklist.md)) |
| <a id="nx-119"></a>NX-119 | Asymmetric (PKI) licence signatures | P2 / S | Sign licence files with a vendor private key (for example Ed25519) and ship only the public key, so a site cannot issue its own licence. `ops/licence.py` and the API licence check change; existing HMAC licences are migrated |
| <a id="nx-120"></a>NX-120 | SSO and LDAP / Active Directory sign-in | P2 / M | Staff sign-in through the institution's directory (LDAP or Active Directory) or an SSO provider (SAML or OpenID Connect), with role mapping from directory groups. Local accounts stay for break-glass access |
| <a id="nx-121"></a>NX-121 | Independent penetration test | P1 / M | External test of the deployed stack (web, API, device ingest, NCIP, SIP2) after NX-125; findings triaged in the defect log and retested |
| <a id="nx-122"></a>NX-122 | Accessibility audit and fixes | P2 / M | Audit the staff UI and OPAC against WCAG 2.2 AA (keyboard use, contrast, screen-reader labels, alternatives to audio cues) and fix the findings |
| <a id="nx-123"></a>NX-123 | Data retention policy and purge jobs | P1 / M | Agree retention periods with the institution for audit entries, gate events and CCTV images, loan history, outbox messages and backups. Implement scheduled, audited purge or anonymisation. The audit log stays append-only for the application role, so purging runs under a separate role |
| <a id="nx-124"></a>NX-124 | Authenticate device requests before body validation | P3 / S | Check `X-Device-Key` before the event body is validated, so an unauthenticated caller always gets 401 rather than 422 (observation in [security checks §5](../06-testing/security-checks.md#5-defects-and-observations)). Add a test for the order |
| <a id="nx-125"></a>NX-125 | Site TLS certificate management | P1 / S | Install procedure for a certificate from the site's PKI, expiry monitoring on the System health screen, and a renewal runbook. The self-signed certificate stays for demonstrations only |
| <a id="nx-126"></a>NX-126 | Verification on Windows Server 2022 | P1 / S | Repeat the AC 09 offline rehearsal and the UAT checklist on Windows Server 2022 with Docker (Linux containers), and record the evidence to close NFR 03 |
| <a id="nx-127"></a>NX-127 | Rehearse the remaining offline-lifecycle paths | P2 / S | Build a deliberately unhealthy release and record the automatic rollback by `update.ps1`; force a failed schema downgrade and record the restore of the pre-update backup; run the full install, update and rollback with the shell scripts on Linux ([rehearsal, "Not exercised"](../../ops/tests/ac09_offline_lifecycle.md#not-exercised-in-this-rehearsal)). Since 1.0.2 (DEF-016) `/api/v1/health` answers 503 when the database check fails, so a release whose API starts but cannot use the database is now detected as unhealthy; the rehearsal should include that case |
| <a id="nx-128"></a>NX-128 | Display the maintenance notice and UI banner | P3 / S | Show `maintenance_notice` and `ui_banner` on the staff screens and the OPAC when they are set, escaped as plain text. Today both settings are stored and returned by the settings API only |
| <a id="nx-129"></a>NX-129 | Show a failing health check on the System health screen | Done / S | Fixed in release 1.0.2 (DEF-024): the screen reads the 503 report. |

## Sequencing

| Phase | Items | Why first |
|---|---|---|
| 1. Site readiness | NX-126, NX-125, NX-111, NX-107, NX-108 | Run on the target platform with the site's certificate and data source, and allow kiosks to be connected |
| 2. Hardware and messaging | NX-101, NX-112, NX-106, NX-104 | Real devices, tags and cards replace the simulator; alerts reach staff |
| 3. Capacity and assurance | NX-063, NX-123, NX-121 | Load at peak, lawful data handling and an independent security test before go-live |
| 4. Full scope | NX-109, NX-110, NX-113, NX-114, NX-102, NX-103, NX-117, NX-119, NX-120, NX-122, NX-127, NX-064 | Complete the SOP functional scope and harden operations |
| 5. Later | NX-105, NX-115, NX-116, NX-118, NX-124, NX-128 | On demand |
