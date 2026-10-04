# Nexus — RFID-Enabled Library Solution

Nexus is a modular prototype that adds RFID workflows (tagging, circulation, inventory, security gates, smart-card login), reporting, data migration and offline lifecycle management to an existing Integrated Library Management System (ILMS) **without modifying, deleting or corrupting existing library records**.

All external devices and services (RFID readers, handhelds, gates, smart cards, CCTV, email, SMS, print, the legacy ILMS, NCIP/SIP2 endpoints) are integrated through documented adapter interfaces with working mocks. All data and credentials in this repository are synthetic.

## Repository map

| Path | Purpose |
|---|---|
| `docs/00-project-control/` | Engineering standards, SOP stage-gate records, issue tracker, progress log, defect log |
| `docs/01-requirements/` | D1 — Requirements package (RTM, assumptions, use cases, data dictionary) |
| `docs/02-design/` | D2 — Architecture package |
| `backend/` | FastAPI application, RFID middleware, interop and integration adapters |
| `frontend/` | React staff UI, OPAC, dashboard and administration |
| `device-sim/` | RFID device simulator (staff reader, handheld, gate, smart card, camera) |
| `migration/` | Spreadsheet migration utility and synthetic data generator |
| `ops/` | Offline install, update, rollback, backup, restore and integrity tooling |

## Delivery process

Development follows the AISYS Software Development SOP §9 stage by stage. Each stage is delivered on a `stage/N-*` branch, closed by a stage-gate review record in `docs/00-project-control/stage-gates/`, merged into `main` and tagged `sop-stage-N`.

Build and run instructions are added in SOP Stage 3 (foundation build).
