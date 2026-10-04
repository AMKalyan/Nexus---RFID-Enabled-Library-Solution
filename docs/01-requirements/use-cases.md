# Use Cases and Acceptance Criteria

Actors:

| Actor | Description |
|---|---|
| Admin | Configures the system, manages users, roles, devices, policies and migrations |
| Librarian | Catalogues, tags, runs inventory, handles circulation and reports |
| Circulation Clerk | Issues, returns and renews items; looks up members |
| Auditor | Read-only access to reports and the audit log |
| Patron | Searches the OPAC and views their own loans and fines |
| Device | Staff reader, handheld reader, security gate, smart-card reader, camera (all simulated) |
| External system | Self-check kiosk or other ILMS speaking NCIP 2.0 / SIP2 (simulated) |

## Use case catalogue

| UC | Name | Primary actor | Requirements | AC |
|---|---|---|---|---|
| UC-01 | Migrate spreadsheet records | Admin | FR 10, NFR 01 | AC 01 |
| UC-02 | Catalogue an item | Librarian | FR 01, FR 02 | AC 02 |
| UC-03 | Tag or re-tag an item | Librarian | FR 05 | AC 02 |
| UC-04 | Check out an item | Circulation Clerk / External system | FR 04, FR 03 | AC 03, AC 04 |
| UC-05 | Renew a loan | Circulation Clerk / External system / Patron | FR 04 | AC 03 |
| UC-06 | Check in an item | Circulation Clerk / External system | FR 04 | AC 03 |
| UC-07 | Block or unblock a member | Librarian | FR 04 | AC 04 |
| UC-08 | Inventory a shelf with a handheld | Librarian + Device | FR 06 | AC 05 |
| UC-09 | Handle a security-gate alarm | Device + Librarian | FR 07, FR 09 | AC 06 |
| UC-10 | Log in with a smart card | Staff + Device | FR 03, FR 11 | AC 07 |
| UC-11 | View dashboard and reports | Librarian / Auditor | FR 08 | AC 08 |
| UC-12 | Install, update and roll back offline | Admin | FR 12 | AC 09 |
| UC-13 | Restore from backup | Admin | NFR 01 | AC 10 |
| UC-14 | Search the OPAC and browse the virtual bookshelf | Patron | FR 02 | — |
| UC-15 | Manage users, roles and policies | Admin | FR 11 | AC 07 |
| UC-16 | Configure notification preferences | Patron / Librarian | FR 09 | AC 06 |

## Acceptance criteria

Each scenario below is automated as `backend/tests/acceptance/test_acNN_*.py` unless noted otherwise.

### AC 01: Spreadsheet migration (UC-01)
```gherkin
Given a synthetic spreadsheet of 20,000 rows containing known invalid rows and known duplicates
When the Admin uploads it and runs validation
Then every row is stored in staging.import_row with status valid, rejected or duplicate
And every rejected row carries a reason code and every duplicate references the row or record it duplicates
And no row is written to the nexus catalogue during validation (dry run)
When the Admin commits the batch
Then a database backup is taken first
And all valid rows are inserted in a single transaction tagged with the batch id
And the reconciliation report shows source = valid + rejected + duplicate, and target = valid
And the legacy_ilms checksums are identical before and after
```

### AC 02: Catalogue and tag an item (UC-02, UC-03)
```gherkin
Given a Librarian is logged in
When they search for an existing bib record or create a new one with an item
Then the item is validated (mandatory fields, unique accession number, item not withdrawn)
When the staff reader mock reports a blank tag and the Librarian associates it with the item
Then an rfid_tag row links the EPC to the item with the security bit set
And the item page shows the tag-to-item relationship and tag history
And associating a tag with an invalid or withdrawn item is rejected with a reason
And re-tagging retires the previous tag instead of deleting it
```

### AC 03: Circulation through NCIP/SIP2 (UC-04, UC-05, UC-06)
```gherkin
Given an active member and an available, tagged lending item
When an NCIP CheckOutItem message is posted to /ncip
Then a loan is created with channel = ncip and a due date from the member's category policy
And the tag's security bit is cleared
When an NCIP RenewItem message is posted
Then the due date is extended and renew_count increases, up to the policy maximum
When an NCIP CheckInItem message is posted
Then the loan is closed, the security bit is set again, and any overdue fine is raised
And the SIP2 mock handles the same flow with messages 11, 29 and 09
And audit_log contains one entry per transaction with actor, channel, item and member
```

### AC 04: Circulation blocks (UC-04, UC-07)
```gherkin
Given circulation policies with a fine limit per member category
Then check-out is refused with code ITEM_REFERENCE_ONLY for a reference item
And refused with code MEMBER_BLOCKED for a blocked member
And refused with code FINE_LIMIT_EXCEEDED when the member's open fines exceed the category limit
And each refusal is returned identically through the UI API, NCIP and SIP2, and is audited
And changing the fine limit in configuration changes the outcome without a code change
```

### AC 05: Handheld inventory (UC-08)
```gherkin
Given a shelf whose expected items are known from the catalogue
And the handheld mock sweeps the shelf, omitting two items and including one item that belongs to another shelf
When the inventory session is closed
Then the report lists the two items as missing and the foreign item as misplaced, with its home shelf
And each read produces a confirmation event: green with a short beep for found, amber with a double beep for misplaced, red with a long tone for missing
And the inventory UI shows these visible and audible confirmations
```

### AC 06: Security-gate alarm (UC-09)
```gherkin
Given an item that is not checked out (security bit set)
When the gate mock reports the item's EPC passing outward
Then a gate_event is recorded with the accession number, alarm = true and authorised = false
And the camera mock supplies a CCTV snapshot that is attached to the event
And an email notification is queued in notification_outbox for the configured recipients
And the event appears live on the gate monitor
And when the API is unreachable the gate still alarms from the security bit, queues the event and replays it on reconnect, without creating duplicates
```

### AC 07: Smart-card login and RBAC (UC-10, UC-15)
```gherkin
Given staff users with different roles and registered smart-card UIDs
When the smart-card reader mock reports a CardTapped event for a staff UID
Then the credential provider resolves the user and a session is issued
And a Circulation Clerk can check out items but receives 403 on admin and migration endpoints
And an Auditor can read reports and the audit log but cannot perform circulation
And a Patron can read only their own loans; requesting another member's loans returns 403
And an unknown or deactivated card is rejected and audited
```

### AC 08: Dashboard and reports (UC-11)
```gherkin
Given seeded activity data
When a Librarian opens the dashboard
Then it shows totals for tagged items, members, active loans, overdue loans, open fines and today's gate alarms
And reports exist for tagged items, members, circulation, operator activity, RFID client (device) activity, fines and gate events
And each report can be filtered by date range plus at least one report-specific field
And each report exports to CSV and PDF
```

### AC 09: Offline install, update and rollback (UC-12). Scripted and manual test in `ops/tests/`
```gherkin
Given a host with Docker and no internet access
When the Admin runs the installer from the v1.0.0 offline bundle
Then the bundle checksums are verified, images are loaded from archives, and the stack becomes healthy
When the Admin applies the v1.0.1 update bundle
Then a backup is taken, migrations run, and /version reports 1.0.1
When the Admin runs the documented rollback
Then /version reports 1.0.0 again, and the data is consistent with the pre-update backup
```

### AC 10: Restore after a failed change (UC-13)
```gherkin
Given legacy_ilms checksums recorded before a migration
When a migration batch is committed and then deliberately failed or corrupted
And the Admin restores the pre-migration backup
Then the nexus data matches the pre-migration state
And the legacy_ilms checksums are identical to the original values
And the restore and integrity check are recorded in the audit log and integrity report
```
