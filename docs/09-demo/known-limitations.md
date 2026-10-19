# Known Limitations

Limitations of release 1.0.2, with their impact, the workaround available today and the production-backlog item that removes them. Sources: the [RTM](../01-requirements/rtm.md) (every row not marked Done), the [defect log](../00-project-control/defect-log.md) (every defect not closed), the verification evidence in [`docs/06-testing/`](../06-testing/) and the prototype design choices recorded in the ADRs.

Backlog items are in [production-backlog.md](production-backlog.md). NX-063 and NX-064 are also open in the [issue tracker](../00-project-control/issue-tracker.md).

## 1. Requirements not fully met (RTM)

| Req | RTM status | Limitation | Impact | Workaround | Backlog |
|---|---|---|---|---|---|
| FR 01 Core ILMS | Partial | Acquisition is captured only as price and acquisition date on the item; there is no ordering, vendor or budget workflow. Serials (subscriptions, issue check-in, claims) are not built | Acquisition and serials stay in the existing ILMS | Keep using the existing ILMS for acquisition and serials; Nexus catalogues the received items | [NX-113](production-backlog.md#nx-113), [NX-114](production-backlog.md#nx-114) |
| FR 03 RFID interoperability | Mock | Devices are reached only through the device simulator; no vendor SDK is integrated. NCIP covers 4 messages (LookupUser, CheckOutItem, RenewItem, CheckInItem) and SIP2 5 message pairs (99/98, 23/24, 11/12, 29/30, 09/10). Neither is conformance-tested | Real readers, gates and kiosks need an adapter before use; other NCIP/SIP2 messages return `Unsupported Service` or `96` | Device bridges that speak the documented event contract ([interface design §2](../02-design/interface-design.md)); kiosks limited to the supported messages | [NX-101](production-backlog.md#nx-101), [NX-109](production-backlog.md#nx-109), [NX-110](production-backlog.md#nx-110) |
| FR 07 Security gate events | Mock | Gate, camera and offline replay are proven against simulated devices only. CCTV images are generated placeholders, not camera frames | No real evidence image is attached to an alarm | Staff review the site's own CCTV for the time on the alarm card | [NX-101](production-backlog.md#nx-101), [NX-102](production-backlog.md#nx-102) |
| FR 09 Notifications | Mock | Email, SMS and print channels write to the outbox through mock adapters; nothing leaves the server | Patrons and staff receive no real messages | The outbox (Devices → Notification outbox) shows every queued message and its status | [NX-103](production-backlog.md#nx-103), [NX-104](production-backlog.md#nx-104), [NX-105](production-backlog.md#nx-105) |
| NFR 03 Compatibility | Partial | Verified on a Windows 11 host (AC 09 rehearsal) and in a browser on Windows 11 (UAT). Not run on Windows Server 2022. Nexus runs only as Linux containers; there is no native Windows service | A Windows Server site needs Docker with Linux containers (WSL 2 or Hyper-V) or a Linux VM | Use the [environment checklist](../07-deployment/environment-checklist.md) host options | [NX-118](production-backlog.md#nx-118), [NX-126](production-backlog.md#nx-126) |

### Release-stage rows

These rows were not yet marked Done in RTM v0.7 because their evidence is the release documentation itself (issue NX-070). They are tracked to closure in this release, not in the production backlog.

| Row | RTM status | Outstanding evidence |
|---|---|---|
| NFR 04 Licensing | In progress | SBOM and licence inventory (`docs/04-repository/sbom-and-licences.md`) |
| NFR 06 Maintainability | In progress | Shown by inspection in the traceability matrix; final status at release |
| NFR 07 Supportability | In progress | Troubleshooting runbook (D8) |
| NFR 08 Documentation | Planned | D7 deployment and D8 operational documentation |
| NFR 09 Delivery | Planned | This D9 package, including the [production backlog](production-backlog.md) |
| D4, D7, D8, D9 | In progress / Planned | Final RTM statuses at the release tag |

## 2. Open defects

| Defect | Severity | Status | Limitation | Impact | Workaround | Backlog |
|---|---|---|---|---|---|---|
| [DEF-008](../00-project-control/defect-log.md) | S3 | Known limitation | One API process saturates at about 86 req/s. At 50 concurrent users search p95 is 842 ms (target 500 ms) and check-out p95 is 1,104 ms (target 300 ms) | Slower responses at peak load; no errors in any run | Q-08 targets are met at 10 concurrent users (search p95 82 ms, check-out p95 227 ms). Running more API workers is not supported in 1.0.2, see §3 | [NX-063](production-backlog.md#nx-063) |
| [DEF-012](../00-project-control/defect-log.md) | S3 | Monitoring | One full test run stalled for about 15 minutes in `POST /api/v1/bibs`; not reproduced under lock monitoring | Test-suite reliability only; no effect seen on the running application | The test database sets `lock_timeout = 30s`, so a recurrence fails fast and names the blocked statement | [NX-064](production-backlog.md#nx-064) |

No S1 or S2 defect is open.

The release-stage defects DEF-015 to DEF-023, found while writing the release documentation, are fixed in 1.0.2 and are no longer limitations: the client address can no longer be spoofed through `X-Forwarded-For` (DEF-015), `/api/v1/health` answers 503 when a check fails (DEF-016), an empty SIP2 allow-list refuses every connection (DEF-017), the containers restart after a host or Docker restart (DEF-018), a failed shell restore restarts the services (DEF-019), a pre-issued licence can be installed with its key and takes effect immediately (DEF-020), a migration commit whose counts do not reconcile is refused (DEF-021), the simulator keeps replayed events refused for a retryable reason (DEF-022) and SIP2 Patron Status carries initials only (DEF-023).

## 3. Prototype design choices

| Choice | Limitation | Impact | Workaround | Backlog |
|---|---|---|---|---|
| Single API process | The command bus, live hub, smart-card challenges and rate-limit counters are held in process memory, and the outbox worker runs inside the API process. A second worker or replica would not share them | No horizontal scaling; see DEF-008. The 4-worker run (162 req/s) was a diagnostic only | Size the host for one process; keep to the measured load | [NX-063](production-backlog.md#nx-063), [NX-117](production-backlog.md#nx-117) |
| HMAC licence files | Licences are HMAC-SHA256 signed, and the site holds the verification key (`LICENCE_KEY`), so anyone with that key can issue a licence | Licensing is a configuration control, not a vendor protection | Restrict access to `.env` on the server | [NX-119](production-backlog.md#nx-119) |
| Self-signed TLS certificate | `install.ps1` and `gen-cert.sh` generate a self-signed certificate (CN `nexus.local`, valid 825 days) | Browsers warn until the certificate is trusted; CLI tools need `--ca` | Install the site's own certificate as `ops/nginx/certs/nexus.crt` and `nexus.key` | [NX-125](production-backlog.md#nx-125) |
| SIP2 transport | SIP2 has no transport security. The TCP listener (port 6001) is off by default and, when enabled, accepts only addresses in `SIP2_ALLOWED_HOSTS`; an empty list refuses every connection (since 1.0.2, DEF-017). Patron Status returns initials, not the full name (DEF-023) | Card numbers and item IDs travel in clear text on the LAN | Keep the listener off, or enable it only for allow-listed kiosks on an isolated network segment; prefer NCIP over HTTPS | [NX-110](production-backlog.md#nx-110) |
| No conformance or certification claims | NCIP 2.0, SIP2 and ISO 28560 behaviour is documented and tested against mocks only (SOP §3). Tags are EPC strings with an ISO 28560-style item ID and security bit, not certified encodings | Interoperability with a specific vendor must be proven on site | Test each kiosk or reader against the supported message tables before go-live | [NX-109](production-backlog.md#nx-109), [NX-110](production-backlog.md#nx-110), [NX-112](production-backlog.md#nx-112) |
| Mock RFID hardware | Staff station, handheld, gate and smart-card reader are the device simulator (`device-sim/sim.py`) | No physical device is supported out of the box | Simulator CLI and panel for training and demonstration | [NX-101](production-backlog.md#nx-101) |
| Mock CCTV | `ADAPTER_CAMERA=mock` attaches a generated image naming the gate, accession and EPC | See FR 07 | See FR 07 | [NX-102](production-backlog.md#nx-102) |
| Mock SMS, email and print | `ADAPTER_SMS`, `ADAPTER_EMAIL` and `ADAPTER_PRINT` are `mock` | See FR 09 | See FR 09 | [NX-103](production-backlog.md#nx-103), [NX-104](production-backlog.md#nx-104), [NX-105](production-backlog.md#nx-105) |
| Mock credential provider | `ADAPTER_CREDENTIALS=mock` looks up the tapped card UID and signs in the matching active staff account. The card itself is not authenticated: there is no cryptographic exchange with the card and no PIN | Card sign-in proves the flow and the reader-bound challenge, not card security | Staff can always sign in with username and password | [NX-106](production-backlog.md#nx-106), [NX-120](production-backlog.md#nx-120) |
| Mock legacy ILMS | `legacy_ilms` is a synthetic schema seeded by `app.db.seed`; Nexus mirrors it once by reference ([ADR-0005](../02-design/adr/0005-legacy-integration.md)) | A real ILMS needs its own connector; mirrored records can drift from the source after the mirror | For the synthetic schema, re-running `python -m app.db.seed --demo` mirrors records added since the last run; changed records are not updated | [NX-107](production-backlog.md#nx-107), [NX-108](production-backlog.md#nx-108) |
| Single branch, English only | Assumption A-13 | No branch-level stock, policies or reports; UI text in English | — | [NX-115](production-backlog.md#nx-115), [NX-116](production-backlog.md#nx-116) |
| Staff accounts are local | Sign-in uses Nexus accounts (argon2id) or the mock card provider; no directory integration | Staff are managed in Administration separately from the institution's directory | Admin manages users and roles on the Administration screen | [NX-120](production-backlog.md#nx-120) |

## 4. Gaps found while preparing the demonstration

| Item | Limitation | Impact | Workaround | Backlog |
|---|---|---|---|---|
| NCIP agency registration | There is no screen, API endpoint or command to register an NCIP agency or rotate its key; the AC 03 tests create one with a fixture | A site cannot connect a kiosk without direct database access | The [demo script §3](demo-script.md#3-ac-03-circulation-through-the-desk-ncip-and-sip2) registers an agency with a one-off script inside the API container, storing only the key's SHA-256 hash | [NX-111](production-backlog.md#nx-111) |
| Device ingest validation order | Device events are validated before the device key is checked, so an unauthenticated caller with a malformed body gets 422 rather than 401 ([security checks §5](../06-testing/security-checks.md#5-defects-and-observations)) | Nothing is processed or stored, the schema is public and the ingest rate limit applies; recorded as an observation, not a defect | None needed | [NX-124](production-backlog.md#nx-124) |
| AC 09 paths not exercised | The automatic rollback after an unhealthy update and the restore after a failed schema downgrade were not run with a deliberately broken release. The shell scripts (`install.sh`, `update.sh`, `rollback.sh`) were exercised only for bundle verification ([rehearsal](../../ops/tests/ac09_offline_lifecycle.md#not-exercised-in-this-rehearsal)) | These paths share code with the proven ones but have no rehearsal record | Use the PowerShell scripts on Windows hosts; the restore itself is proven by AC 10 | [NX-127](production-backlog.md#nx-127) |
| Performance evidence | Figures are observations on one development host, not certified results (Q-08) | Capacity on site hardware is unknown | Re-run `backend/tests/perf/perf_async.py` on the target host | [NX-063](production-backlog.md#nx-063) |
| Security assurance | Scanners, 18 live smoke checks and a threat-table review only; no independent penetration test | Residual risk is not independently assessed | Keep the server on an isolated LAN behind the TLS proxy | [NX-121](production-backlog.md#nx-121) |
| Accessibility | No accessibility audit of the staff UI or OPAC | Conformance with accessibility guidelines is unknown | — | [NX-122](production-backlog.md#nx-122) |
| Data retention | Audit log, gate events (with CCTV images), outbox and backups are kept indefinitely; there is no retention or purge policy | Storage grows without bound; personal data is kept longer than necessary | Prune backups manually from the `backups` volume | [NX-123](production-backlog.md#nx-123) |

## 5. Gaps found while preparing release 1.0.2

| Item | Limitation | Impact | Workaround | Backlog |
|---|---|---|---|---|
| Maintenance notice not displayed | The `maintenance_notice` setting (and `ui_banner`) is stored and returned by `GET /api/v1/admin/settings`, but no screen displays it. The 1.0.1 build note said administrators could "publish" a notice | Staff and patrons do not see a notice set by an administrator | Announce maintenance through the library's usual channels | [NX-128](production-backlog.md#nx-128) |
| System health screen on a failing check | Since 1.0.2 `/api/v1/health` answers 503 when a check fails, and the **System health** screen does not display the body of an error answer. Opened during a failure it shows the overall badge as not ok with no checks listed; left open when a check starts failing, it keeps the last successful result | The screen can show a stale "ok" while the database is down | `docker compose ps` (`api` turns `unhealthy`) or a direct request to `/api/v1/health` ([administrator guide §10](../08-operations/administrator-guide.md#10-health-and-version)) | [NX-129](production-backlog.md#nx-129) |
| Client address on a development host | Rate limits and the audit log use the address nginx sees (DEF-015). With Docker port publishing on a development host that is the Docker gateway (for example `172.18.0.1`) for every client | On such a host all clients share one rate-limit counter and the audit log shows the same address for everyone | Run the server so nginx receives client connections directly; see the [configuration guide §4](../07-deployment/configuration-guide.md#4-ports-and-https) | — |
