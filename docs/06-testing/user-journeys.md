# User Journeys: Manual Checks

Manual walkthroughs on the development stack (seeded with `python -m app.db.seed --legacy 2000 --demo`), in addition to the automated suites. Results come from the running UI at `http://localhost:5173` against the API on `:8000`.

## Stage 4: core library functions (2026-10-07)

| # | Journey | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| UJ-01 | Role-aware landing page | Librarian, Circulation Clerk | Sign in | Librarian lands on the dashboard; clerk lands on the circulation desk; menus show only permitted screens | Pass |
| UJ-02 | Dashboard | Librarian | Open Dashboard | Tiles show tagged/untagged items, members, loans, overdue loans, open fines and gate alarms from live data; 30-day loan chart and top titles render | Pass (1,391 tagged, 958 untagged, 142 on loan, 95 overdue, 598.00 open fines) |
| UJ-03 | Reference item refused | Circulation Clerk | Look up member `B00144`, check out reference item `ACC-000013` | Red refusal banner "reference item cannot leave the library" with code `ITEM_REFERENCE_ONLY`; no loan created | Pass |
| UJ-04 | Issue and return | Circulation Clerk | Check out lending item `ACC-000002` to `B00144`, then check it in | Issue message with due date 14 days out (UG policy); loan appears under Current loans; member loan count 1/4; after check-in the loan disappears and the count returns to 0/4 | Pass |
| UJ-05 | Public catalogue | Anonymous | Open OPAC | All 2,000 records listed with copies available / total; no sign-in required | Pass |
| UJ-06 | Session handling | Any | Reload the page | In-memory tokens are cleared; the user is returned to sign-in (by design: no tokens in browser storage) | Pass |

Console check: no application errors. Earlier `defaultProps` warnings came from the charting library and were removed by upgrading to Recharts 3 (DEF-004). The 401 and 409 network entries are expected: a pre-sign-in token check, and the deliberate refusal in UJ-03.

Screenshots of these journeys are taken in the Stage 7 user-acceptance run (`evidence/uat/`). During this session the browser pane could not render off-screen, so the evidence above is recorded from page text.

## Stage 5: RFID middleware and integrations (2026-10-07)

Run with the device simulator (`device-sim/sim.py`) against the development API.

| # | Journey | Steps | Expected | Result |
|---|---|---|---|---|
| UJ-07 | Smart-card sign-in (AC 07) | Login page → "Tap staff card"; `python sim.py tap --uid <librarian card>` | The page waits on its own challenge, completes when the tap arrives, and the librarian lands on the dashboard | Pass |
| UJ-08 | Gate alarm (AC 06) | Gate monitor open; `python sim.py gate --epc <unissued item>` | Red alarm banner and tone; newest card shows accession number, CCTV snapshot and "email queued" | Pass (`evidence/stage5/ac06-gate-monitor-alarm-with-cctv.jpg`) |
| UJ-09 | Gate while Nexus is unreachable (FR 07) | Stop the API; `sim.py gate …` (alarm decided from the security bit, queued); start the API; `sim.py offline off` | Queued event replayed once, marked "decided offline", ordered by passage time | Pass |
| UJ-10 | Offline mode with the link up | `sim.py offline on`; two gate passages (bit on, bit off); `sim.py offline off` | Both replayed; Nexus records the bit-off passage as an alarm too, because the item is not on loan, which flags the tag/loan mismatch | Pass (finding recorded below) |
| UJ-11 | Handheld inventory (AC 05) | Inventory screen → Start session A-01; `sim.py sweep --shelf A-01 --session <id> --omit 2 --add-foreign B-01`; Close and report | Live grid fills (253 of 254 expected); report: 252 found, 1 misplaced (home shelf B-01), 2 missing (exactly the omitted items) | Pass |

**Finding (UJ-10).** A gate that trusts only the security bit lets an item through if its bit was wrongly cleared. Nexus re-checks every passage against open loans and records such a passage as an alarm, so the mismatch shows up on the gate monitor and in the gate-events report. This is intended behaviour; it is documented in the administrator guide (Release).

**Simulator change from this run.** Events queued during an outage are now marked as offline decisions (the gate decided on its own), and shelf sweeps read EPCs from one tagged-items report call instead of one call per item.
