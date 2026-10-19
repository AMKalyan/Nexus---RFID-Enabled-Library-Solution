# Installation Guide

Nexus is installed from an offline bundle, `nexus-<version>.zip`. The installer needs no network access: images are loaded from the bundle, and secrets, the TLS certificate and (for a demonstration) a licence are generated on the host. The packaging approach is described in [ADR-0002](../02-design/adr/0002-offline-packaging.md).

Complete the [environment checklist](environment-checklist.md) first.

## 1. Bundle contents

The bundle is built by `ops/build_bundle.sh <version>` and unzips to one folder, `nexus-<version>/`:

| Path | Contents |
|---|---|
| `images.tar.gz` | `nexus-api`, `nexus-web` and `nexus-devsim` images for the release, and `postgres:16.4-alpine` |
| `docker-compose.yml`, `.env.example` | Service definitions and the configuration template |
| `VERSION`, `RELEASE-NOTES.md` | Release number and notes |
| `ops/` | `install`, `update`, `rollback`, `backup`, `restore` (each as `.sh` and `.ps1`), `common.sh`, `common.ps1`, `integrity.py`, `licence.py`, `db/init/01-roles.sh`, `nginx/default.conf.template`, `nginx/gen-cert.sh`, `tests/security_smoke.py` |
| `sbom/` | Backend requirements, frontend lockfile, licence report and the source commit |
| `SHA256SUMS` | SHA-256 of every other file in the bundle |

## 2. What the installer does

`ops/install.ps1` and `ops/install.sh` do the same steps, in this order:

1. Verify every file against `SHA256SUMS`. On any mismatch or missing file it prints `Bundle verification FAILED: do not install this copy.` and stops before changing anything.
2. Stop here if `-VerifyOnly` / `--verify-only` was given.
3. Load the images with `docker load -i images.tar.gz`.
4. If there is no `.env`, create it from `.env.example` and replace every `replace-...` placeholder with a new random 64-character hex value. An existing `.env` is kept.
5. Set `NEXUS_VERSION` in `.env` to the bundle's `VERSION`.
6. If `ops/nginx/certs/nexus.crt` is missing, generate a self-signed certificate (RSA 2048, 825 days, `CN=nexus.local`) with the API image's `openssl`.
7. Licence:
   - with `-LicenceKeyFile KEY_FILE` / `--licence-key-file KEY_FILE`, first set `LICENCE_KEY` in `.env` to the key in that file (the key the licence was signed with)
   - with `-Licence FILE` / `--licence FILE`, copy that file to `licence/licence.json`
   - otherwise, with `-Demo` / `--demo` and no existing licence, issue a 30-day licence for "Demonstration site", signed with the new `LICENCE_KEY`
8. Start the stack with `docker compose up -d --no-build`. On first start the database container creates the roles (`ops/db/init/01-roles.sh`) and the API applies the schema migrations. If step 7 installed or issued a licence, restart the API so it reads the new licence (DEF-020).
9. Wait up to 180 s for the API container to report `healthy`. If it does not, the installer stops with an error.
10. With `-Demo` / `--demo` only: seed synthetic data (2,000 legacy bibliographic records, mirrored into Nexus with shelves, devices, staff users, tags and activity) and copy the generated sign-in details to `ops/demo-credentials.txt`.
11. Print the `/api/v1/version` response and the URL.

## 3. Options

| PowerShell | Shell | Effect |
|---|---|---|
| `-VerifyOnly` | `--verify-only` | Check `SHA256SUMS` and exit: `0` if the bundle is intact, `1` if not. Nothing is loaded or changed |
| `-Demo` | `--demo` | Issue a 30-day demonstration licence (if none exists) and seed synthetic demonstration data after start-up |
| `-Licence FILE` | `--licence FILE` | Install `FILE` as `licence/licence.json` and restart the API so it takes effect. Takes precedence over the demonstration licence |
| `-LicenceKeyFile KEY_FILE` | `--licence-key-file KEY_FILE` | Set `LICENCE_KEY` in `.env` to the key in `KEY_FILE`, the key the licence was signed with. Use it with `-Licence` / `--licence` for a licence issued before installation |

Any other option makes `install.sh` exit with `unknown option` (exit code 2).

## 4. Install on Windows

1. Copy `nexus-<version>.zip` to the host and unzip it into the parent folder of the installation, for example `C:\Nexus`:

   ```powershell
   Expand-Archive -LiteralPath D:\media\nexus-1.0.2.zip -DestinationPath C:\Nexus
   cd C:\Nexus\nexus-1.0.2
   ```

   This folder is the installation folder from now on. Its name keeps the first version after updates. Do not move it after installing: the certificate and licence folders are bind-mounted from it.

2. Verify the bundle:

   ```powershell
   powershell -ExecutionPolicy Bypass -File ops\install.ps1 -VerifyOnly
   ```

   Expected: `bundle verified`.

3. Install. For an evaluation or demonstration:

   ```powershell
   powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Demo
   ```

   For a site with an issued licence file (see [section 6](#6-licence)):

   ```powershell
   powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Licence D:\media\licence.json -LicenceKeyFile D:\media\licence.key
   ```

4. Check the result. The installer ends with a line such as `version: {"version":"1.0.2","alembic_rev":"0004","licence":"valid",...}` and `Nexus 1.0.2 is running at https://localhost:8443/`.

## 5. Install on Linux

1. Unzip the bundle and change to the installation folder:

   ```sh
   unzip nexus-1.0.2.zip -d /opt/nexus
   cd /opt/nexus/nexus-1.0.2
   ```

2. Verify the bundle:

   ```sh
   sh ops/install.sh --verify-only
   ```

   Expected: `bundle verified (<n> files)`.

3. Install:

   ```sh
   sh ops/install.sh --demo                      # evaluation or demonstration
   sh ops/install.sh --licence /media/licence.json --licence-key-file /media/licence.key  # site with an issued licence
   ```

4. Check the `version:` line and the URL printed at the end.

## 6. Licence

The API reads `licence/licence.json` (mounted read-only at `/app/licence/licence.json`) when it starts, and reports the result as `licence` on `/api/v1/version`: `valid`, `missing`, `invalid` or `expired`.

- Outside development, an installation without a valid licence is **read-only** for everyone except administrators. Write requests from other roles get `403` with code `LICENCE_REQUIRED`. Sign-in is always allowed.
- A licence is `{site, expires, features, sig}`, where `sig` is HMAC-SHA256 over the other fields. It is valid only if it was signed with the installation's `LICENCE_KEY` (in `.env`).
- On a first install, the installer generates a new random `LICENCE_KEY`. A licence file issued before installation is valid only if it was signed with the key that ends up in `.env`. Since 1.0.2 (DEF-020), pass the issued key with the licence: `-Licence FILE -LicenceKeyFile KEY_FILE` / `--licence FILE --licence-key-file KEY_FILE`. The installer writes the key to `LICENCE_KEY` in `.env` (replacing the generated one) before it starts the stack. Keep the key file as protected as `.env`.
- HMAC means the site holds the verification key, so it could also issue licences. This is a prototype choice. Asymmetric (PKI) licence signing is in the [production backlog](../09-demo/production-backlog.md).

To install or replace a licence on a running installation:

1. Copy the file to `licence/licence.json` in the installation folder.
2. Restart the API so it reads the file again, and check the status:

   ```powershell
   docker compose restart api
   docker compose exec -T api python /app/ops/licence.py verify /app/licence/licence.json
   ```

   `verify` prints `valid` (exit 0) or the reason it is not valid (exit 1).

Alternatively, run the installer again with `-Licence FILE` / `--licence FILE` (and the key file if the key changes). Since 1.0.2 the installer restarts the API after installing a licence, so the new licence takes effect immediately. The licence status is still read only when the API starts: a file copied by hand needs the restart above.

## 7. After installation

1. Open `https://<host>:<HTTPS_PORT>/` (default `https://localhost:8443/`). With the self-signed certificate the browser shows a warning until the certificate is trusted.
2. Check the services:

   ```sh
   docker compose ps
   ```

   `db` and `api` should be `healthy` and `web` running.

3. Replace the self-signed certificate with the site certificate ([environment checklist, section 4](environment-checklist.md#4-certificate)).
4. For a demonstration install, the staff sign-in details are in `ops/demo-credentials.txt`. Keep the file private. To start the device simulator panel (on `http://127.0.0.1:8100`):

   ```sh
   docker compose --profile demo up -d devsim
   ```

5. Take a first backup and an integrity baseline ([backup and restore](backup-restore.md)).
6. Store a protected copy of `.env`, `licence/` and `ops/nginx/certs/`.

## 8. Re-running the installer

The installer is safe to run again in the same folder. It keeps an existing `.env`, certificate and licence, loads the images again and runs `docker compose up -d`. To move to a newer release, use the [update procedure](update-rollback.md), not the installer.

Bundle verification checks the files listed in `SHA256SUMS`. After an update the installed scripts no longer match the original bundle's `SHA256SUMS`, so re-running the installer in an updated folder fails verification.

## 9. Not provided

- No Windows service or `systemd` unit. Since 1.0.2 (DEF-018) the compose file sets `restart: unless-stopped` on `db`, `api` and `web`, so the containers come back after a host or Docker restart, provided Docker itself starts at boot (configure that on the host). Containers stopped by hand with `docker compose stop` stay stopped. A native service package is in the [production backlog](../09-demo/production-backlog.md).
- No uninstaller. `docker compose down` stops and removes the containers and keeps the volumes. `docker compose down -v` also deletes the database **and the backup volume**.
