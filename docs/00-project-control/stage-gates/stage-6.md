# Stage Gate 6: Migration and Resilience (D7)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 6 |
| Branch | `stage/6-migration` |
| Gate date | 2026-10-07 |
| Outcome | Pending approval |

## Exit criteria (SOP §9 Stage 6 bullets)

| SOP requirement | Output | Evidence | Met |
|---|---|---|---|
| Profile the sample spreadsheet | 20,000-row synthetic export with a manifest of every planted defect; column profile (empties, distinct values, mixed cell types) | `migration/gen_sample.py`, `migration/profile_sheet.py`; `migration/test_gen_sample.py` (5); [`profile-report.md`](../../05-data-migration/profile-report.md) | ☑ |
| Run validation and dry-run import | Upload into `staging.import_row` (type and column checks, size limit); YAML rules with reason codes; exact and likely duplicate detection; dry-run report with nothing written to the catalogue | `services/migration/`, `api/v1/migration.py`, Migration screen, `nexus_migrate.py`; `test_ac01_migration.py` (9), `test_migration_validate.py` (5) | ☑ |
| Reconcile counts and errors | `source = valid + rejected + duplicate` and `committed = valid` checked on every report; rejections by reason; row-level CSV | [`migration-run-report.md`](../../05-data-migration/migration-run-report.md): 20,000 = 19,200 + 600 + 200, matching the manifest per reason | ☑ |
| Execute migration into the test database | Verified backup, then a single-transaction insert tagged with the batch id; legacy fingerprints before and after; audited | Batch `db7e5931…` committed 19,200 items in 13.7 s end to end (target under 5 minutes) | ☑ |
| Demonstrate rollback | Batch rollback removes only that batch's bibs and items | `test_ac01_batch_rollback_removes_only_that_batch`; live rehearsal: 50-row batch committed and rolled back, 20k batch untouched, legacy IDENTICAL (run report, "Batch rollback rehearsal") | ☑ |
| Demonstrate restore | Checksum-verified `pg_restore` in one transaction; operator scripts for shell and PowerShell; integrity snapshot and compare tool | `nexus_ops/backup.py`, `ops/backup.*`, `ops/restore.*`, `ops/integrity.py`; `test_ac10_restore_integrity.py` (5); [`restore-and-integrity-report.md`](../../05-data-migration/restore-and-integrity-report.md): 19,200 damaged items restored, legacy IDENTICAL | ☑ |

## Test totals at gate
- Backend: 214 tests, 91% line coverage
- Simulator: 6 tests
- Migration tool: 5 tests
- Frontend: 8 tests

All of these pass. ruff, mypy, bandit, pip-audit and npm audit are clean (`bash ops/ci-local.sh`).

## Findings and decisions
- **DEF-005 (S2):** the API image's pg_dump 15 could not back up the PostgreSQL 16 server. The image now installs `postgresql-client-16` from the PostgreSQL apt repository.
- **DEF-006 (S3):** staging used per-row ORM statements. It now uses core multi-row inserts and pipelined updates, taking the 20k run from an estimated 3.5 minutes to 13.7 s.
- **Likely duplicates** are flagged and migrated rather than rejected, because title, author and year can legitimately repeat across editions. The live run flagged 204: the 200 planted ones, plus 4 that match seeded records because the seed and the generator share a random seed.
- **Commit safety:** a commit is refused unless the batch has been validated. It rolls back if any legacy fingerprint changes or the counts don't balance.
- **Restores** close other database sessions and run with the API stopped, so no writes interleave with `pg_restore`.
- **Static analysis:** bandit's B608 on the integrity query was reviewed. The identifiers come from the system catalogue and are quoted (ADR-0003), and the line is annotated.
- **Process:** formatting run from the repository root ignored the backend's ruff settings. Those changes were discarded before commit, and backend lint is run from `backend/`.

## Decision
Pending approval. Verification (Stage 7) starts from `main` once this branch is merged.
