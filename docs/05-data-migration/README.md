# D5: Database and Migration Package

This package covers the database structure, schema migrations, the synthetic sample dataset, the spreadsheet import utility, and the evidence that the migration reconciles and that existing ILMS data stays intact (FR 10, NFR 01, AC 01, AC 10).

## Contents

| Item | Location |
|---|---|
| Database design (schemas, roles, ER diagram) | [`docs/02-design/database-design.md`](../02-design/database-design.md) |
| Data dictionary | [`docs/01-requirements/data-dictionary.md`](../01-requirements/data-dictionary.md) |
| ORM models | `backend/app/db/models/` |
| Schema migrations (Alembic) | `backend/app/db/migrations/versions/` |
| Database roles and grants | `ops/db/init/01-roles.sh`, `0001_baseline.py` |
| Sample data generator and profiler | `migration/gen_sample.py`, `migration/profile_sheet.py` |
| Import utility (command line) | `migration/nexus_migrate.py` |
| Import utility (screen) | Administration → Migration (`/migration`) |
| Validation rules and column mapping | `backend/app/services/migration/rules.yaml`, `mapping.yaml` |
| Backup, restore and integrity tools | `backend/nexus_ops/`, `ops/backup.*`, `ops/restore.*`, `ops/integrity.py` |
| Source profile report | [`profile-report.md`](profile-report.md) |
| Validation and reconciliation report (20k run) | [`migration-run-report.md`](migration-run-report.md) |
| Restore and integrity report | [`restore-and-integrity-report.md`](restore-and-integrity-report.md) |

## Schemas

| Schema | Purpose | Application role access |
|---|---|---|
| `legacy_ilms` | Synthetic copy of the existing ILMS (catalogue, accession, borrower). Owned by `legacy_owner` | `SELECT` only. Nexus cannot change it (NFR 01) |
| `nexus` | Application data: bibs, items, tags, members, loans, fines, devices, gate events, outbox, migration batches, `audit_log` | Read and write. `audit_log` is insert and select only |
| `staging` | Staged import rows (`staging.import_row`) with their validation status and reasons | Read and write |

## Migration history

```
<base> -> 0001, baseline
0001 -> 0002, Roles, permissions and circulation policies
0002 -> 0003, agency
0003 -> 0004 (head), release 1.0.1: maintenance notice setting and release record
```

`alembic upgrade head` runs when the API container starts. The full list is available with `docker compose exec api alembic history`.

## Sample dataset

```bash
python migration/gen_sample.py --rows 20000 --out migration/samples/library-export-20k.xlsx --seed 42
```

The generator writes a workbook in the export layout, plus `<file>.manifest.json` that lists every planted defect. The defects are:
- about 3% invalid rows: missing title, bad accession format, failed ISBN checksum, year out of range, negative price, unknown item type
- 1% exact duplicates
- 1% likely duplicates

It also plants valid but awkward cells that the importer should normalise rather than reject: ISBNs stored as numbers, Excel serial dates, mixed case and stray whitespace.

The data is fully synthetic and generated with Faker. Generated files are not committed (`migration/samples/` is ignored).

To profile a file before importing it:

```bash
python migration/profile_sheet.py migration/samples/library-export-20k.xlsx
```

## Import procedure

1. **Stage.** The file is uploaded, either by `nexus_migrate.py --file` or on the Migration screen. Every row is stored unchanged in `staging.import_row`, and the file's sha256 is recorded on the batch. Only `.xlsx` and `.csv` files with the expected columns are accepted, and the size is limited by `UPLOAD_MAX_MB`.
2. **Validate (dry run).** Each row is normalised and checked against `rules.yaml`.
   - Each failure adds a reason code to the row.
   - A row whose accession number appeared earlier in the file, or is already in the catalogue, is an exact duplicate and is excluded.
   - Rows with the same normalised title, author and year are flagged `LIKELY_DUPLICATE` but still migrated.
   - Nothing is written to the catalogue at this step.
3. **Review.** The reconciliation report shows source, valid, rejected and duplicate counts, the rejections by reason, and whether `source = valid + rejected + duplicate`. A row-level CSV is available with `--csv` or from the Download button.
4. **Commit.** The commit runs these steps in order:
   - Take a verified backup with `pg_dump` (sha256 side file).
   - Fingerprint the legacy tables.
   - Insert all valid rows in one transaction, tagged with the batch id.
   - Fingerprint the legacy tables again.

   Before anything is touched, the commit is refused with `BATCH_NOT_BALANCED` unless the counts reconcile and the staged valid rows match the report (DEF-021). If any legacy table changed during the insert, the transaction is rolled back. The result is audited as `migration.commit`.
5. **Roll back a batch** if needed. This deletes only the items and bibs carrying that batch id and is audited as `migration.rollback`.

```bash
python migration/nexus_migrate.py --ca ops/nginx/certs/nexus.crt --file migration/samples/library-export-20k.xlsx            # stage and validate
python migration/nexus_migrate.py --ca ops/nginx/certs/nexus.crt --file migration/samples/library-export-20k.xlsx --commit   # and commit
python migration/nexus_migrate.py --ca ops/nginx/certs/nexus.crt --report <batch-id> --csv rows.csv
python migration/nexus_migrate.py --ca ops/nginx/certs/nexus.crt --rollback <batch-id>
```

The utility asks for the admin password, or reads it from `NEXUS_PASSWORD` for unattended runs. It never accepts the password as an argument. Only the Admin role holds `migration.run`.

## Backup, restore and integrity

| Task | Command |
|---|---|
| Take a backup | `ops/backup.sh pre-change` (or `ops\backup.ps1 -Reason pre-change`) |
| List backups | `docker compose exec api python -m nexus_ops.backup list` |
| Restore a backup | `ops/restore.sh <file>.dump` (stops the web and API services, verifies the checksum, restores in a single transaction, restarts) |
| Fingerprint legacy tables | `docker compose exec api python /app/ops/integrity.py snapshot` |
| Compare two fingerprints | `python ops/integrity.py compare BEFORE.json AFTER.json` (prints `IDENTICAL` and exits 0, or prints `CHANGED` with the tables and exits 1) |

A restore refuses a backup whose checksum file is missing or doesn't match.

## Rollback options

| Situation | Action |
|---|---|
| A committed batch is wrong but the rest of the system is fine | Batch rollback (`--rollback <batch-id>` or the Migration screen) |
| A batch or integration change damaged other data | Restore the pre-commit backup named in the commit report (`backup_file`) with `ops/restore.sh`, then run `integrity.py compare` against the pre-change fingerprint |
| A commit failed part-way | No action needed. The commit is one transaction, so nothing is kept |

## Evidence

| Requirement | Evidence |
|---|---|
| FR 10, AC 01 | `backend/tests/acceptance/test_ac01_migration.py` (9 tests), `tests/unit/test_migration_validate.py` (5), `migration/test_gen_sample.py` (5). The 20k run reconciled exactly against the manifest (`migration-run-report.md`) |
| NFR 01, AC 10 | `backend/tests/acceptance/test_ac10_restore_integrity.py` (5 tests). The live rehearsal restored 19,200 damaged items, and the legacy fingerprints compared `IDENTICAL` (`restore-and-integrity-report.md`). The database grants are covered by `test_nfr01_app_role_cannot_modify_legacy` |
