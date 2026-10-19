# Update and Rollback

An update applies a newer offline bundle to an existing installation. Every update takes a backup first and records what it replaced, so it can be rolled back automatically (when the new release is not healthy) or by hand. The procedure was rehearsed offline from 1.0.0 to 1.0.1 and back ([AC 09 record](../../ops/tests/ac09_offline_lifecycle.md)). The examples below update 1.0.1 to the current release, 1.0.2.

Run all commands from the installation folder with the stack running.

## 1. Before updating

1. Read the new release's `RELEASE-NOTES.md` for its schema revision and any special steps. 1.0.1 moved the schema from `0003` to `0004`. 1.0.2 has no migration: the schema stays at `0004`.
2. Copy the bundle (`nexus-<version>.zip`) to the host. It can stay zipped.
3. Check the current release and its state:

   ```sh
   docker compose ps
   docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/version').read().decode())"
   ```

4. Take an integrity snapshot with the label `pre-update` ([backup and restore, section 7](backup-restore.md#7-integrity-check)).
5. Plan a short outage. The API and UI restart during the update.

## 2. Running the update

```powershell
powershell -ExecutionPolicy Bypass -File ops\update.ps1 D:\media\nexus-1.0.2.zip
```

```sh
sh ops/update.sh /media/nexus-1.0.2.zip
```

The argument is the bundle `.zip` or an already unzipped bundle folder.

## 3. What the update does

In order:

1. If given a `.zip`, unzip it to a temporary folder (removed at the end).
2. Verify the new bundle against its `SHA256SUMS`. On failure: `Update bundle verification FAILED: nothing was changed.` and exit 1.
3. Read the current release (`NEXUS_VERSION` in `.env`) and the new release (`VERSION` in the bundle). If they are the same, print `already at <version>` and stop.
4. Read the current schema revision (`alembic_rev`) from `/api/v1/version`.
5. Take a backup with the reason `pre-update-<from>-<to>`. If it fails, stop with `backup failed: nothing was changed`.
6. Copy the current `docker-compose.yml`, `VERSION` and `RELEASE-NOTES.md` to `ops/previous/` (replacing an earlier copy).
7. Write `ops/state.json` ([section 4](#4-opsstatejson)).
8. Load the new images with `docker load`. The previous release's images stay loaded.
9. Copy the new `docker-compose.yml`, `VERSION`, `RELEASE-NOTES.md`, `.env.example`, the `ops/*.sh`, `ops/*.ps1` and `ops/*.py` scripts and `ops/nginx/default.conf.template` into the installation folder.
10. Set `NEXUS_VERSION` in `.env` to the new release. Other `.env` values, the certificate and the licence are kept.
11. Start the new release with `docker compose up -d --no-build`. The API applies the new schema migrations as it starts.
12. Wait up to **120 s** for the API container to report `healthy`:
    - healthy: print `updated to <to>: <version response>` and the name of the pre-update backup
    - not healthy within 120 s: print `== <to> is not healthy: rolling back to <from>`, run the rollback script ([section 5](#5-rollback)) and exit 1

After a successful update:

1. Check `/api/v1/version`: the new `version` and `alembic_rev`, and `licence` still `valid`.
2. Take an integrity snapshot and compare it with `pre-update`. Expected: `IDENTICAL`.
3. Keep the pre-update backup and `ops/state.json` until the new release is accepted.

## 4. `ops/state.json`

The update records the release it replaced:

```json
{
  "previous_version": "1.0.1",
  "previous_alembic_rev": "0004",
  "current_version": "1.0.2",
  "backup": "nexus-1.0.1-<UTC timestamp>-pre-update-1-0-1-1-0-2.dump",
  "updated_at": "<UTC time>"
}
```

- 1.0.2 has the same schema revision as 1.0.1 (`0004`). A rollback from 1.0.2 to 1.0.1 therefore runs `alembic downgrade 0004`, which changes nothing, and then switches back to the 1.0.1 images.
- Only the most recent update is recorded. A second update overwrites `ops/state.json` and `ops/previous/`, so rollback goes back one release only.
- After a rollback the file is renamed `ops/state-rolled-back-<UTC timestamp>.json`. Without `ops/state.json`, the rollback script prints `no ops/state.json: nothing to roll back` and exits 1.

## 5. Rollback

Run a manual rollback when the new release is healthy but not acceptable:

```powershell
powershell -ExecutionPolicy Bypass -File ops\rollback.ps1
```

```sh
sh ops/rollback.sh
```

The same script runs automatically when an update is not healthy within 120 s. In order, it:

1. Reads `ops/state.json`.
2. Sets `NEXUS_VERSION` back to the **new** release and stops `web` and `api`.
3. Runs `alembic downgrade <previous_alembic_rev>` in a one-off container of the new image. Only the new image contains the migration scripts that can undo its own schema changes.
4. Copies `ops/previous/docker-compose.yml` and `ops/previous/VERSION` back into the installation folder.
5. Sets `NEXUS_VERSION` to the previous release.
6. If the downgrade in step 3 failed (`schema downgrade failed: restoring backup <file>`), restores the pre-update backup recorded in `ops/state.json` with `python -m nexus_ops.backup restore <file> --yes`. The restore verifies the checksum first and runs in one transaction.
7. Starts the previous release with `docker compose up -d --no-build` and waits up to 120 s for it to be healthy.
8. Prints `rolled back to <previous>: <version response>` and renames `ops/state.json`.

If the previous release is not healthy within 120 s, the script exits with an error and leaves `ops/state.json` in place.

### Downgrade or restore

| Path | When | Data written after the update |
|---|---|---|
| Schema downgrade (normal) | The new release's downgrade succeeds | Kept, except what the downgrade removes. From 1.0.2 to 1.0.1 nothing is removed (no schema change). From 1.0.1 to 1.0.0 only the `maintenance_notice` setting and the 1.0.1 release record are removed |
| Restore of the pre-update backup (fallback) | The downgrade fails | **Lost**: the database returns to the state at the start of the update |

Only the downgrade path was exercised in the AC 09 rehearsal. The automatic rollback after an unhealthy start and the restore fallback use the same scripts but were not exercised with a broken release.

### After a rollback

1. Check `/api/v1/version`: the previous `version` and `alembic_rev`.
2. Take an integrity snapshot and compare it with `pre-update`. Expected: `IDENTICAL`.
3. If the restore fallback ran, tell staff that changes made after the update were lost.

If the rollback itself fails, restore the pre-update backup by hand with `ops/restore.ps1` / `ops/restore.sh` once `NEXUS_VERSION` and `docker-compose.yml` are back on the previous release ([backup and restore, section 6](backup-restore.md#6-restoring-a-backup)).

## 6. Notes and limits

- The rollback restores only `docker-compose.yml` and `VERSION`. The `ops` scripts, `RELEASE-NOTES.md`, `.env.example` and the nginx template copied by the update stay at the new release's versions.
- "Healthy" is the Docker health check of the API container, which requests `/api/v1/health` inside the container. The endpoint answers HTTP 200 when every check passes and HTTP 503 with `"status": "degraded"` when any check fails (DEF-016, fixed in 1.0.2). The only check is the database connection. A release whose API starts but cannot reach the database is therefore reported `unhealthy` and rolled back automatically.
- Images of earlier releases are not removed. Remove them with `docker image rm nexus-api:<version> nexus-web:<version> nexus-devsim:<version>` once rollback to that release is no longer needed.
- The update script only checks that the bundle's version differs from the installed one; it does not refuse an older bundle. Applying an older bundle with `update` is not a supported way to roll back. Use the rollback script.
