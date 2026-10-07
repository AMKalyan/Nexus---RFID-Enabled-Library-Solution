# Stage Gate 5: RFID Middleware and Integrations (D6)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 5 |
| Branch | `stage/5-rfid` |
| Gate date | 2026-10-07 |
| Outcome | Approved |

## Exit criteria (SOP §9 Stage 5 bullets)

| SOP requirement | Output | Evidence | Met |
|---|---|---|---|
| Implement device-neutral commands and event handlers | Authenticated event ingest (per-device keys, stored hashed), type-checked envelope, dispatcher, command bus (WebSocket push or polling), live hub with permission-filtered topics, device registry with key rotation | `backend/app/middleware_rfid/`, `api/v1/devices.py`, `api/v1/ws.py`; `test_device_ingest.py` (10), `test_commands.py` (5), `test_live.py` (8) | ☑ |
| Add NCIP 2.0 and SIP2 adapter boundaries with mocks | NCIP LookupUser, CheckOutItem, RenewItem, CheckInItem for authenticated agencies; SIP2 99/98, 23/24, 11/12, 29/30, 09/10 with checksums; optional allow-listed TCP listener. Both use the shared circulation service; no conformance claimed | `backend/app/interop/`; `test_ac03_circulation_interop.py` (14), `test_sip2.py` (3) | ☑ |
| Implement tagging workflow | Validation before (re)tagging, retire-on-retag history, one owner per EPC, security bit set from loan state, staff-station reads published to the tagging screen | `services/tagging.py`; `test_ac02_tagging.py` (11); Tagging screen | ☑ |
| Implement inventory workflow | Handheld sessions, found/misplaced/unknown classification, repeat reads counted once, beep and light commands, missing list with librarian confirmation | `services/inventory.py`; `test_ac05_inventory.py` (8); UJ-11 | ☑ |
| Implement gate-event workflow | Every passage recorded with accession number; alarm when an item leaves without a loan; footfall; offline decisions replayed once and ordered by passage time | `services/gate.py`; `test_ac06_gate_event.py` (8); UJ-08..10 | ☑ |
| Implement notification workflow | Outbox with email, SMS and print mock channels, per-member preferences, configurable gate-alert recipients, retrying worker | `services/notifications.py`, `worker.py`; `test_outbox.py` (6) | ☑ |
| Implement smart-card workflow | Reader-bound, single-use challenge handshake; mock credential provider (active staff only); card UIDs never stored or audited | `services/smartcard.py`; `test_ac07_smartcard_rbac.py` (8); UJ-07 | ☑ |
| Implement camera workflow | Mock CCTV snapshot attached to every alarm; camera fault does not lose the alarm | `integrations/camera_mock.py`; `test_ac06_unissued_item_triggers_alarm_photo_and_email` | ☑ |
| Test retries, timeouts, duplicate events and offline behaviour | Command timeout and retry; outbox backoff and give-up; duplicate event ids; out-of-order offline replay; simulator queue ordering and outage marking | `test_fr03_command_times_out_and_retries`, `test_fr03_command_succeeds_on_retry`, `test_fr09_outbox_retries_then_sends`, `test_fr09_gives_up_after_five_attempts`, `test_fr03_duplicate_event_ignored`, `test_fr07_offline_replay_out_of_order`, `device-sim/test_sim.py` (6); UJ-09 | ☑ |

## Test totals at gate
189 backend tests (90% line coverage), 6 simulator tests and 8 frontend tests passing. ruff, mypy, bandit, pip-audit and npm audit are clean (`bash ops/ci-local.sh`). OpenAPI re-exported (58 paths).

## Findings and decisions
- Nexus confirms gate alarms against open loans instead of trusting the device's security bit. A passage the gate allowed because the bit was wrongly cleared is still recorded as an alarm (UJ-10).
- Card UIDs are masked before device events are stored, and are never written to the audit log.
- Two static-analysis findings were resolved. The SIP2 listener bind address is now a setting that defaults to loopback, and the NCIP response builder is annotated as not parsing input. A commit that went in while the pipeline was failing is noted in the progress records.
- Not covered by an automated test: the optional SIP2 TCP listener (a thin wrapper over the tested adapter). It is scheduled for the Stage 7 manual check.

## Decision
Approved on 2026-10-07. Migration and resilience (Stage 6) can start from `main` once this branch is merged.
