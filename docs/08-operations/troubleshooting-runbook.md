# Troubleshooting Runbook

Symptom → check → fix procedures for Nexus 1.0.2 on a Docker Compose installation. Run the commands from the installation folder (the folder with `docker-compose.yml` and `.env`). Shell examples work in PowerShell and in a POSIX shell unless marked.

Before changing anything that touches data, take a backup (`ops\backup.ps1` or `sh ops/backup.sh`).

## Contents

0. [Collecting diagnostics](#0-collecting-diagnostics)
1. [API unhealthy](#1-api-unhealthy)
2. [Database down](#2-database-down)
3. [API refuses to start: "Insecure configuration"](#3-api-refuses-to-start-insecure-configuration)
4. [Device offline](#4-device-offline)
5. [Gate events not arriving](#5-gate-events-not-arriving)
6. [Outbox stuck](#6-outbox-stuck)
7. [Migration failed](#7-migration-failed)
8. [Update failed](#8-update-failed)
9. [Licence invalid](#9-licence-invalid)
10. [Certificate expired](#10-certificate-expired)
11. [Operator scripts on a development stack](#11-operator-scripts-on-a-development-stack)

## 0. Collecting diagnostics

```sh
docker compose ps                                  # state and health of db, api, web
docker compose logs --tail 200 api                 # JSON log lines; personal data is masked
docker compose logs --tail 100 web db
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health').read().decode())"
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/version').read().decode())"
```

`/health` returns `{"status": "ok" | "degraded", "checks": {"database": true | false}}`. Since 1.0.2 (DEF-016) it answers HTTP 200 only when every check passes and **HTTP 503** when any fails, so the Docker health check marks `api` `unhealthy` after its retries (12 checks, 10 s apart) and the update's automatic rollback sees the failure. With a 503 the `urlopen` command above fails with `HTTP Error 503: Service Unavailable` instead of printing the body; request `https://<host>:<HTTPS_PORT>/api/v1/health` from a browser or with `curl -k` to read it. `/version` returns the release, the database revision (`alembic_rev`, `0004` for 1.0.2) and the licence status.

API error responses never contain internal details; an `ERR_INTERNAL` response means the cause is in the API log.

## 1. API unhealthy

**Symptoms:** `docker compose ps` shows `api` as `unhealthy`, `starting` or exited; `install`, `update` or `rollback` prints "API not healthy after N s"; the browser gets `502 Bad Gateway`; `web` does not start (it waits for a healthy `api`).

| Check | Command | What it tells you |
|---|---|---|
| Container state | `docker compose ps api` | Exited means start-up failed |
| Start-up log | `docker compose logs --tail 100 api` | The container runs `alembic upgrade head` then uvicorn; the first error line is usually the cause |
| Configuration guard | Look for `Insecure configuration` in the log | See [§3](#3-api-refuses-to-start-insecure-configuration) |
| Database | `docker compose ps db` | `api` starts only after `db` is healthy, and a running `api` turns `unhealthy` when it cannot reach the database; see [§2](#2-database-down) |
| Migration failure | Look for `alembic` errors in the log | Schema upgrade failed; see [§8](#8-update-failed) |

**Fixes:**
1. Fix the cause shown in the log.
2. Start the stack again: `docker compose up -d`.
3. Wait for `api` to show `healthy`, then confirm `/health` reports `ok`.

Since 1.0.2 (DEF-018) `db`, `api` and `web` have `restart: unless-stopped`: after a crash, a host reboot or a Docker restart they start again by themselves, as long as Docker itself starts. Containers stopped with `docker compose stop` stay stopped until `docker compose up -d` or `docker compose start` is run. Docker restarts a container that exits; it does not restart one that is running but `unhealthy`.

## 2. Database down

**Symptoms:** `/health` answers `503` with `"status": "degraded"` and `"database": false`; `docker compose ps` shows `api` as `unhealthy` after about two minutes; screens fail with "Internal Server Error"; the API log has `database health check failed`.

**Checks:**
1. `docker compose ps db` (should be `healthy`).
2. `docker compose logs --tail 100 db` (disk full, permission or corruption messages).
3. `docker compose exec db pg_isready -U nexus_owner -d nexus`.
4. Free disk space on the host and `docker system df`.

**Fixes:**
1. Start the database: `docker compose up -d db`. The API reconnects by itself (pooled connections are checked before use); a restart is not needed. `/health` answers `200` again and `api` returns to `healthy` at the next successful check.
2. If the volume is full, free space on the host, then start `db` again.
3. If the database cannot start or its data is damaged, restore the newest verified backup:
   ```powershell
   docker compose exec api python -m nexus_ops.backup list
   .\ops\restore.ps1 -File <backup-file-name>
   ```
   ```sh
   sh ops/restore.sh <backup-file-name>
   ```
   The restore stops `web` and `api`, refuses a dump whose SHA-256 does not match, and starts them again, also when the restore fails (the shell script then prints `Restore FAILED (exit <n>)`, DEF-019). Afterwards run `docker compose exec api python /app/ops/integrity.py snapshot` and compare it with an earlier snapshot to prove legacy data is unchanged (AC 10).

## 3. API refuses to start: "Insecure configuration"

**Symptom:** the API exits at start-up with:

```text
Insecure configuration for environment 'production': JWT_SECRET must be a generated value of at least 32 characters; DATABASE_URL uses a development or placeholder password
```

This is the guard added for DEF-009. Outside `ENVIRONMENT=dev` or `test` (the image defaults to `production`), the API refuses to start when:
- `JWT_SECRET` or `LICENCE_KEY` starts with `dev-` or `replace`, or is shorter than 32 characters;
- the password in `DATABASE_URL` or `OWNER_DATABASE_URL` is a development password (`devapp`, `devowner`) or starts with `replace`.

The message names the settings only, never their values.

**Fixes:**
- **Production install:** `ops\install.ps1` (or `install.sh`) generates a `.env` with new random secrets when none exists. If `.env` was copied from `.env.example` by hand, replace every `replace-...` value with a generated one (for example 32 random bytes as hex), keeping `DATABASE_URL`/`OWNER_DATABASE_URL` consistent with `NEXUS_APP_PASSWORD`/`POSTGRES_PASSWORD`. Changing the database passwords after the database volume was created also needs the roles' passwords changed in PostgreSQL.
- **Development stack:** include the development override, which sets `ENVIRONMENT=dev`:
  ```sh
  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
  ```
  Never use the override on a production host.

## 4. Device offline

**Symptom:** **Devices** shows a device as `offline`. A device is offline when no event of any kind has arrived for 30 seconds.

**Checks:**
1. Is the device sending anything? For the simulator, run `python device-sim/sim.py heartbeat --device HH-01` and read the reply.
2. Read the status code in the reply:

| Reply | Meaning | Fix |
|---|---|---|
| `202 {"status": "accepted"}` | Working; the device just was not sending | Configure regular heartbeats (every 10 to 20 s) |
| `401 ERR_DEVICE_AUTH` | Wrong key, or the key was rotated | Install the current key; rotate it if unknown ([device configuration §3](device-configuration.md#3-rotate-a-device-key)) |
| `403 LICENCE_REQUIRED` | Installation unlicensed: device events are refused | See [§9](#9-licence-invalid) |
| `422 DEVICE_TYPE_MISMATCH` | The event's `device_type` differs from the registration | Correct the device's type; in the simulator, use the code prefix that matches the type |
| `429 ERR_RATE_LIMIT` | Over 600 events a minute from one address | Slow the device down or raise `RATE_LIMIT_DEVICES` |
| `No key for device ...` (simulator) | The simulator has no key for that code | Set `SIM_DEVICE_KEYS`, or re-seed the demo |
| Connection or certificate error | Network, TLS or `SIM_API` | Check `SIM_API`, `SIM_CA_FILE` and the certificate ([§10](#10-certificate-expired)) |

`CAM-01` and `PRN-01` are always offline in the prototype because nothing sends events for them, and `heartbeat --all` gets `422` for them. Both are expected.

Rate limits count per client address, which is the address nginx sees (DEF-015). With Docker port publishing on a development host that is the Docker gateway (such as `172.18.0.1`) for every client, so all devices and staff on such a host share one counter and can reach a limit together.

A SIP2 kiosk whose connection is closed without an answer is not in `SIP2_ALLOWED_HOSTS`. Since 1.0.2 (DEF-017) an empty list refuses every connection. The API log has `SIP2 connection refused from <address>` for each attempt, and `SIP2_ALLOWED_HOSTS is empty: every SIP2 connection will be refused` at start-up when the list is empty. Add the address from the log line to the list and run `docker compose up -d`.

## 5. Gate events not arriving

**Symptom:** a test passage through `GATE-01` produces no card on **Gate monitor** and no row in the gate-events report.

**Checks, in order:**
1. **Simulator offline mode.** `python device-sim/sim.py gate --epc <EPC>` printing `queued GatePassage (offline)` means offline mode is on. `python device-sim/sim.py offline off` replays the queue.
2. **Reply code.** Anything other than `202` or `200 duplicate` is covered in [§4](#4-device-offline). Since 1.0.2 (DEF-022) the simulator keeps events answered `401`, `403`, `429` or `5xx` in its queue, in order, and stops the replay there: fix the cause and run `offline off` again. Events answered with any other `4xx` (for example `422`) are dropped with `dropping queued <type>: Nexus rejected it with <status>`, because they will never be accepted.
3. **Duplicate.** `200 {"status": "duplicate"}` means that `event_id` was already received. Each simulator command generates a new id; a bridge that reuses ids will see this.
4. **Not an alarm.** Nexus raises an alarm for every outbound passage unless the tag's item is on loan or the tag is a member card; an unknown EPC going out is an alarm with "unknown tag". Inbound passages, items on loan and member cards create events that are not alarms, and **Gate monitor** shows alarms only by default: clear **Alarms only**. The `security_bit` sent by the gate is not used for the decision.
5. **Live feed.** The alarm banner and tone need the WebSocket `/api/v1/ws/live`. If the page shows events only after a refresh, check that nginx passes WebSocket upgrades (`location /api/` in `ops/nginx/default.conf.template`) and that the user has `gate.read`. The page also polls every 15 seconds.
6. **Server side.** `docker compose logs --tail 100 api` for handler errors (`device event ... rejected by handler`).

## 6. Outbox stuck

The outbox worker runs inside the API process (`RUN_WORKER`, on by default) every 5 seconds. It sends queued messages through the configured adapter, retries failures after 2, 4, 8 and 16 seconds, and marks a message `failed` after 5 attempts. The mock adapters write `.eml`, `.txt` and `.pdf` files into the `outbox` volume (`/app/outbox/<channel>`) instead of sending anything.

**Symptoms:** **Devices** → **Notification outbox** shows messages staying `queued`, or `failed` with an error; the gate monitor says "email queued" but no file appears.

**Checks:**
1. List messages by status:
   ```http
   GET /api/v1/notifications/outbox?status=queued
   GET /api/v1/notifications/outbox?status=failed
   ```
   `last_error` gives the adapter's reason.
2. `docker compose logs --tail 200 api | grep -i "worker\|adapter"` (PowerShell: `| Select-String "worker|adapter"`).
3. Check `.env` for an adapter name that does not exist (`ADAPTER_EMAIL`, `ADAPTER_SMS`, `ADAPTER_PRINT`: only `mock` exists in 1.0.2) and for `MOCK_EMAIL_FAIL_FIRST`, which makes the mock email fail its first N sends on purpose.
4. Check the outbox volume is writable: `docker compose exec api ls -l /app/outbox`.

**Fixes:**
1. Correct the adapter configuration and restart the API (`docker compose restart api`). Queued messages are then delivered on the next tick.
2. There is no API to re-queue `failed` messages in 1.0.2. If they must still be sent, re-queue them in the database with the owner role, after a backup:
   ```sh
   docker compose exec db psql -U nexus_owner -d nexus -c \
     "UPDATE nexus.notification_outbox SET status = 'queued', attempts = 0, next_attempt_at = now() WHERE status = 'failed';"
   ```
   This change is not recorded in the application audit log; record it in the change log.

## 7. Migration failed

| Symptom | Cause | Fix |
|---|---|---|
| `413 UPLOAD_TOO_LARGE` | File over `UPLOAD_MAX_MB` (25 MB; nginx also limits bodies to 25 MB) | Split the file, or raise both limits |
| `422 UPLOAD_TYPE_INVALID`, `UPLOAD_UNREADABLE`, `UPLOAD_EMPTY` | Not an .xlsx or .csv, damaged workbook, or no header row | Re-export from the source system |
| `422 UPLOAD_COLUMNS_MISSING` | Columns differ from the export layout | Compare with `backend/app/services/migration/mapping.yaml` |
| `422 UPLOAD_TOO_MANY_ROWS` | More than 100,000 rows | Split into batches |
| `429 ERR_RATE_LIMIT` | More than 10 uploads a minute | Wait a minute |
| `409 BATCH_NOT_VALIDATED` | Commit before validation | Run **Validate (dry run)** first |
| `409 BATCH_NOT_BALANCED` | The counts do not reconcile at commit time (`source ≠ valid + rejected + duplicate`, or the staged valid rows differ from the valid count). Checked before the backup (DEF-021) | Nothing was changed. Run **Validate (dry run)** again and check the reconciliation before committing |
| `409 BATCH_LOCKED` | Re-validating a committed, rolled-back or failed batch | Stage the file again as a new batch |
| Reconciliation "NOT balanced" | `source ≠ valid + rejected + duplicate` | Do not commit (a commit is refused with `BATCH_NOT_BALANCED`); download the row-level CSV and investigate |
| `500 ERR_INTERNAL` on commit | Usually the pre-commit backup failed (`pg_dump failed` in the API log) | Check the backups volume has space and the owner credentials in `.env`; nothing was inserted |
| `500 LEGACY_CHANGED` | Legacy fingerprints differed during the commit | The transaction was rolled back; nothing was inserted. Find what changed `legacy_ilms` before retrying |
| Browser times out on a large commit | Long request through the browser | Use `migration/nexus_migrate.py` (900 s timeout) |

After any failed or doubtful commit:
1. Check the batch status on **Migration** → **Recent batches**.
2. If a batch was committed but should not have been, select **Roll back batch** (deletes only that batch's bibs and items).
3. If more than the batch is affected, restore the backup named in the commit report (`pre-migration-<batch id>`) as in [§2](#2-database-down).
4. Prove legacy data is unchanged with `integrity.py compare`.

## 8. Update failed

The update scripts (`ops\update.ps1 <bundle.zip|folder>`, `ops/update.sh`) verify the bundle, take a backup, record the current release in `ops/state.json`, load the new images and start them. If the new release is not healthy within 120 seconds they run the rollback script automatically.

| Message | Meaning | Fix |
|---|---|---|
| `Update bundle verification FAILED: nothing was changed.` | A file is missing or its SHA-256 differs from `SHA256SUMS` | Obtain a new copy of the bundle |
| `already at <version>` | `.env` `NEXUS_VERSION` already equals the bundle's version | Nothing to do |
| `backup failed: nothing was changed` | The pre-update backup did not complete | Check the backups volume and the API log, then retry |
| `<version> is not healthy: rolling back to <previous>` | The new release did not become healthy | The rollback runs automatically; read `docker compose logs api` from the failed start to find the cause |
| `docker load failed` | Image archive unreadable | Re-copy the bundle; check disk space |

To roll back by hand after an update that did start (for example a functional problem found later):

```powershell
powershell -ExecutionPolicy Bypass -File ops\rollback.ps1
```

```sh
sh ops/rollback.sh
```

The rollback:
1. stops `web` and `api`;
2. downgrades the schema with the newer image to the revision recorded in `ops/state.json`;
3. restores the previous compose file and `NEXUS_VERSION`;
4. if the schema downgrade failed, restores the backup taken before the update instead;
5. starts the previous release, waits for it to be healthy, and renames `ops/state.json` to `ops/state-rolled-back-<time>.json`.

`no ops\state.json: nothing to roll back` means no update was recorded. Confirm the result with `/version` (1.0.0 has `alembic_rev` `0003`; 1.0.1 and 1.0.2 both have `0004`, so after a rollback from 1.0.2 check `version`, not the revision). The rehearsal of this path is in [`ops/tests/ac09_offline_lifecycle.md`](../../ops/tests/ac09_offline_lifecycle.md).

## 9. Licence invalid

**Symptoms:** non-administrators get `403 LICENCE_REQUIRED` ("This installation is not activated … read-only") on every change; devices and NCIP clients are refused the same way; **System health** shows the licence as `missing`, `invalid` or `expired`; the API log has `licence <status>: the API is read-only for non-administrators`.

**Checks:**
1. `GET /api/v1/version` → `licence`.
2. The file exists: `docker compose exec api ls -l /app/licence/` (host folder `licence/`).
3. The signature matches the key the API uses:
   ```sh
   docker compose exec api python /app/ops/licence.py verify /app/licence/licence.json
   ```

| Status | Cause | Fix |
|---|---|---|
| `missing` | No `licence/licence.json` | Copy the site's licence file there |
| `invalid` | Not JSON, no `expires`, or the signature does not match `LICENCE_KEY` (file edited, or issued with a different key, or `LICENCE_KEY` regenerated in `.env`) | Obtain a licence issued with this site's `LICENCE_KEY`, or restore the original `LICENCE_KEY` |
| `expired` | `expires` is before today | Obtain a renewed licence |

After replacing the file, restart the API (`docker compose restart api`): the status is read only at start-up. Installing the licence with the installer (`-Licence` / `--licence`) restarts the API itself since 1.0.2 (DEF-020). A licence issued before installation reports `invalid` unless it was installed with the key it was signed with (`-LicenceKeyFile` / `--licence-key-file`). Administrators can still sign in and work while the licence is invalid. The full procedure is in the [administrator guide](administrator-guide.md#9-licence-activation).

## 10. Certificate expired

nginx serves `ops/nginx/certs/nexus.crt` and `nexus.key`, generated at install as a self-signed certificate valid for 825 days (CN `nexus.local`, with `localhost`, `nexus.local` and `127.0.0.1` as alternative names). Production sites should use their own PKI.

**Symptoms:** browsers warn that the certificate has expired; the simulator, `nexus_migrate.py` or other clients fail with certificate verification errors.

**Check:**

```sh
openssl x509 -enddate -noout -in ops/nginx/certs/nexus.crt
```

**Fix:**
1. Move the old `nexus.crt` and `nexus.key` out of `ops/nginx/certs/` (the generator does nothing while a certificate exists).
2. Install the site's certificate and key under those names, or generate a new self-signed pair with `sh ops/nginx/gen-cert.sh` (needs `openssl` on the host; `install.ps1` instead runs `openssl` from the API image).
3. Restart nginx: `docker compose restart web`.
4. Distribute the new certificate to clients that pin it: `SIM_CA_FILE` for the simulator, `--ca` for `nexus_migrate.py`, and the browsers' trust stores for a self-signed certificate.

## 11. Operator scripts on a development stack

A development stack is started with the override `docker-compose.dev.yml`, which publishes PostgreSQL on `localhost:5433` and sets `ENVIRONMENT=dev`. `ops/backup.*` and `ops/restore.*` call plain `docker compose`, which reads only `docker-compose.yml` unless told otherwise. On a development stack the API they start then runs in production mode and refuses the development `.env` ([§3](#3-api-refuses-to-start-insecure-configuration)).

**Fix:** include the override through `COMPOSE_FILE` for those commands, as the [README](../../README.md#quality-checks) describes:

```sh
COMPOSE_FILE="docker-compose.yml;docker-compose.dev.yml" sh ops/restore.sh <backup-file-name>   # Git Bash on Windows
COMPOSE_FILE="docker-compose.yml:docker-compose.dev.yml" sh ops/restore.sh <backup-file-name>   # Linux and macOS
```

```powershell
$env:COMPOSE_FILE = "docker-compose.yml;docker-compose.dev.yml"
.\ops\restore.ps1 -File <backup-file-name>
Remove-Item Env:COMPOSE_FILE
```

`install`, `update` and `rollback` always pass `-f docker-compose.yml` explicitly, so `COMPOSE_FILE` does not affect them; they are meant for bundle installations, not for development stacks.
