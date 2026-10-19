# Demonstration Script

Live demonstration of the ten priority acceptance scenarios (SOP §8, AC 01–AC 10) against release 1.0.2. On the installed-bundle stack the demonstration starts on 1.0.1 and updates to 1.0.2 live in §9. One section per scenario; the section numbers match the "Demo step" column of the [RTM](../01-requirements/rtm.md#3-priority-acceptance-scenarios).

Every step below was run during verification. The expected results are the ones recorded in the [UAT checklist](../06-testing/uat-checklist.md), the [user journeys](../06-testing/user-journeys.md), the [migration reports](../05-data-migration/README.md) and the [AC 09 rehearsal](../../ops/tests/ac09_offline_lifecycle.md). Counts that depend on the state of the database (dashboard tiles, live-read totals) are quoted from the UAT run and will differ slightly on another database.

All data, accounts and device keys are synthetic. Passwords, device keys and card UIDs are never typed on screen from this document: they are read from `ops/demo-credentials.txt`, which the seed command writes and git ignores.

## Contents

- [Time budget](#time-budget)
- [Pre-demo checklist](#pre-demo-checklist)
- [§1 AC 01 Migration](#1-ac-01-spreadsheet-migration)
- [§2 AC 02 Tagging](#2-ac-02-tagging)
- [§3 AC 03 Circulation and interoperability](#3-ac-03-circulation-through-the-desk-ncip-and-sip2)
- [§4 AC 04 Circulation blocks](#4-ac-04-circulation-blocks)
- [§5 AC 05 Handheld inventory](#5-ac-05-handheld-inventory)
- [§6 AC 06 Security gate](#6-ac-06-security-gate-alarm)
- [§7 AC 07 Smart-card sign-in](#7-ac-07-smart-card-sign-in-and-rbac)
- [§8 AC 08 Dashboard and reports](#8-ac-08-dashboard-and-reports)
- [§9 AC 09 Offline lifecycle](#9-ac-09-offline-install-update-and-rollback)
- [§10 AC 10 Restore and integrity](#10-ac-10-restore-and-legacy-integrity)
- [Fallback evidence](#fallback-evidence)

## Time budget

| Section | Scenario | Budget | Ends at |
|---|---|---|---|
| — | Opening: what Nexus is, the stack on screen, data is synthetic | 0:30 | 0:30 |
| §1 | AC 01 Migration of 20,000 rows | 2:00 | 2:30 |
| §2 | AC 02 Tagging | 1:00 | 3:30 |
| §3 | AC 03 Desk, NCIP and SIP2 circulation with audit trail | 2:30 | 6:00 |
| §4 | AC 04 Circulation blocks | 1:00 | 7:00 |
| §5 | AC 05 Handheld inventory | 1:30 | 8:30 |
| §6 | AC 06 Security gate alarm | 1:00 | 9:30 |
| §7 | AC 07 Smart-card sign-in and RBAC | 1:00 | 10:30 |
| §8 | AC 08 Dashboard and reports | 1:30 | 12:00 |
| §9 | AC 09 Offline lifecycle (short live version) | 1:30 | 13:30 |
| §10 | AC 10 Restore and legacy integrity (short live version) | 1:30 | 15:00 |

§9 and §10 take several minutes when run in full. The live versions above show the decisive step and then point to the recorded transcript and report.

## Pre-demo checklist

### 1. Choose one stack

Run only one Nexus stack on the demonstration host. Both use the Compose project name `nexus`, the same volumes and port 8443.

| | A. Development stack | B. Installed offline bundle |
|---|---|---|
| Use when | Presenting from the repository checkout | Presenting the delivered package; allows a full live §9 |
| Bring up | See [A](#a-development-stack) | See [B](#b-installed-offline-bundle) |
| UI | `https://localhost:8443` | `https://localhost:8443` |
| Certificate for CLI tools | `ops\nginx\certs\nexus.crt` | `<site>\ops\nginx\certs\nexus.crt` |
| Credentials file | `ops\demo-credentials.txt` (copied out of the API container) | `<site>\ops\demo-credentials.txt` (copied by `install.ps1 -Demo`) |
| Operator scripts | Need `COMPOSE_FILE` set to include the dev override | Run from `<site>` as they are |
| §9 live version | Bundle verification and the transcript | Update from 1.0.1 to 1.0.2 and roll back, live |

The UAT itself used the local-process setup from the README (API on `http://localhost:8000`, Vite on `http://localhost:5173`). That setup also works: leave `SIM_API` at its default and drop `--ca` from the commands. Rehearse once on whichever stack is used on the day.

#### A. Development stack

Start from empty volumes so that §1 migrates into a clean catalogue. If the database holds anything worth keeping, back it up first (`ops\backup.ps1`).

```powershell
cd "D:\AC\Nexus - RFID-enabled library solution"
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.dev.yml"   # operator scripts then include the dev override
Copy-Item .env.example .env                                        # first time only; replace every placeholder
sh ops/nginx/gen-cert.sh                                           # first time only (Git Bash sh)
docker compose up -d --build
docker compose exec api python -m app.db.seed --legacy 2000 --demo
docker compose cp api:/app/ops/demo-credentials.txt ops/demo-credentials.txt
```

Expected: the seed prints the legacy counts (2,000 bibs, 2,377 accessions, 300 borrowers) and the nexus counts, and reports that generated credentials were written.

#### B. Installed offline bundle

On the demonstration host, unzip `nexus-1.0.1.zip` into a site folder and install it. Keep `nexus-1.0.2.zip` on local media for §9. Both bundles are built from the repository with `sh ops/build_bundle.sh <version>` on the matching release tag; rehearse §9 once with the exact bundles used on the day.

```powershell
cd <site>\nexus-1.0.1
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Demo
```

Expected (as in rehearsal step 1, with the 1.0.1 bundle): `bundle verified`, images loaded, `.env`, certificate and 30-day demo licence created, then `version: {"version":"1.0.1","alembic_rev":"0004","licence":"valid","build_notes":"..."}` and `Nexus 1.0.1 is running at https://localhost:8443/`.

### 2. Tools and sample file

```powershell
pip install -r device-sim\requirements.txt -r migration\requirements.txt
python migration\gen_sample.py --rows 20000 --out migration\samples\library-export-20k.xlsx --seed 42   # if the file is not there yet
```

### 3. Console variables (one PowerShell window, kept open for the whole demo)

The helper reads values from the credentials file into variables without printing them.

```powershell
$creds = "ops\demo-credentials.txt"                     # stack B: "<site>\ops\demo-credentials.txt"
$ca    = "ops\nginx\certs\nexus.crt"                    # stack B: "<site>\ops\nginx\certs\nexus.crt"
function Get-DemoValue([string]$Label) {
    (Select-String -Path $creds -Pattern ("^" + [regex]::Escape($Label) + ": (\S+)$") | Select-Object -Last 1).Matches[0].Groups[1].Value
}
$env:SIM_API         = "https://localhost:8443/api/v1"
$env:SIM_CA_FILE     = $ca
$env:SIM_CREDENTIALS = $creds                           # device keys for the simulator
$env:SIM_USER        = "librarian"                      # shelf look-ups for the handheld sweep
$env:SIM_PASSWORD    = Get-DemoValue "staff librarian (Librarian) password"
$env:NEXUS_PASSWORD  = Get-DemoValue "staff admin (Admin) password"   # migration CLI
$librarianCard       = Get-DemoValue "staff librarian smart-card UID"
```

`Select-Object -Last 1` matters: the seed appends to the file, and the newest values are the valid ones.

Run the console from the folder that holds the active `docker-compose.yml`: the repository root for stack A (with `$env:COMPOSE_FILE` set), `<site>\nexus-1.0.1` for stack B. The `docker compose` commands in §3, §9 and §10 rely on it. For stack B, give `device-sim\sim.py` and `migration\nexus_migrate.py` with their full path in the repository checkout; the bundle does not contain them.

### 4. Baseline and devices

```powershell
python device-sim\sim.py heartbeat --all
$before = ((docker compose exec -T api python /app/ops/integrity.py snapshot --out /backups/reports --label demo-before) |
           Select-String '^report: ').Line -replace '^report: ', ''
$before
```

Expected: one `202` line per device; then the snapshot lists `accession` 2,377 rows, `borrower` 300 rows and `catalogue` 2,000 rows and prints its report path. §10 compares against this file.

### 5. Browser tabs and sign-ins

Sign in with the passwords from the credentials file, with the file kept off screen. Each tab keeps its own in-memory session; a reload returns to sign-in (UJ-06, by design).

| Tab | Account | Role | Used in |
|---|---|---|---|
| 1 | `admin` | Admin | §1 Migration screen, §3 Audit log, §9 System health |
| 2 | `librarian` | Librarian | §2 Tagging, §3–§4 Circulation desk and Members, §5 Inventory, §6 Gate monitor and Devices, §8 Dashboard and Reports |
| 3 | signed out, on the sign-in page | Librarian by card | §7 |
| Console | the PowerShell window above | — | Simulator, migration CLI, ops scripts |

The Circulation Clerk (`clerk`) and Auditor (`auditor`) accounts are not needed for the main flow. The clerk lands on the Circulation desk and can be used for §3–§4 instead of the librarian; the auditor can show the Audit log read-only.

### 6. Final checks

| Check | Expected |
|---|---|
| Tab 2 → Devices | STAFF-01, CARD-01, HH-01 and GATE-01 online (a device shows offline 30 s after its last event, so heartbeat again just before §2 if needed) |
| Tab 2 → Gate monitor | "Alarms only" ticked; seeded alarm cards listed |
| Tab 1 → System health | Database ok; version (1.0.2 on stack A, 1.0.1 on stack B before §9) and licence shown |
| Browser sound | On (§5 and §6 play tones through the Web Audio API) |

---

## §1 AC 01: Spreadsheet migration

**Scenario:** import a supplied spreadsheet into staging, reject invalid rows, identify duplicates, migrate valid records and reconcile source and target counts.

**Setup:** console variables set; Tab 1 (Admin) open.

1. In the console, stage, validate and commit the 20,000-row export:

   ```powershell
   python migration\nexus_migrate.py --ca $ca --file migration\samples\library-export-20k.xlsx --commit --csv $env:TEMP\migration-rows.csv
   ```

2. Copy the batch id from the first output line into a variable for §10:

   ```powershell
   $batch = "<batch id printed by the CLI>"
   ```

3. Tab 1 → **Migration** ("Data migration") → **Recent batches**.
4. Optionally open `$env:TEMP\migration-rows.csv` to show the reason codes and original cells of rejected and duplicate rows.

**Expected:**

| Output | Value (migration run report) |
|---|---|
| `Staged … rows as batch <id>` | 20,000 rows |
| Validation (dry run): `source` / `valid` / `rejected` / `duplicate` | 20,000 / 19,200 / 600 / 200 |
| `likely_duplicate` | 204 (200 planted; 4 match seeded records) |
| `balanced` | True: 20,000 = 19,200 + 600 + 200 |
| rejected rows by reason | ACCESSION_FORMAT 103, ISBN_CHECKSUM 112, ITEM_TYPE_UNKNOWN 98, PRICE_NEGATIVE 87, TITLE_MISSING 95, YEAR_RANGE 105 |
| Committed: `status` / `committed` | `committed` / 19,200 |
| `backup_file` | a `…-pre-migration-….dump` taken before the insert |
| Recent batches row | `library-export-20k.xlsx`, 20,000 rows, 19,200 committed, status committed |
| Time | 13.7 s end to end in the run report (target under 5 minutes) |

**Talking points:** rows are stored unchanged in `staging.import_row`; validation writes nothing to the catalogue; the commit is one transaction between two legacy fingerprints, so it aborts if any legacy table changes or the counts do not balance. Batch rollback (`nexus_migrate.py --rollback <batch-id>` or **Roll back batch** on the screen) was rehearsed with a 50-row batch: see the [run report](../05-data-migration/migration-run-report.md#batch-rollback-rehearsal).

## §2 AC 02: Tagging

**Scenario:** locate a bibliographic item, validate it, associate a mock RFID tag and display the tag-to-item relationship.

**Setup:** Tab 2 (Librarian). `ACC-100002` is one of the items migrated in §1 and has no tag.

1. Tab 2 → **Tagging** → card "1. Find the item": type `ACC-100002` → **Find**.
2. In the console, put a blank tag on the staff-station reader:

   ```powershell
   python device-sim\sim.py scan --station STAFF-01 --epc E28011600000000000A10002
   ```

3. Card "2. Read and associate a tag": the EPC field fills from the read → **Associate**.

**Expected:**

| Where | Value |
|---|---|
| Card 1 | Title, `ACC-100002`, shelf and status; "Validated: ready for tagging" |
| Console | `202 {"status":"accepted",…}` |
| Card 2 | "Blank tag read on the staff station: E28011600000000000A10002" |
| Banner after Associate | "Tag E28011600000000000A10002 is now linked to ACC-100002. Security bit on." |
| Tag-to-item relationship | One row: status active, security bit on, encoded time; `tag.associate` is audited |

If `ACC-100002` is already tagged (a database reused from the UAT run), use another migrated, untagged accession and a new EPC, and confirm card 1 says "Validated: ready for tagging" before associating. Remember the EPC for §6.

## §3 AC 03: Circulation through the desk, NCIP and SIP2

**Scenario:** check out, renew and check in an item through a mocked NCIP or SIP2 flow while preserving an auditable transaction history.

**Setup:** Tab 2 on **Circulation desk**; member `B00144`; lending items `ACC-000002` (desk), `ACC-000003` (NCIP) and `ACC-000004` (SIP2).

### Desk (UI channel)

1. Member card: type `B00144` → **Look up**.
2. Item card: `ACC-000002` → **Check out**, then **Renew**, then **Check in**.

Expected: "Issued ACC-000002, due …" (14 days for the UG category), "Renewed ACC-000002, now due …", "Returned ACC-000002". During the loan, Current loans lists the item with channel `ui`.

### NCIP 2.0 (self-check kiosk or partner library)

NCIP callers authenticate with an agency key. Release 1.0.2 has no screen or command for registering an agency (see [known limitations](known-limitations.md)), so register one once per database with a short script run inside the API container. The key is generated in the console and only its SHA-256 hash is stored.

```powershell
$env:NCIP_KEY = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$register = @'
import hashlib, sys
from app.db.base import SessionLocal
from app.db.models import Agency
with SessionLocal() as session:
    session.add(Agency(code="DEMO-ILL", name="Demonstration partner library",
                       api_key_hash=hashlib.sha256(sys.argv[1].encode()).hexdigest()))
    session.commit()
print("agency DEMO-ILL registered")
'@
$register | docker compose exec -T api python - $env:NCIP_KEY

$ncip = @'
import os, sys
import httpx
NS = 'xmlns="http://www.niso.org/2008/ncip" version="http://www.niso.org/schemas/ncip/v2_02/ncip_v2_02.xsd"'
service, card, accession = sys.argv[1:4]
user = "" if service == "CheckInItem" else f"<UserId><UserIdentifierValue>{card}</UserIdentifierValue></UserId>"
item = f"<ItemId><ItemIdentifierValue>{accession}</ItemIdentifierValue></ItemId>"
r = httpx.post(os.environ["SIM_API"] + "/ncip",
               content=f"<NCIPMessage {NS}><{service}>{user}{item}</{service}></NCIPMessage>",
               headers={"Content-Type": "application/xml", "X-Agency-Key": os.environ["NCIP_KEY"]},
               verify=os.environ.get("SIM_CA_FILE") or True)
print(r.status_code, r.text)
'@
$ncip | python - CheckOutItem B00144 ACC-000003
$ncip | python - RenewItem    B00144 ACC-000003
```

`python` here is any Python with `httpx` installed, for example the repository's `backend\.venv\Scripts\python.exe`.

Expected: `200` and an XML response with `<DateDue>` and no `<Problem>` element, for both messages.

### SIP2 (adapter boundary)

The SIP2 TCP listener is off by default (`SIP2_LISTENER_ENABLED=false`, because SIP2 has no transport security). The demo calls the same handler the listener uses, inside the API container:

```powershell
$ts = "20261005    101500"; $blank = " " * 18
$sip2 = @'
import sys
from app.db.base import SessionLocal
from app.interop.sip2 import Sip2Adapter
for message in sys.argv[1:]:
    with SessionLocal() as session:
        print(Sip2Adapter(session).handle(message))
'@
$sip2 | docker compose exec -T api python - "11YN$ts$($blank)AOMAIN|AAB00144|ABACC-000004|AC|" "29NN$ts$($blank)AOMAIN|AAB00144|ABACC-000004|"
```

Expected: the first response starts with `121` (check-out accepted), the second with `301` (renewal accepted); both carry the title (`AJ`) and due date (`AH`).

### Back at the desk, then return both items

1. Tab 2 → Member card: `B00144` → **Look up** again (DEF-013 fix: the loan list refreshes).
2. Current loans now lists `ACC-000003` with channel `ncip` and `ACC-000004` with channel `sip2`, each renewed once.
3. Return them through the same channels:

   ```powershell
   $ncip | python - CheckInItem B00144 ACC-000003
   $sip2 | docker compose exec -T api python - "09N$ts$($ts)AP|AOMAIN|ABACC-000004|AC|"
   ```

   Expected: NCIP `200` with no `<Problem>`; SIP2 response starting with `101`.

4. Tab 1 → **Audit log** → "Action starts with" `circulation.` → **Filter**.

Expected: `circulation.checkout`, `circulation.renew` and `circulation.checkin` entries for the `ui`, `ncip` and `sip2` channels, with the actor type (staff user for the desk, `external` for NCIP and SIP2). In the UAT run the log also showed the `circulation.refused` entry from §4.

## §4 AC 04: Circulation blocks

**Scenario:** block circulation for a reference item, a blocked member, or a member whose fine exceeds a configurable limit.

**Setup:** Tab 2 on **Circulation desk** with `B00144` looked up.

1. Item card: `ACC-000013` (reference item) → **Check out**.

   Expected: red banner "This is a reference item and cannot leave the library" with code `ITEM_REFERENCE_ONLY`; the member's loans stay at 0 / 4; `circulation.refused` is audited.

2. Optional (about 30 s), blocked member: Tab 2 → **Members** → search `B00144` → **Open** → **Block** (enter a reason) → **Circulation desk** → **Look up** `B00144` → `ACC-000002` → **Check out**.

   Expected: banner "This member is blocked from borrowing", code `MEMBER_BLOCKED`. Then **Members** → **Unblock** so later steps are not affected.

3. Mention the fine limit: the limit is set per member category on **Administration → Circulation policies** ("fine limit" column), and a member over it is refused with `FINE_LIMIT_EXCEEDED`. The blocked-member and fine-limit cases are covered by the `test_ac04_*` tests (16 cases, all passing), and the same refusal codes are returned over NCIP and SIP2 (`test_ac04_ncip_refusal_matches_ui_code`, `test_ac04_sip2_refusal_reported_in_screen_message`).

## §5 AC 05: Handheld inventory

**Scenario:** use a handheld-reader mock to inventory a shelf and report missing and misplaced items with visible and audible confirmation events.

**Setup:** Tab 2 → **Inventory**, "Sound" ticked.

1. Shelf `A-01`, Handheld `HH-01` → **Start session**. Copy the session id shown next to the buttons.
2. In the console, sweep the shelf, leaving out two tagged items and adding one item from shelf B-01:

   ```powershell
   python device-sim\sim.py sweep --shelf A-01 --session <session id> --omit 2 --add-foreign B-01
   ```

3. Watch the live grid fill, then **Close and report**.

**Expected (UAT run):**

| Where | Value |
|---|---|
| Console | `swept 253 tag(s): 202 …` |
| Live reads card | "Live reads · 253 of 254 expected": green tiles, one amber tile "misplaced (belongs on B-01)" with a warning tone |
| Report tiles | Found 252, Misplaced 1, Missing 2, Unknown tags 0 |
| Missing from shelf | The two omitted items (random each run) |
| Misplaced | One item with home shelf B-01 (`ACC-000010` in the UAT run) |

Do not press **Confirm and mark missing** unless asked: the UAT left the missing items' status unchanged, and the confirmation is the librarian's decision.

## §6 AC 06: Security gate alarm

**Scenario:** generate an unauthorised-removal event from the gate mock, record the accession number, attach a mock CCTV image and queue an email notification.

**Setup:** Tab 2 → **Gate monitor**, "Alarms only" ticked. The item tagged in §2 is not on loan, so its security bit is on.

1. In the console, walk the item out through the gate:

   ```powershell
   python device-sim\sim.py gate --gate GATE-01 --epc E28011600000000000A10002 --direction out
   ```

2. Tab 2 → **Devices** → **Notification outbox**.

**Expected:**

| Where | Value |
|---|---|
| Console | `gate ALARM: 202 …` and a console bell |
| Gate monitor | Red banner "Security gate alarm" with an alarm tone; new card "ALARM · out", "Accession: ACC-100002", "GATE-01 · <time> · email queued", with the simulated CCTV image naming the gate, accession and EPC |
| Notification outbox | A queued email for the gate alert |
| Audit | `gate.alarm` recorded; the event also appears in the gate-events report (§8) |

Optional (about 30 s), gate decision while Nexus is unreachable (FR 07, UJ-10):

```powershell
python device-sim\sim.py offline on
python device-sim\sim.py gate --epc E28011600000000000A10002 --direction out
python device-sim\sim.py offline off
```

Expected: `gate ALARM (offline decision): queued GatePassage (offline)`, then `offline mode OFF: replayed 1 queued event(s), 0 still queued`; the new card on the Gate monitor carries the "decided offline" badge.

## §7 AC 07: Smart-card sign-in and RBAC

**Scenario:** staff smart-card login through a mock credential provider, with role-based permissions enforced.

**Setup:** Tab 3 on the sign-in page ("Nexus sign in").

1. Tab 3 → **Tap staff card**. The button changes to "Tap your card on CARD-01…".
2. In the console:

   ```powershell
   python device-sim\sim.py tap --reader CARD-01 --uid $librarianCard
   ```

3. Show the menu, then compare it with Tab 1 (Admin).

**Expected:**

| Where | Value |
|---|---|
| Console | `202 …` |
| Tab 3 | Signed in as the librarian, landing on the Dashboard |
| Menu (Librarian) | Dashboard, Circulation desk, Catalogue, Tagging, Inventory, Gate monitor, Members, Reports, Devices, OPAC. No Migration, Audit log, Administration or System health |
| Menu (Admin, Tab 1) | All of the above plus Migration, Audit log, Administration and System health |

**Talking points:** the page waits on its own single-use challenge bound to CARD-01, so a tap only completes the sign-in that asked for it; card UIDs are never stored in the audit log. The menu only hides screens: the server checks the permission on every request. Denials (clerk to an admin endpoint, patron to the audit log, patron to another member's loans) are covered by `test_ac07_*` and by the live [security smoke checks](../06-testing/security-checks.md#2-live-smoke-checks) (18 of 18 pass).

## §8 AC 08: Dashboard and reports

**Scenario:** dashboard statistics and filterable reports for tagged items, members, circulation, operators, RFID clients and gate events.

**Setup:** Tab 2.

1. **Dashboard**: walk through the tiles, "Loans issued, last 30 days" and "Most borrowed titles".
2. **Reports** → Report "Gate events" → alarm `true` → **Apply**. Show the §6 alarm (accession `ACC-100002`) in the list, then press **CSV** and **PDF**.
3. Switch Report to "Circulation" → channel `ncip` → **Apply** to show the §3 NCIP loan. Mention the other reports in the list: Tagged items, Members, Operator activity, RFID client activity and Fines, each with From/To dates and its own filters.

**Expected (UAT run):**

| Where | Value |
|---|---|
| Dashboard tiles | Tagged items 1,391; untagged items 20,158; 300 members; 142 on loan; 100 overdue; open fines 598.00; gate alarms today 5. Values on the demo stack differ with its data |
| Gate events report | Columns include alarm, offline decision and notified; filters for dates, alarm and device code; CSV and PDF downloads |
| Exports | Contents are covered by `test_ac08_*`; CSV exports neutralise spreadsheet formulas (`test_nfr02_csv_export_neutralises_formulas`) |

## §9 AC 09: Offline install, update and rollback

**Scenario:** install and run the solution without internet access, apply an offline update and complete a documented rollback.

The recorded offline proof is the full rehearsal that ran with networking off on 2026-10-08 and took about 1 minute 40 seconds: install 1.0.0, update to 1.0.1, roll back, compare legacy fingerprints. The live demonstration uses the same scripts one release later (1.0.1 to 1.0.2). Record: [`ops/tests/ac09_offline_lifecycle.md`](../../ops/tests/ac09_offline_lifecycle.md); transcript: [`ac09-offline-transcript.txt`](../06-testing/evidence/ac09/ac09-offline-transcript.txt).

### Short live version on stack A (about 1:30)

1. Show the bundle is self-verifying (no Docker or network access is used by this step):

   ```powershell
   Expand-Archive ops\bundles\nexus-1.0.2.zip -DestinationPath $env:TEMP\nexus-verify -Force
   powershell -ExecutionPolicy Bypass -File $env:TEMP\nexus-verify\nexus-1.0.2\ops\install.ps1 -VerifyOnly
   ```

   Expected: `bundle verified`, exit code 0. A copy with one changed byte in `images.tar.gz` reports `checksum mismatch: images.tar.gz` and exits 1 (checked during the rehearsal).

2. Tab 1 → **System health** → "Software version": application 1.0.2, database revision 0004.
3. Open the transcript and walk through its steps 0–4.

### Live version on stack B (about 1:30, plus discussion)

From the installed site folder, with the network still off if it was off for the install:

```powershell
cd <site>\nexus-1.0.1
powershell -ExecutionPolicy Bypass -File ops\update.ps1 <media>\nexus-1.0.2.zip
powershell -ExecutionPolicy Bypass -File ops\rollback.ps1
```

**Expected:**

| Step | Output | Time in the 1.0.0 → 1.0.1 rehearsal |
|---|---|---|
| Update | `== updating 1.0.1 (schema 0004) to 1.0.2`; pre-update backup `nexus-1.0.1-…-pre-update-1-0-1-1-0-2.dump`; `ops\state.json` records 1.0.1 and schema 0004; `/version` reports 1.0.2, `alembic_rev` 0004 and the 1.0.2 `build_notes`; containers `nexus-api:1.0.2`, `nexus-web:1.0.2` | about 30 s |
| Roll back | `== rolling back 1.0.2 to 1.0.1 (schema 0004)`; `schema downgraded to 0004` (1.0.2 has no migration, so the downgrade changes nothing); `rolled back to 1.0.1: {"version":"1.0.1","alembic_rev":"0004","licence":"valid",...}`; containers back on 1.0.1 | about 20 s |
| Counts | bibs 2,000, items 2,377, members 300, legacy catalogue 2,000 throughout (fresh install without the §1 batch) | — |
| Legacy integrity | `IDENTICAL: 3 legacy tables, 4,677 rows` | — |

The schema stays at `0004` throughout, so show the change of release with `version` on `/version` or **System health**, not with the database revision.

Optional, about 20 s, between the update and the rollback (skip it if behind time): show that a database failure is now visible to the health check (DEF-016).

```powershell
docker compose stop db
curl.exe -k -s -o NUL -w "%{http_code}`n" https://localhost:8443/api/v1/health
docker compose start db
curl.exe -k -s -o NUL -w "%{http_code}`n" https://localhost:8443/api/v1/health
```

Expected: `503` while the database is stopped, then `200` once it is back (allow a few seconds for `db` to start). Run the rollback only after the second `200`.

If the new release is not healthy within 120 s, `update.ps1` calls `rollback.ps1` automatically. Since 1.0.2, `/health` answers 503 when the database check fails (DEF-016), so this also covers a release that starts but cannot use the database. That path was not exercised with a deliberately broken release (see [known limitations](known-limitations.md)).

## §10 AC 10: Restore and legacy integrity

**Scenario:** restore from backup after a simulated failed migration or integration change, and prove that the original data remains intact.

### Short live version (about 1:30)

Compare the legacy fingerprints taken before the demo with fingerprints taken now, after the migration, tagging, circulation, inventory and gate activity of §1–§8:

```powershell
$after = ((docker compose exec -T api python /app/ops/integrity.py snapshot --out /backups/reports --label demo-after) |
          Select-String '^report: ').Line -replace '^report: ', ''
docker compose exec -T api python /app/ops/integrity.py compare $before $after
```

Expected: `IDENTICAL: 3 legacy tables, 4,677 rows`, exit code 0.

Then show the [restore and integrity report](../05-data-migration/restore-and-integrity-report.md): 19,200 migrated items were damaged on purpose, restored from a checksum-verified backup in one transaction, and the legacy fingerprints compared IDENTICAL. Mention the layered guarantee: the application role cannot write to `legacy_ilms` at all, fingerprints detect any change, and a verified backup precedes every migration commit and update.

### Full live version (if time allows)

Stack A needs `$env:COMPOSE_FILE` from the checklist; on stack B run from `<site>`. The restore stops and restarts the web and API containers; its duration was not timed in the report.

```powershell
powershell -ExecutionPolicy Bypass -File ops\backup.ps1 -Reason pre-change
#   -> backup: /backups/nexus-<version>-<timestamp>-pre-change.dump   (and its sha256)
$pgUser = (Select-String .env -Pattern '^POSTGRES_USER=(.+)$').Matches[0].Groups[1].Value
$pgDb   = (Select-String .env -Pattern '^POSTGRES_DB=(.+)$').Matches[0].Groups[1].Value
docker compose exec -T db psql -U $pgUser -d $pgDb -c "UPDATE nexus.item SET status='withdrawn' WHERE migration_batch_id='$batch'"
powershell -ExecutionPolicy Bypass -File ops\restore.ps1 -File nexus-<version>-<timestamp>-pre-change.dump
docker compose exec -T db psql -U $pgUser -d $pgDb -c "SELECT status, count(*) FROM nexus.item WHERE migration_batch_id='$batch' GROUP BY 1"
```

Expected (report): `UPDATE 19200`; the restore verifies the checksum, restores and restarts the services ("Restore complete"; a failed restore also restarts them, DEF-019); the query shows 19,200 items `available`; a new snapshot compared with `$before` prints `IDENTICAL: 3 legacy tables, 4,677 rows`.

---

## Fallback evidence

If a live step fails, show the recorded evidence for that scenario and carry on.

| AC | Evidence |
|---|---|
| AC 01 | [`ac01-migration-batches.jpg`](../06-testing/evidence/uat/ac01-migration-batches.jpg), [migration run report](../05-data-migration/migration-run-report.md) |
| AC 02 | [`ac02-tag-associated.jpg`](../06-testing/evidence/uat/ac02-tag-associated.jpg) |
| AC 03 | [`ac03-1-issued-at-desk.jpg`](../06-testing/evidence/uat/ac03-1-issued-at-desk.jpg), [`ac03-2-renewed-and-returned.jpg`](../06-testing/evidence/uat/ac03-2-renewed-and-returned.jpg), [`ac03-3-ncip-and-sip2-loans.jpg`](../06-testing/evidence/uat/ac03-3-ncip-and-sip2-loans.jpg), [`ac03-4-audit-trail.jpg`](../06-testing/evidence/uat/ac03-4-audit-trail.jpg) |
| AC 04 | [`ac04-reference-item-refused.jpg`](../06-testing/evidence/uat/ac04-reference-item-refused.jpg) |
| AC 05 | [`ac05-1-live-sweep.jpg`](../06-testing/evidence/uat/ac05-1-live-sweep.jpg), [`ac05-2-inventory-report.jpg`](../06-testing/evidence/uat/ac05-2-inventory-report.jpg) |
| AC 06 | [`ac06-gate-alarm-cctv-email.jpg`](../06-testing/evidence/uat/ac06-gate-alarm-cctv-email.jpg), [`ac06-gate-monitor-alarm-with-cctv.jpg`](../06-testing/evidence/stage5/ac06-gate-monitor-alarm-with-cctv.jpg) |
| AC 07 | [`ac07-1-waiting-for-card-tap.jpg`](../06-testing/evidence/uat/ac07-1-waiting-for-card-tap.jpg), [`ac07-2-signed-in-by-card.jpg`](../06-testing/evidence/uat/ac07-2-signed-in-by-card.jpg) |
| AC 08 | [`ac08-dashboard.jpg`](../06-testing/evidence/uat/ac08-dashboard.jpg), [`ac08-gate-events-report.jpg`](../06-testing/evidence/uat/ac08-gate-events-report.jpg) |
| AC 09 | [offline rehearsal](../../ops/tests/ac09_offline_lifecycle.md), [offline transcript](../06-testing/evidence/ac09/ac09-offline-transcript.txt), [online dry run](../06-testing/evidence/ac09/ac09-dry-run-online-transcript.txt) |
| AC 10 | [restore and integrity report](../05-data-migration/restore-and-integrity-report.md) |

The automated acceptance suite (`pytest -m acceptance`, 83 passing) is the other fallback: [`junit-acceptance.xml`](../06-testing/junit-acceptance.xml).
