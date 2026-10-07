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
