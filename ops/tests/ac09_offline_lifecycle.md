# AC 09: Offline Install, Update and Rollback Rehearsal

**Scenario (AC 09):** install the solution offline, apply an offline update package, and demonstrate the documented rollback.

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Host | Windows 11 development host with Docker Desktop (WSL 2) |
| Network | **Off.** Wi-Fi and Bluetooth adapters disconnected; only Docker's internal WSL adapter was up. `pypi.org:443` and `registry-1.docker.io:443` were unreachable at the start and at the end |
| Bundles | `nexus-1.0.0.zip` (tag `v1.0.0`) and `nexus-1.0.1.zip` (tag `v1.0.1`), built with `ops/build_bundle.sh`, each with `SHA256SUMS` |
| Starting state | No Nexus or PostgreSQL images and no Nexus volumes on the host (removed beforehand; the development database was backed up first) |
| Runner | [`ops/tests/rehearse-ac09.ps1`](rehearse-ac09.ps1). It calls the bundle's own `install.ps1`, `update.ps1` and `rollback.ps1` |
| Transcript | [`docs/06-testing/evidence/ac09/ac09-offline-transcript.txt`](../../docs/06-testing/evidence/ac09/ac09-offline-transcript.txt) (user and machine fields redacted) |

## Results

| Step | Command | Expected | Observed | Result |
|---|---|---|---|---|
| 0. Offline | `Get-NetAdapter`; `Test-NetConnection` | No internet, no registry | Wi-Fi and Bluetooth `Disconnected`; PyPI and Docker registry `False` | Pass |
| 1. Install 1.0.0 | `ops\install.ps1 -Demo` in the unzipped bundle | Bundle verified; images loaded from the archive; secrets, certificate and demo licence generated locally; healthy | `bundle verified`; loaded `nexus-api`, `nexus-web`, `nexus-devsim` 1.0.0 and `postgres:16.4-alpine`; `.env`, TLS certificate and 30-day licence created; `/version` = `{"version":"1.0.0","alembic_rev":"0003","licence":"valid"}`; 2,000 bibs, 2,377 items, 300 members | Pass |
| 2. Update to 1.0.1 | `ops\update.ps1 media\nexus-1.0.1.zip` | Bundle verified; backup first; state recorded; new release healthy with schema 0004 | Backup `nexus-1.0.0-…-pre-update-1-0-0-1-0-1.dump`; `ops\state.json` records 1.0.0 and schema 0003; `/version` = `1.0.1`, `alembic_rev` `0004`, `build_notes` present; containers `nexus-api:1.0.1`, `nexus-web:1.0.1`; counts unchanged | Pass |
| 3. Roll back | `ops\rollback.ps1` | Schema downgraded with the 1.0.1 image; 1.0.0 running again | `schema downgraded to 0003`; `/version` = `1.0.0`, `alembic_rev` `0003`; containers `nexus-api:1.0.0`, `nexus-web:1.0.0`; counts unchanged | Pass |
| 4. Legacy integrity | `integrity.py compare` after install vs after rollback | Identical | `IDENTICAL: 3 legacy tables, 4,677 rows` (exit 0) | Pass |

Total time on the offline host: about 1 minute 40 seconds (00:22:40 to 00:24:17).

## Further evidence

| Check | Evidence |
|---|---|
| A tampered bundle is refused before anything is installed | `ops/tests/test_bundle_scripts.sh` (shell verifier). The PowerShell verifier was checked the same way: the intact copy exited 0; the copy with one changed byte in `images.tar.gz` reported `checksum mismatch: images.tar.gz` and exited 1 |
| The 1.0.1 migration can be applied, reverted and re-applied | `test_ac09_release_101_migration_upgrades_downgrades_and_reapplies` |
| Unlicensed installations are read-only for non-administrators | `test_fr12_unlicensed_installation_is_read_only_for_non_admins` and related licence tests |
| The same runner passed before the offline run with the network on | [`ac09-dry-run-online-transcript.txt`](../../docs/06-testing/evidence/ac09/ac09-dry-run-online-transcript.txt) |

## Not exercised in this rehearsal

- **Automatic rollback when an update is unhealthy** (`update.ps1` calls `rollback.ps1` after 120 s). It uses the same rollback path shown in step 3. A deliberately broken release was not built.
- **Restoring the pre-update backup when the schema downgrade fails.** The restore itself is proven by AC 10.
- **The shell scripts (`install.sh`, `update.sh`, `rollback.sh`)** were exercised only for bundle verification. The full lifecycle was run with the PowerShell scripts, which are the ones for the Windows target (NFR 03).
