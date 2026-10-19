# Training Plan

Role-based training for Nexus 1.0.2. Each session is hands-on, on a training stack with synthetic data, using the device simulator in place of RFID hardware. Screens and procedures are described in the [user guide](user-guide.md) and the [administrator guide](administrator-guide.md).

## 1. Training environment

Set up once per course, never on a production installation:

1. Start a development stack and seed it (see the [README](../../README.md#build-and-run-development)):
   ```sh
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
   docker compose exec api python -m app.db.seed --legacy 2000 --demo
   ```
2. Sign-in details for the demo staff accounts and patrons, smart-card UIDs and device keys are in `ops/demo-credentials.txt`. Hand each trainee only the account for their role.
3. Prepare the simulator on the trainer's machine (or `docker compose --profile demo up -d devsim` for the web panel on `http://127.0.0.1:8100`):
   ```powershell
   cd device-sim
   pip install -r requirements.txt
   $env:SIM_API = "https://localhost:8443/api/v1"
   $env:SIM_CA_FILE = "..\ops\nginx\certs\nexus.crt"
   python sim.py heartbeat --all
   ```
   For shelf sweeps also set `SIM_USER` and `SIM_PASSWORD` to the demo Librarian account.
4. Check that **Devices** shows `STAFF-01`, `HH-01`, `GATE-01` and `CARD-01` online after the heartbeat (`CAM-01` and `PRN-01` stay offline; that is expected).

Training data used below (all synthetic):

| Data | Value |
|---|---|
| Member (UG, limit 4 items) | `B00144` |
| Lending item | `ACC-000002` |
| Reference item | `ACC-000013` |
| Shelf and foreign shelf | `A-01`, `B-01` |
| New training copy (created in session T3) | accession `ACC-900001`, barcode `TRN-900001` |
| Training tag EPC | `E28011600000000000B00001` (choose another hex value if it is already registered) |

After a course, re-create the stack or restore the backup taken before it.

## 2. Sessions

| Session | Audience | Duration | Prerequisite |
|---|---|---|---|
| T1 Orientation | All staff | 30 min | — |
| T2 Circulation desk | Circulation Clerks, Librarians | 90 min | T1 |
| T3 Collection and RFID | Librarians | 2 h 30 min | T2 |
| T4 Oversight and audit | Auditors | 60 min | T1 |
| T5 Administration and operations | Admins | 3 h | T3 |
| T6 Patron self-service | Front-line staff who brief patrons | 20 min | T1 |

### T1 Orientation (all staff, 30 min)

Content:
- What Nexus does alongside the existing ILMS; legacy records are read-only.
- Roles and the menu each role sees ([user guide](user-guide.md#menu-by-role)).
- Signing in by password and by staff card; why reloading the page signs you out.
- Red refusal banners: message plus code.
- The public OPAC.

Exercises:
1. Sign in with your demo account; note the landing screen and menu.
2. Sign out by reloading the page; sign in again.
3. Card sign-in: select **Tap staff card**, then the trainer runs
   ```sh
   python sim.py tap --reader CARD-01 --uid <your card UID from ops/demo-credentials.txt>
   ```
4. Search the OPAC for a subject and tick **Available now**.

### T2 Circulation desk (Clerks and Librarians, 90 min)

Content: look-up, check-out, renewal, check-in, refusal codes, current loans and channels, the gate monitor.

Exercises:
1. Look up `B00144`; read loans and fines against the limits.
2. Check out `ACC-000002`; note the due date (14 days for UG).
3. Renew it; note the new due date and the renewal count.
4. Try to check out reference item `ACC-000013`: expect `ITEM_REFERENCE_ONLY`, and loans unchanged.
5. Check `ACC-000002` in.
6. Try to check it in again: expect `ITEM_NOT_ON_LOAN`.
7. With **Gate monitor** open (clear **Alarms only**), the trainer walks a tagged item that is not on loan out. The trainer takes its EPC from the Tagged items report (filter shelf `A-01`, tag status `active`):
   ```sh
   python sim.py gate --gate GATE-01 --epc <EPC from the report> --direction out
   ```
   Identify the alarm card, accession number, snapshot and "email queued".
8. The trainer repeats with `--direction in`: an event with no alarm.

### T3 Collection and RFID (Librarians, 2 h 30 min)

Content: cataloguing, item validation, tagging and re-tagging, shelf inventory, members (create, block, card), dashboard, reports and exports, device status and the outbox.

Exercises:
1. **Catalogue.** Create a bibliographic record, then add copy `ACC-900001`, barcode `TRN-900001`, shelf `A-01`, type Lending. Open the item and select **Validate for tagging**.
2. **Tag (AC 02).** On **Tagging**, find `ACC-900001`. The trainer places the blank tag on the staff station:
   ```sh
   python sim.py scan --station STAFF-01 --epc E28011600000000000B00001
   ```
   Confirm the EPC fills in, select **Associate**, and read the relationship table (active, security bit on).
3. **Gate with a tagged item (AC 06).** Walk the new item out: alarm. Check it out to `B00144` at the desk, then walk it out again with the bit cleared: no alarm.
   ```sh
   python sim.py gate --epc E28011600000000000B00001 --direction out
   python sim.py gate --epc E28011600000000000B00001 --direction out --bit off
   ```
   Check it in afterwards.
4. **Gate while Nexus is unreachable.** The trainer runs:
   ```sh
   python sim.py offline on
   python sim.py gate --epc E28011600000000000B00001 --direction out
   python sim.py offline off
   ```
   Find the replayed event marked "decided offline".
5. **Inventory (AC 05).** Start a session for `A-01` with `HH-01`; copy the session id shown on screen. The trainer sweeps, leaving two items out and adding one from `B-01`:
   ```sh
   python sim.py sweep --handheld HH-01 --shelf A-01 --session <session id> --omit 2 --add-foreign B-01
   ```
   Watch green and amber tiles, then **Close and report**: 2 missing, 1 misplaced. Discuss why you confirm by hand before **Confirm and mark missing** (do not confirm in training).
6. **Members.** Create a member; print the card PDF. Block `B00144` with a reason, try a check-out at the desk (`MEMBER_BLOCKED`), then unblock.
7. **Dashboard and reports (AC 08).** Read the tiles; run the Gate events report for today with alarm `true`; export CSV and PDF.
8. **Devices.** Find the gate's last heartbeat and the queued `gate_alert` emails in the outbox.

### T4 Oversight and audit (Auditors, 60 min)

Content: read-only access, masked personal data, the audit log, reports.

Exercises:
1. Open **Members** and confirm email and phone appear as `***`.
2. **Audit log**: filter `circulation.` for today; find the check-out, renewal, refusal and check-in from T2 and their channel.
3. Filter `auth.login.failure` after the trainer makes a failed sign-in; note that the username is not recorded.
4. Filter `gate.alarm` and match the entries to the Gate events report.
5. Export the Members report to CSV and confirm contact details are masked.
6. Confirm the menu has no Circulation desk, Catalogue, Migration or Administration, and explain that the server refuses any change from this role with `ERR_FORBIDDEN` even if it is attempted directly against the API.

### T5 Administration and operations (Admins, 3 h)

Content: staff users, smart cards, policies, settings through the API, device registration and key rotation, migration, licence, health, backup, restore, update and rollback, the runbook.

Exercises:
1. **Users.** Create a Circulation Clerk with a smart-card UID (8 hexadecimal characters of your choice). Sign in as them with **Tap staff card** while the trainer taps that UID. Deactivate the user and tap again: expect "This card is not registered to an active staff member".
2. **Policies.** Change the UG loan days to 21, check out an item and confirm the due date, then set it back to 14. Find both `policy.update` entries in the audit log.
3. **Settings (API).** With an Admin token:
   ```http
   PUT /api/v1/admin/settings/gate_alert_recipients
   Content-Type: application/json

   {"value": ["training@example.org"]}
   ```
   Trigger a gate alarm and find the new recipient in the outbox. Try an invalid value (`{"value": "not-a-list"}`) and expect `SETTING_INVALID`.
4. **Devices (API).** Register a handheld `HH-02` (`POST /api/v1/devices`), keep the key it returns, and send a heartbeat with it:
   ```powershell
   $env:SIM_DEVICE_KEYS = '{"HH-02": "<key returned by the API>"}'
   python sim.py heartbeat --device HH-02
   ```
   Rotate the key (`POST /api/v1/devices/HH-02/rotate-key`), send another heartbeat with the old key and expect `401 ERR_DEVICE_AUTH`, then update `SIM_DEVICE_KEYS` and confirm `202`. Clear `SIM_DEVICE_KEYS` afterwards.
5. **Migration (AC 01).** Generate a small file and run it through the Migration screen:
   ```sh
   python migration/gen_sample.py --rows 500 --out migration/samples/training-500.xlsx --seed 7
   ```
   Stage, validate, read the reconciliation, download the row-level CSV, commit, then roll back the batch.
6. **Licence.** Read the licence status on **System health**. Walk through the activation steps in the [administrator guide](administrator-guide.md#9-licence-activation); on the development stack the licence is reported but not enforced.
7. **Backup and restore.** On the training stack only:
   ```sh
   COMPOSE_FILE="docker-compose.yml;docker-compose.dev.yml" sh ops/backup.sh training
   docker compose exec api python /app/ops/integrity.py snapshot --label before
   ```
   Restore the backup with `ops/restore.sh` (same `COMPOSE_FILE`), take a second snapshot and run `integrity.py compare`. Use `;` between the compose files in Git Bash on Windows and `:` on Linux or macOS ([runbook §11](troubleshooting-runbook.md#11-operator-scripts-on-a-development-stack)).
8. **Runbook drill.** Stop the database (`docker compose stop db`), read `/health` (HTTP `503`, `"status": "degraded"`, `"database": false`) and watch `docker compose ps` mark `api` `unhealthy` after about two minutes. Start the database again and confirm `/health` answers `200` `ok` and `api` returns to `healthy` without restarting the API. Discuss the update and rollback procedure using the AC 09 rehearsal record.

### T6 Patron self-service briefing (20 min)

Content: what patrons can do, so staff can help them.

Exercises:
1. Sign in as a demo patron with the card number and password from `ops/demo-credentials.txt`.
2. Open **My loans**; renew a loan; read a refusal if the renewal limit is reached.
3. Read the fines list.
4. Use the OPAC without signing in.

## 3. Assessment checklist

A trainee passes a session when the trainer has seen them complete each item without help.

### Circulation Clerk (T1, T2)

- [ ] Signs in by password and by staff card.
- [ ] Looks up a member and explains loans and fines against the limits.
- [ ] Checks out, renews and checks in an item, and reads the due date.
- [ ] Explains `ITEM_REFERENCE_ONLY`, `MEMBER_BLOCKED`, `FINE_LIMIT_EXCEEDED`, `MAX_ITEMS_REACHED` and `ITEM_NOT_ON_LOAN` in plain words.
- [ ] Recognises a gate alarm, its accession number and snapshot, and states the desk procedure for it.
- [ ] Explains "decided offline" on a gate event.

### Librarian (T1 to T3)

- [ ] All Circulation Clerk items.
- [ ] Creates a bibliographic record and a copy, and validates it for tagging.
- [ ] Tags an item from a staff-station read and reads the relationship table.
- [ ] Runs a shelf inventory, reads found, misplaced and missing, and explains when to confirm missing items.
- [ ] Creates, blocks and unblocks a member and prints a card.
- [ ] Runs a report with filters and exports it to CSV and PDF.
- [ ] Reads device status and finds a message in the notification outbox.

### Auditor (T1, T4)

- [ ] Filters the audit log by action prefix and date, and follows one circulation event across entries.
- [ ] Explains which personal data is masked for the Auditor role and why.
- [ ] Matches gate alarms in the audit log to the gate-events report.
- [ ] Exports a report and confirms masking in the file.

### Admin (T1 to T3, T5)

- [ ] Creates and deactivates a staff user, and assigns a smart card.
- [ ] Changes a circulation policy and finds its audit entry.
- [ ] Reads and changes a setting through the API, and explains which settings have an effect in 1.0.2.
- [ ] Registers a device, rotates its key, and explains why the key is shown only once.
- [ ] Runs a migration batch from staging to rollback and explains the reconciliation.
- [ ] Explains read-only mode and activates a licence (procedure).
- [ ] Takes a backup, restores it on a training stack and proves legacy integrity.
- [ ] Uses the runbook to diagnose a degraded `/health` (HTTP 503) and an `unhealthy` API container.

### Patron briefing (T6)

- [ ] Signs in as a patron with a card number, renews a loan and reads fines.
- [ ] Explains to a patron why a renewal was refused.

## 4. Records

Keep the session, date and checklist result for each trainee in the site's own training records, not in this repository.
