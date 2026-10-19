# Backup and Restore

Nexus takes logical backups of the whole `nexus` database (schemas `legacy_ilms`, `nexus` and `staging`) with `pg_dump`, and restores them with `pg_restore` in a single transaction. Every backup has a SHA-256 checksum file, and a restore refuses a backup whose checksum is missing or does not match. The restore procedure and its integrity proof were rehearsed for AC 10 ([restore and integrity report](../05-data-migration/restore-and-integrity-report.md)).

All commands below are run from the installation folder with the stack running.

## 1. What is backed up

| Item | In the backup | Where it lives |
|---|---|---|
| Database (all schemas, data, migration revision) | Yes | Volume `nexus_pgdata` |
| `.env` (secrets) | No | Installation folder |
| Licence | No | `licence/licence.json` |
| TLS certificate and key | No | `ops/nginx/certs/` |
| Mock notification outbox | No | Volume `nexus_outbox` |

Keep a protected copy of `.env`, `licence/` and `ops/nginx/certs/` with the off-host backups. Database roles and their passwords are not in the dump; they are created when the database volume is first initialised.

## 2. Backup files

- Folder: `/backups` in the API container, which is the Docker volume `nexus_backups`.
- Name: `nexus-<version>-<UTC timestamp>-<reason>.dump`, for example `nexus-1.0.0-20261007T145907Z-pre-change.dump`. The reason is reduced to letters, digits, `-` and `_`, and at most 60 characters.
- Format: PostgreSQL custom format (`pg_dump -Fc`).
- Checksum: `<name>.dump.sha256`, in `sha256sum` format.

Backups are also taken automatically:

| When | Reason in the file name |
|---|---|
| Before every migration batch commit | `pre-migration-<batch id>` |
| Before every update (`ops/update.ps1` / `update.sh`) | `pre-update-<from>-<to>` |

Nothing deletes old backups. Remove old files from the volume as part of the retention routine.

## 3. Schedule recommendation

| Backup | When | Keep |
|---|---|---|
| Scheduled | Daily, outside opening hours | 14 daily copies on the host; copy each one off the host |
| Before planned change | Before bulk edits, configuration changes or a migration outside the importer | Until the change is accepted |
| Before update | Automatic | Until the new release is accepted |
| Integrity baseline | After installation, after each migration batch and after each restore | With the backups |

Windows (Task Scheduler, run as an account that can use Docker):

```powershell
schtasks /Create /SC DAILY /ST 01:00 /TN "Nexus backup" /TR "powershell -ExecutionPolicy Bypass -File C:\Nexus\nexus-1.0.0\ops\backup.ps1 -Reason scheduled"
```

Linux (crontab of an account in the `docker` group):

```sh
0 1 * * * sh /opt/nexus/nexus-1.0.0/ops/backup.sh scheduled
```

These are recommendations. Retention and off-host copying are not automated in 1.0.x.

## 4. Taking a backup

```powershell
ops\backup.ps1 -Reason pre-change
```

```sh
sh ops/backup.sh pre-change
```

The reason is optional (default `manual`). The script runs `python -m nexus_ops.backup create` in the API container and prints the backup path and its SHA-256:

```
backup: /backups/nexus-1.0.0-20261007T145907Z-pre-change.dump
sha256: b16adfc1...
```

A failed `pg_dump` deletes the partial file and exits with an error.

List the backups:

```sh
docker compose exec api python -m nexus_ops.backup list
```

### Copying backups off the host

Copy each dump **with** its `.sha256` file:

```sh
docker compose cp api:/backups/nexus-1.0.0-20261007T145907Z-pre-change.dump D:/nexus-backups/
docker compose cp api:/backups/nexus-1.0.0-20261007T145907Z-pre-change.dump.sha256 D:/nexus-backups/
```

To restore a copy kept off the host, copy both files back into `/backups` the same way (`docker compose cp <file> api:/backups/`).

`docker compose down -v` deletes the `nexus_backups` volume together with the database. Off-host copies are the only protection against that.

## 5. Verifying a backup

The checksum is verified automatically before every restore. To check a backup without restoring it:

```sh
docker compose exec api sh -c "cd /backups && sha256sum -c nexus-1.0.0-20261007T145907Z-pre-change.dump.sha256"
```

Expected: `nexus-1.0.0-20261007T145907Z-pre-change.dump: OK`. Check off-host copies the same way with `sha256sum -c` on Linux, or by comparing `Get-FileHash -Algorithm SHA256 <file>` with the value in the `.sha256` file on Windows.

## 6. Restoring a backup

A restore replaces the whole database with the backup, including Nexus data changed since it was taken. Take a backup of the current state first if it may be needed.

1. Take an integrity snapshot of the current legacy data ([section 7](#7-integrity-check)) with the label `before`.
2. Run the restore with the backup's file name:

   ```powershell
   ops\restore.ps1 -File nexus-1.0.0-20261007T145907Z-pre-change.dump
   ```

   ```sh
   sh ops/restore.sh nexus-1.0.0-20261007T145907Z-pre-change.dump
   ```

   The script:

   1. stops `web` and `api`, so no session writes during the restore
   2. runs `python -m nexus_ops.backup restore <file> --yes` in a one-off API container
   3. verifies the checksum and refuses the file if it is missing or does not match
   4. fingerprints the legacy tables, closes other database sessions, runs `pg_restore --clean --if-exists --single-transaction`, and fingerprints the legacy tables again
   5. prints `restored <file> (closed <n> other session(s))` and `{"legacy_tables_changed_by_restore": [...]}`
   6. starts `api` and `web` again

3. Check the service and the data:

   ```sh
   docker compose ps
   docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health').read().decode())"
   ```

   Expected: `{"status":"ok","checks":{"database":true}}`. Since 1.0.2 a failed check answers HTTP 503 (DEF-016), so this command then fails with `HTTP Error 503` instead of printing the body.

4. Take an integrity snapshot with the label `after` and compare it with `before` (or with an earlier baseline).

Because the restore is one transaction, a failed restore leaves the database as it was. Both scripts start `api` and `web` again when the restore fails, and exit with the restore's exit code. Since 1.0.2 (DEF-019) the shell script then prints `Restore FAILED (exit <n>): the previous data is still in place and the services were restarted.`

The file name is looked up in `/backups`. An absolute path inside the container is also accepted.

## 7. Integrity check

`ops/integrity.py` fingerprints every table in the `legacy_ilms` schema: the row count and a SHA-256 over all rows in primary-key order. Two snapshots match only if no row was added, removed or changed (NFR 01, AC 10).

The bundle does not contain the backend code that `ops/integrity.py` imports, so run it inside the API container, where it is installed as `/app/ops/integrity.py`. Write reports to the backup volume so they survive container recreation (the default folder, `/app/ops/reports`, is inside the container):

```sh
docker compose exec api python /app/ops/integrity.py snapshot --out /backups/reports --label before
```

Output: one line per table with `rows=` and `sha256=`, and `report: /backups/reports/integrity-<UTC timestamp>-before.json`.

Compare two reports:

```sh
docker compose exec api python /app/ops/integrity.py compare /backups/reports/integrity-20261007T145800Z-before.json /backups/reports/integrity-20261007T150200Z-after.json
```

| Result | Output | Exit code |
|---|---|---|
| Unchanged | `IDENTICAL: <n> legacy tables, <rows> rows` | `0` |
| Changed | `CHANGED: <table>, ...` | `1` |

Recommended points for a snapshot: after installation (baseline), before and after each migration batch, before and after each restore, and before and after each update or rollback. The AC 09 rehearsal compared the snapshot after installation with the one after rollback ([AC 09 record](../../ops/tests/ac09_offline_lifecycle.md)).

A `CHANGED` result on `legacy_ilms` means the existing ILMS data differs from the snapshot. The Nexus application role cannot write to that schema, so investigate any change made with owner credentials, and restore the last backup taken before it if needed.
