# Baseline Test Report: Stage 3 (Foundation Build)

- Date: 2026-10-05
- Branch: `stage/3-foundation`
- Command: `bash ops/ci-local.sh` (same steps as `.github/workflows/ci.yml`)
- Environment: Windows 11 development host, Docker Desktop (WSL2), PostgreSQL 16.4 container, Python 3.12.6, Node 22.14

## Results

| Check | Tool | Result |
|---|---|---|
| Format | `ruff format --check` | Pass |
| Lint (incl. security rules) | `ruff check` | Pass, 0 findings |
| Type check | `mypy app` | Pass, 0 issues in 37 files |
| Static security analysis | `bandit -r app -x app/db/migrations` | 0 findings (2 reviewed and annotated: seeded RNG used only for synthetic data) |
| Python dependency scan | `pip-audit -r requirements.txt` | No known vulnerabilities (after DEF-001 fix) |
| Backend tests | `pytest --cov=app` | 29 passed, 0 failed; line coverage 83% |
| Frontend type check | `tsc -b` | Pass |
| Frontend tests | `vitest run` | 2 passed |
| Frontend dependency scan | `npm audit --audit-level=high` | 0 vulnerabilities (after DEF-003 fix) |
| Frontend build | `vite build` | Pass |
| Container build and start | `docker compose up -d --build` | db, api and web healthy; `/api/v1/health` reports database ok; `/api/v1/version` reports 1.0.0 at migration 0002 |
| TLS and headers | `curl -kI https://localhost:8443/` | 200 with HSTS, CSP, X-Frame-Options, nosniff; port 80 redirects to HTTPS |

## Tests by requirement

| Requirement | Tests |
|---|---|
| NFR 01 Data integrity | `test_nfr01_app_role_can_read_legacy`, `test_nfr01_app_role_cannot_modify_legacy` (UPDATE, DELETE, INSERT, TRUNCATE), `test_nfr01_mirror_copies_without_touching_legacy` |
| NFR 02 Security | `test_nfr02_password_hash_is_argon2_and_verifies`, `test_nfr02_tampered_token_rejected`, `test_nfr02_login_success_and_me`, `test_nfr02_bad_password_generic_error`, `test_nfr02_login_rate_limited`, `test_nfr02_refresh_rotation_and_reuse_detection`, `test_nfr02_role_change_effective_immediately`, `test_nfr02_patron_logs_in_with_card_number`, `test_nfr02_missing_or_garbage_token_is_401`, `test_nfr02_logout_revokes_refresh_token`, `test_nfr02_login_attempts_are_audited_without_username`, `test_nfr02_audit_log_is_append_only`, `test_nfr02_audit_masks_pii_details`, `test_nfr02_masks_email_and_phone`, `test_nfr02_mask_leaves_plain_text`, `test_nfr02_unhandled_error_is_sanitised`, `test_validation_error_does_not_echo_input`, `test_app_error_shape` |
| NFR 06 Maintainability | `test_adr0003_no_raw_sql_in_application_code`; migration upgrade → downgrade → upgrade round trip; `alembic check` reports no model drift |
| NFR 07 Supportability | `test_nfr07_version_endpoint`, `test_nfr07_health_checks_database_and_reports_migration` |
| FR 02 Search | `test_fr02_search_vector_maintained_by_trigger` |
| FR 10 Data quality | `test_fr10_seeded_isbns_have_valid_check_digits` |

## Manual checks

| Check | Result | Evidence |
|---|---|---|
| Seed the development database (`python -m app.db.seed --legacy 2000 --demo`) | 2,000 legacy bibs, 2,377 items, 300 members mirrored; 1,391 tags, 142 loans, 6 devices, 4 staff users; second run is a no-op | Console output |
| Librarian sign-in through the UI | Sign-in succeeds; navigation shows only Librarian items; version footer shows 1.0.0 | `evidence/stage3/librarian-login-navigation.jpg` |

## Defects raised in this stage

DEF-001 (Python dependency vulnerabilities), DEF-002 (audit details had no database default) and DEF-003 (frontend dependency vulnerabilities) were all fixed and retested in Stage 3. See `docs/00-project-control/defect-log.md`.
