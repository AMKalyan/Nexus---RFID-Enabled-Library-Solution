# Risks, Dependencies and Excluded Work

Owner: Moksh · Opened: 2026-10-04 (SOP Stage 1)

## 1. Risk register

Likelihood (L) and impact (I) are rated High, Medium or Low.

| ID | Risk | L | I | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R-01 | 48-hour time box is too short for full scope (12 FR, 9 NFR, 9 deliverables) | H | H | Acceptance-scenario-first vertical slices; non-AC features as Partial/Backlog in the RTM; daily cut-line | Moksh | Open |
| R-02 | Legacy records accidentally modified by migration or integration | L | H | Read-only DB role on `legacy_ilms`; mandatory backup before change; checksum integrity tool; AC 10 test | Moksh | Open |
| R-03 | Container runtime unavailable or unreliable on Windows host | M | H | Docker Desktop with WSL2 on the dev host; documented Windows Server 2022 options; native install noted in backlog | Moksh | Open |
| R-04 | Offline install fails due to missing dependency | M | H | Bundle all images with `docker save`; SHA-256 checksums; install rehearsal with network disabled | Moksh | Open |
| R-05 | Personal data or secrets committed by mistake | L | H | Synthetic-data declaration; `.gitignore` for `.env`/keys; secret scan in pipeline; review at every gate | Moksh | Open |
| R-06 | Mock behaviour diverges from real devices/protocols | M | M | Contracts documented independently of mocks; mocks exercise timeouts, duplicates and offline modes | Moksh | Open |
| R-07 | Evaluator reads NCIP/SIP2 subset as a compliance claim | M | M | Explicit "no certification claimed" statements; message coverage tables | Moksh | Open |
| R-08 | 20k-row import is slow or locks the DB | M | M | Bulk insert into staging; set-based validation; single commit transaction; timed perf test | Moksh | Open |
| R-09 | Dependency licence incompatible with offline redistribution | L | M | Prefer MIT/BSD/Apache/PostgreSQL licences; SBOM with licence review | Moksh | Open |
| R-10 | Demo failure on the day (environment drift) | M | H | Scripted demo, seed reset command, recorded fallback video | Moksh | Open |

## 2. Dependencies

| ID | Dependency | Type | Needed by | Notes |
|---|---|---|---|---|
| DEP-01 | Docker Desktop (WSL2 backend) on the development host | Tooling | Stage 3 | Being installed on 2026-10-04 |
| DEP-02 | PostgreSQL 16 container image | Runtime | Stage 3 | Official `postgres` image (PostgreSQL licence) |
| DEP-03 | Python 3.11+ base image and pinned PyPI packages | Runtime | Stage 3 | Pinned in `backend/requirements*.txt` |
| DEP-04 | Node 20+ and pinned npm packages (build time only) | Tooling | Stage 3 | Built into a static bundle served by nginx |
| DEP-05 | nginx container image | Runtime | Stage 3 | TLS termination and static UI |
| DEP-06 | Synthetic data generator (Faker) | Tooling | Stage 3/6 | No real personal data |
| DEP-07 | Vendor RFID SDKs, ILMS APIs, SMS/email gateways, CCTV VMS | External | Production | Unavailable. Replaced by mocks behind adapters |

## 3. Excluded work (SOP §3)

| Excluded item | How the prototype handles it |
|---|---|
| Manufacture, installation or repair of RFID readers, gates, tags, smart cards, printers, PCs, servers, cameras or cabling | Device simulator and mock adapters only |
| Access to production systems, production databases, personal data, restricted networks or live institutional environments | Synthetic `legacy_ilms` schema; synthetic people and credentials |
| NCIP, SIP2, ISO, OEM, security or performance certification claims | Implemented subsets are documented as boundaries with test evidence only; no certification is claimed |
| Real email/SMS delivery, real CCTV capture | Outbox and synthetic images |
| Multi-branch, multi-language, high-availability clustering | Listed in the production-completion backlog |
