# Restore and Integrity Report (AC 10)

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Environment | Development stack (`docker compose`), database `nexus` with 2,000 legacy bibs, 2,377 accessions, 300 borrowers and the committed 20,000-row migration batch `db7e5931…` |
| Tools | `ops/integrity.py`, `ops/backup.sh`, `ops/restore.sh` (PowerShell equivalents in `ops/*.ps1`) |

## Procedure and results

| Step | Command | Result |
|---|---|---|
| 1. Fingerprint legacy data | `docker compose exec api python /app/ops/integrity.py snapshot --out /backups/reports --label before` | accession 2,377 rows `b4a8f241…`; borrower 300 rows `581c9777…`; catalogue 2,000 rows `3b69cba4…` |
| 2. Back up | `ops/backup.sh pre-change` | `nexus-1.0.0-20261007T145907Z-pre-change.dump`, sha256 `b16adfc1…` |
| 3. Simulate a failed change | `UPDATE nexus.item SET status='withdrawn' WHERE migration_batch_id='db7e5931…'` | 19,200 items damaged (all `withdrawn`) |
| 4. Restore | `ops/restore.sh nexus-1.0.0-20261007T145907Z-pre-change.dump` | Checksum verified; API stopped, other sessions closed, `pg_restore --clean --single-transaction`, API restarted |
| 5. Verify the nexus data | `SELECT status, count(*) … GROUP BY 1` | 19,200 items `available` again |
| 6. Prove legacy data intact | `integrity.py snapshot --label after`, then `integrity.py compare before.json after.json` | **IDENTICAL: 3 legacy tables, 4,677 rows** (exit code 0) |
| 7. Service health | `GET /api/v1/health` | `{"status":"ok","checks":{"database":true}}` |

## Automated evidence

`backend/tests/acceptance/test_ac10_restore_integrity.py` runs on a dedicated database, `nexus_restore_test`:

| Test | Proves |
|---|---|
| `test_ac10_restore_after_failed_migration_proves_original_data_intact` | 500 junk items and a damaged record are reverted by restore; legacy fingerprints unchanged |
| `test_ac10_integrity_check_detects_a_changed_legacy_row_and_restore_repairs_it` | A single changed legacy title is detected (`catalogue`) and repaired by restore |
| `test_ac10_restore_refuses_tampered_backup` | A dump whose bytes changed is refused |
| `test_ac10_restore_refuses_backup_without_checksum` | A dump without its `.sha256` file is refused |
| `test_ac10_snapshot_counts_every_legacy_table` | Every legacy table is fingerprinted |

## How the guarantee is layered

1. **Prevention:** the application role cannot modify `legacy_ilms` at all (database grants, `test_nfr01_app_role_cannot_modify_legacy`).
2. **Detection:** row-level SHA-256 fingerprints, compared before and after every migration commit and every restore.
3. **Recovery:** a verified backup is taken automatically before every migration commit (and on demand), and a restore is a single transaction.
