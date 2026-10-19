# Administrator Guide

This guide covers the tasks reserved for the `Admin` role in Nexus 1.0.2. Some of them have a screen; others are available only through the REST API (shown as `http` examples, all under `/api/v1`, with an Admin bearer token). See the [API guide](api-guide.md) for authentication.

| Task | Screen | API |
|---|---|---|
| Staff users (create, deactivate) | Administration | `/admin/users` |
| Change a user's role, password or smart card | — | `PATCH /admin/users/{id}` |
| Circulation policies | Administration | `/admin/policies` |
| System settings | — | `/admin/settings` |
| Devices: list | Devices | `GET /devices` |
| Devices: register, rotate key | — | `POST /devices`, `POST /devices/{code}/rotate-key` |
| NCIP agencies | — | none (database insert, see §5) |
| Data migration | Migration | `/migration/batches` |
| Audit review | Audit log | `GET /admin/audit` |
| Health and version | System health | `GET /health`, `GET /version` |
| Licence activation | — | licence file and API restart (§9) |

## 1. Roles and permissions

There are five roles. They are seeded by migration `0002_rbac_seed.py`, and there is no API or screen to create roles or change their permissions (the `admin.roles.write` permission exists but no endpoint uses it). `GET /admin/roles` lists the roles with their permissions.

| Permission | Admin | Librarian | CirculationClerk | Auditor | Patron |
|---|:-:|:-:|:-:|:-:|:-:|
| `catalog.read` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `catalog.write` | ✔ | ✔ | | | |
| `tagging.write` | ✔ | ✔ | | | |
| `members.read` | ✔ | ✔ | ✔ | ✔ | |
| `members.write` | ✔ | ✔ | | | |
| `members.block` | ✔ | ✔ | | | |
| `member.pii.read` (unmasked email and phone) | ✔ | ✔ | ✔ | | |
| `circulation.read` | ✔ | ✔ | ✔ | ✔ | |
| `circulation.checkout`, `circulation.checkin`, `circulation.renew` | ✔ | ✔ | ✔ | | |
| `fines.read` | ✔ | ✔ | ✔ | ✔ | |
| `fines.write` (pay, waive) | ✔ | ✔ | | | |
| `inventory.read` | ✔ | ✔ | | ✔ | |
| `inventory.write` | ✔ | ✔ | | | |
| `gate.read` | ✔ | ✔ | ✔ | ✔ | |
| `devices.read` | ✔ | ✔ | | ✔ | |
| `notifications.read` | ✔ | ✔ | | ✔ | |
| `reports.read` | ✔ | ✔ | | ✔ | |
| `audit.read` | ✔ | | | ✔ | |
| `migration.run` | ✔ | | | | |
| `admin.users.write`, `admin.roles.write`, `admin.policies.write`, `admin.settings.write`, `admin.devices.write`, `admin.health` | ✔ | | | | |

Notes:
- The role name in the API is `CirculationClerk` (no space).
- Patrons hold only `catalog.read`. They can still read their own loans and fines and renew their own loans, because those routes allow the member themselves (`ensure_self_or`), whatever their permissions.
- Permissions are re-read from the database on every request, so a role change or a deactivation takes effect on the user's next request.
- The menu hides screens a role cannot use, but the server enforces every permission. A refused request returns `403 {"code": "ERR_FORBIDDEN"}`.

## 2. Staff users

### Create a user (screen)

1. Open **Administration**.
2. In **New staff user**, enter a username (3 to 64 characters: letters, digits, `.`, `_`, `-`), a display name and a role (`Admin`, `Librarian`, `CirculationClerk` or `Auditor`).
3. Enter an initial password: at least 12 characters with at least one letter and one digit.
4. Optionally enter a smart-card UID (4 to 32 hexadecimal characters). It is stored in upper case and must not be assigned to another user (`CARD_IN_USE`).
5. Select **Create user**. The action is audited as `user.create`.

### Deactivate or reactivate a user (screen)

In **Staff users**, select **Deactivate** or **Activate**. A deactivated user cannot sign in by password or card, and any access token they hold stops working on the next request. Audited as `user.update`.

### Change role, password, email or card (API only)

```http
PATCH /api/v1/admin/users/{user_id}
Authorization: Bearer <admin access token>
Content-Type: application/json

{"role": "Librarian", "smartcard_uid": "<hex UID>"}
```

Accepted fields: `display_name`, `email`, `role`, `is_active`, `password` (same policy as above), `smartcard_uid`. The audit entry records which fields changed, never the values of the password.

There is no endpoint to delete a staff user; deactivate instead.

### Patron accounts

Patrons sign in with their card number and a password. The member API has no password field, so in this prototype patron passwords exist only for the members the demo seed provisions (see `ops/demo-credentials.txt`).

## 3. Circulation policies

Each member category has one policy. The seeded categories are:

| Category | Name | Loan days | Max items | Max renewals | Fine / day | Fine limit | May borrow reference |
|---|---|--:|--:|--:|--:|--:|:-:|
| `UG` | Undergraduate | 14 | 4 | 2 | 2.00 | 100.00 | no |
| `PG` | Postgraduate | 21 | 6 | 3 | 2.00 | 150.00 | no |
| `FAC` | Faculty | 60 | 15 | 5 | 0.00 | 500.00 | yes |
| `STAFF` | Library staff | 30 | 8 | 3 | 1.00 | 200.00 | no |

To change a policy:
1. Open **Administration** → **Circulation policies**.
2. Edit the values in the category's row. The **Save** button for that row becomes active.
3. Select **Save**. The change is audited as `policy.update` with the before and after values.

API equivalent: `PATCH /api/v1/admin/policies/{category_code}` with any of `loan_days` (1 to 365), `max_items` (0 to 100), `max_renewals` (0 to 20), `fine_per_day`, `fine_limit` (non-negative, two decimals), `can_borrow_reference`. Categories cannot be added or removed.

How the rules apply (the first matching rule wins), identically for the desk, NCIP and SIP2:

| Operation | Checks, in order | Refusal code |
|---|---|---|
| Check-out | member blocked | `MEMBER_BLOCKED` |
| | member expired | `MEMBER_EXPIRED` |
| | item not `available` | `ITEM_NOT_AVAILABLE` |
| | reference item and the category may not borrow reference | `ITEM_REFERENCE_ONLY` |
| | open fines greater than the fine limit | `FINE_LIMIT_EXCEEDED` |
| | open loans at or above max items | `MAX_ITEMS_REACHED` |
| Renewal | blocked, expired, fines over the limit | as above |
| | renewals already at max renewals | `MAX_RENEWALS_REACHED` |
| Check-in | no open loan for the item | `ITEM_NOT_ON_LOAN` |

A renewal extends the loan by the category's loan days from the later of now and the current due date. At check-in an overdue fine of whole days overdue × fine per day is raised, and an overdue notice is queued if `overdue_notices_enabled` is on (§7). Every refusal is audited as `circulation.refused`.

## 4. Devices and keys

The device registry and key handling are described in [device-configuration.md](device-configuration.md). In summary:
- The **Devices** screen lists devices with their online or offline state (offline when no event has arrived for 30 seconds) and, for roles with `notifications.read`, the notification outbox.
- Registering a device and rotating its key are API-only (`POST /devices`, `POST /devices/{code}/rotate-key`, permission `admin.devices.write`). The key is returned once; only its SHA-256 hash is stored.
- There is no endpoint to edit or remove a device.

### Gate behaviour to be aware of

The gate decides locally from the security bit on each tag, so it keeps working when Nexus is unreachable. Nexus does not trust that decision: it re-checks every passage against open loans. An outbound passage is an alarm unless the item is on loan or the tag belongs to a member card. This means a tag whose security bit was wrongly cleared still shows as an alarm in Nexus (gate monitor and gate-events report), which flags the tag and loan mismatch. Passages decided while Nexus was unreachable are marked "decided offline". On every alarm Nexus takes a snapshot from the camera named in the gate's `config.camera` (mock), queues a `gate_alert` email to `gate_alert_recipients` and records `gate.alarm` in the audit log.

## 5. NCIP agencies

External systems (self-check kiosks, partner ILMS) call `POST /api/v1/ncip` with an `X-Agency-Key` header. Agencies are stored in `nexus.agency` with the SHA-256 hash of their key. Release 1.0.2 has no API, screen or seed step for agencies, so an operator adds one directly in the database with the owner role:

```sh
docker compose exec db psql -U nexus_owner -d nexus -c \
  "INSERT INTO nexus.agency (code, name, api_key_hash) VALUES ('KIOSK-01', 'Self-check kiosk', encode(sha256('<new random key>'::bytea), 'hex'));"
```

Generate the key with a random generator, hand it to the agency out of band, and do not keep it in shell history. This insert is not recorded in the application audit log. To revoke an agency, delete its row.

The SIP2 listener has no agency keys; it is restricted by IP address (`SIP2_ALLOWED_HOSTS`). An empty list refuses every connection. See the [API guide](api-guide.md#9-sip2).

## 6. Migrations

Spreadsheet migration (AC 01) is reserved for Admin (`migration.run`). The full procedure, rules and evidence are in the [migration package](../05-data-migration/README.md). On the **Migration** screen:

1. **Upload a spreadsheet (.xlsx or .csv)**, then select **Stage**. Files are limited to `UPLOAD_MAX_MB` (25 MB by default) and 100,000 rows, and must have the expected columns. Every row is stored unchanged in `staging.import_row`.
2. Select **Validate (dry run)**. Nothing is written to the catalogue. The tiles show source, valid, rejected, duplicate, likely-duplicate and committed counts, the rejections by reason, and whether `source = valid + rejected + duplicate` balances.
3. Select **Row-level report (CSV)** to review the rejected and duplicate rows.
4. Select **Commit** and confirm. Nexus first checks that the counts still reconcile (`source = valid + rejected + duplicate`, and the number of staged valid rows equals the valid count). If not, the commit is refused with `409 BATCH_NOT_BALANCED` before anything is backed up or written (since 1.0.2, DEF-021); validate the batch again. Nexus then takes a verified `pg_dump` backup, fingerprints the legacy tables, inserts all valid rows in one transaction tagged with the batch id, and fingerprints the legacy tables again. If legacy data changed, the commit is aborted (`LEGACY_CHANGED`). The backup file name is shown after the commit.
5. If needed, select **Roll back batch**. This deletes only the bibs and items carrying that batch id.

Each step is audited (`migration.stage`, `migration.validate`, `migration.commit`, `migration.rollback`). A batch can only be validated while `staged` or `validated` (`BATCH_LOCKED` otherwise), committed when `validated` (`BATCH_NOT_VALIDATED`) and balanced (`BATCH_NOT_BALANCED`), and rolled back when `committed` (`BATCH_NOT_COMMITTED`).

For large files the command-line client avoids browser time-outs:

```sh
python migration/nexus_migrate.py --file migration/samples/library-export-20k.xlsx --ca ops/nginx/certs/nexus.crt
python migration/nexus_migrate.py --file migration/samples/library-export-20k.xlsx --commit --ca ops/nginx/certs/nexus.crt
python migration/nexus_migrate.py --report <batch-id> --csv rejected.csv
python migration/nexus_migrate.py --rollback <batch-id>
```

It signs in as `--user` (default `admin`) and prompts for the password, or reads it from `NEXUS_PASSWORD`. The API defaults to `https://localhost:8443`.

To prove legacy data is untouched after a migration or restore (AC 10):

```sh
docker compose exec api python /app/ops/integrity.py snapshot --label before
# ... migration or restore ...
docker compose exec api python /app/ops/integrity.py snapshot --label after
docker compose exec api python /app/ops/integrity.py compare <before-file> <after-file>
```

## 7. Settings

Five settings exist. Each has a validator; any other key is refused with `SETTING_UNKNOWN`, and a bad value with `SETTING_INVALID`. There is no settings screen in 1.0.2, so settings are read and written through the API with `admin.settings.write`.

| Key | Value | Default when unset | Used by |
|---|---|---|---|
| `gate_alert_recipients` | list of up to 20 email addresses | `["security@example.org"]` | Recipients of the `gate_alert` email queued on every gate alarm |
| `overdue_notices_enabled` | `true` / `false` | `true` | Whether check-in of an overdue item queues an `overdue_notice` to the member (email, SMS or print, by the member's preferences) |
| `library_name` | text, up to 200 characters | — | Stored only. The patron-card PDF and SIP2 responses use the fixed name "Nexus Library" |
| `ui_banner` | text, up to 200 characters | — | Stored only. No screen displays it in 1.0.2 |
| `maintenance_notice` | text, up to 200 characters | `""` (seeded by migration `0004`) | Stored and returned by `GET /admin/settings`. No screen displays it in 1.0.2 |

Read all settings:

```http
GET /api/v1/admin/settings
Authorization: Bearer <admin access token>
```

Change one:

```http
PUT /api/v1/admin/settings/gate_alert_recipients
Authorization: Bearer <admin access token>
Content-Type: application/json

{"value": ["security@example.org", "duty-manager@example.org"]}
```

```http
PUT /api/v1/admin/settings/maintenance_notice
Content-Type: application/json

{"value": "Nexus will be updated on Saturday from 08:00; the desk will use offline procedures."}
```

The response is `{"<key>": <value>}`. Each change is audited as `setting.update` (the key, not the value). Rolling back from 1.0.1 to 1.0.0 removes `maintenance_notice` and leaves the other settings as they are. Rolling back from 1.0.2 to 1.0.1 changes no settings.

## 8. Audit review

Every administrative change, circulation event, fine change, tagging action, migration step, sign-in and gate alarm is written to `nexus.audit_log`. The application role can only insert into and read that table, so entries cannot be edited or deleted through Nexus. Personal values in details (email, phone, names, card UIDs) are masked, and failed sign-ins record only the username length.

On the **Audit log** screen (Admin and Auditor):
1. Enter the start of an action name in **Action starts with**, for example `circulation.` or `auth.login.failure`.
2. Optionally set **From** and **To** dates.
3. Select **Filter**. Results are newest first, 50 per page; use **Previous** and **Next**.

The API also filters by actor and entity: `GET /api/v1/admin/audit?actor_id=<uuid>&entity_id=<id>&action=<prefix>&from=YYYY-MM-DD&to=YYYY-MM-DD&page=1&size=50` (size up to 200).

Actions recorded in 1.0.2:

| Area | Actions |
|---|---|
| Sign-in | `auth.login.success`, `auth.login.failure`, `auth.logout`, `auth.card.tap` |
| Administration | `user.create`, `user.update`, `policy.update`, `setting.update`, `device.register`, `device.rotate_key` |
| Catalogue and tagging | `bib.create`, `bib.update`, `item.create`, `tag.associate`, `tag.retire` |
| Members | `member.create`, `member.update`, `member.block`, `member.unblock` |
| Circulation and fines | `circulation.checkout`, `circulation.renew`, `circulation.checkin`, `circulation.refused`, `fine.raise`, `fine.paid`, `fine.waived` |
| Inventory and gate | `inventory.start`, `inventory.close`, `inventory.mark_missing`, `gate.alarm` |
| Migration | `migration.stage`, `migration.validate`, `migration.commit`, `migration.rollback`, `legacy.mirror` (seed) |

Each entry also records the client IP address. Since 1.0.2 (DEF-015) this is the address nginx received the connection from; a client cannot set it with an `X-Forwarded-For` header. With Docker port publishing on a development host, that address is the Docker gateway (such as `172.18.0.1`) for every client.

Circulation entries carry the channel (`ui`, `ncip`, `sip2`), item accession number and member card number. NCIP and SIP2 entries have actor type `external` and no actor id: the audit log does not record which agency or SIP2 client made the call.

Suggested routine checks:
- `auth.login.failure` bursts from one IP (also limited to 10 attempts a minute per client).
- `circulation.refused` volumes by code, to spot policy problems.
- `user.update` and `setting.update` entries, against change requests.
- `gate.alarm` entries, against the gate-events report.

## 9. Licence activation

Outside development (`ENVIRONMENT` other than `dev` or `test`) Nexus checks a signed licence file when the API starts:
- The file is `licence/licence.json` in the installation folder, mounted read-only into the API container at `/app/licence/licence.json` (`LICENCE_FILE`).
- It is `{site, expires, features, sig}`, where `sig` is HMAC-SHA256 over the other fields, keyed with `LICENCE_KEY` from `.env`.
- The status is `valid`, `missing`, `invalid` (bad signature, bad JSON or no `expires`) or `expired`. It is shown on **System health** and in `GET /api/v1/version` as `licence`.

When the status is not `valid`, the installation is **read-only for everyone except administrators**:
- `GET`, `HEAD` and `OPTIONS` requests work.
- Everything under `/api/v1/auth/` works, so everyone can still sign in, refresh and sign out.
- Any other change (`POST`, `PUT`, `PATCH`, `DELETE`) is refused with `403 {"code": "LICENCE_REQUIRED", "licence": "<status>"}` unless the bearer token carries the `Admin` role. This includes device events and NCIP calls, which carry no bearer token.
- WebSocket connections are not affected.

The status is read only at start-up. A licence that expires while the API is running keeps working until the next restart; a licence copied in by hand takes effect only after a restart. Since 1.0.2 (DEF-020) the installer restarts the API itself whenever it installs or issues a licence.

To activate:
1. Obtain a licence file issued for the site with the site's `LICENCE_KEY`. For the prototype the issuing tool is `ops/licence.py` (HMAC, so whoever holds the key can issue licences; production would use an asymmetric signature):
   ```sh
   python ops/licence.py issue --site "Central Library" --expires 2027-12-31 --key-file site.key --out licence.json
   ```
2. Copy it to `licence/licence.json` in the installation folder. At install time, pass the licence and the key it was signed with instead: `ops\install.ps1 -Licence <file> -LicenceKeyFile <key file>` (`ops/install.sh --licence <file> --licence-key-file <key file>`). The installer writes the key to `LICENCE_KEY` in `.env`, installs the file and restarts the API, so step 4 is not needed; its final `version:` line shows the licence status.
3. Check the signature against the key the API uses:
   ```sh
   docker compose exec api python /app/ops/licence.py verify /app/licence/licence.json
   ```
4. Restart the API: `docker compose restart api`.
5. Confirm `licence` is `valid` on **System health** or with `GET /api/v1/version`.

`ops\install.ps1 -Demo` issues a 30-day demonstration licence automatically. In development (`docker-compose.dev.yml`, `ENVIRONMENT=dev`) the licence is reported but not enforced.

## 10. Health and version

**System health** (Admin) shows the health checks and the version. The same data is public:

```http
GET /api/v1/health     -> {"status": "ok" | "degraded", "checks": {"database": true}}
GET /api/v1/version    -> {"version": "1.0.2", "alembic_rev": "0004", "licence": "valid", "build_notes": "..."}
```

`/health` answers HTTP 200 when every check passes and HTTP 503 with `"status": "degraded"` when any check fails (since 1.0.2, DEF-016). The Docker health check and the update's automatic rollback read the status code. The only check in 1.0.2 is the database.

The **System health** screen does not display the body of a 503 answer. Opened while a check fails, it shows the overall badge as not ok with no checks listed; left open when a check starts failing, it keeps showing the last successful result. Use `docker compose ps` (`api` becomes `unhealthy`) or request `/api/v1/health` directly to see the current state. For backups, restore, update and rollback see the [troubleshooting runbook](troubleshooting-runbook.md) and the offline lifecycle rehearsal ([`ops/tests/ac09_offline_lifecycle.md`](../../ops/tests/ac09_offline_lifecycle.md)).
