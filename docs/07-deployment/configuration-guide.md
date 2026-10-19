# Configuration Guide

Nexus is configured through the `.env` file in the installation folder. The installer creates it from `.env.example` with generated secrets ([installation guide](installation-guide.md#2-what-the-installer-does)). `.env` holds secrets: never commit it or copy it to an unprotected location.

## 1. How settings are read

- `docker-compose.yml` passes the whole `.env` to the API container (`env_file: .env`) and uses some keys for the `db` and `web` services.
- The API reads its settings with pydantic-settings (`backend/app/core/config.py`). Each setting is read from the environment variable of the same name in upper case: the field `jwt_secret` is read from `JWT_SECRET`. Names are not case-sensitive. Unknown keys are ignored.
- Some API settings are fixed by the `environment:` block in `docker-compose.yml`. That block overrides `.env`, so for these keys the `.env` value has no effect in the container: `DATABASE_URL`, `OWNER_DATABASE_URL`, `BACKUP_DIR`, `OUTBOX_DIR`, `LICENCE_FILE`.
- List settings (`CORS_ORIGINS`, `SIP2_ALLOWED_HOSTS`) are written as JSON, for example `SIP2_ALLOWED_HOSTS=["10.10.20.31","10.10.20.32"]`. Booleans are `true` or `false`.
- Changes take effect when the container is recreated: `docker compose up -d` (it recreates services whose configuration changed). nginx reads `HTTPS_PORT` only at start-up.

## 2. Keys in `.env.example`

| Key | Used by | Meaning | Value in `.env.example` | Installer |
|---|---|---|---|---|
| `NEXUS_VERSION` | compose | Image tag for `nexus-api`, `nexus-web` and `nexus-devsim` | `1.0.2` | Set to the bundle's `VERSION`. Changed by update and rollback; do not edit by hand |
| `HTTPS_PORT` | compose, `web` | Host port published for HTTPS, and the port used in the HTTP redirect | `8443` | Kept |
| `HTTP_PORT` | compose | Host port published for the HTTP-to-HTTPS redirect | `8080` | Kept |
| `POSTGRES_USER` | `db`, compose | Database owner role. Owns the schemas, runs migrations, backups, restores and integrity checks | `nexus_owner` | Kept |
| `POSTGRES_PASSWORD` | `db`, compose | Password of the owner role | placeholder | Generated |
| `POSTGRES_DB` | `db`, compose | Database name | `nexus` | Kept |
| `NEXUS_APP_PASSWORD` | `db`, compose | Password of `nexus_app`, the role the API uses. It cannot modify `legacy_ilms` or update or delete `audit_log` | placeholder | Generated |
| `NEXUS_READONLY_PASSWORD` | `db` | Password of `nexus_readonly`, a select-only role on `legacy_ilms` and `nexus` for reporting tools. Nexus itself does not use it | placeholder | Generated |
| `DATABASE_URL` | API | Application connection URL. Overridden in compose (built from `NEXUS_APP_PASSWORD` and `POSTGRES_DB`) | placeholder URL | Placeholder password replaced |
| `OWNER_DATABASE_URL` | API, ops tools | Owner connection URL used for migrations, backup, restore and integrity. Overridden in compose (built from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) | placeholder URL | Placeholder password replaced |
| `JWT_SECRET` | API | Key that signs access tokens. At least 32 characters outside development | placeholder | Generated (64 hex characters) |
| `LICENCE_KEY` | API, `licence.py` | HMAC key that verifies (and issues) the licence file. At least 32 characters outside development | placeholder | Generated (64 hex characters) |
| `ADAPTER_EMAIL` | API | E-mail notification adapter | `mock` | Kept |
| `ADAPTER_SMS` | API | SMS notification adapter | `mock` | Kept |
| `ADAPTER_PRINT` | API | Receipt and slip print adapter | `mock` | Kept |
| `ADAPTER_LEGACY` | API | Connector to the existing ILMS (reads the `legacy_ilms` schema) | `db` | Kept |
| `ADAPTER_CAMERA` | API | CCTV snapshot adapter used on gate alarms | `mock` | Kept |
| `ADAPTER_CREDENTIALS` | API | Smart-card credential provider for staff card sign-in | `mock` | Kept |
| `SIP2_LISTENER_ENABLED` | API | Start the SIP2 TCP listener inside the API process | `false` | Kept |

The database passwords (`POSTGRES_PASSWORD`, `NEXUS_APP_PASSWORD`, `NEXUS_READONLY_PASSWORD`) are applied only when the database volume is first created: the PostgreSQL image sets the owner password and `ops/db/init/01-roles.sh` creates `nexus_app`, `nexus_readonly` and `legacy_owner`. Changing them in `.env` later does not change the roles. To rotate a password, change it in the database (`ALTER ROLE ... PASSWORD ...` as the owner) and in `.env`, then run `docker compose up -d`.

## 3. Other API settings

These keys are not in `.env.example`. Add them to `.env` only to change the default.

| Key | Meaning | Default |
|---|---|---|
| `ENVIRONMENT` | Run mode. See [section 6](#6-environment-and-the-insecure-secret-guard) | `production` in the API image (the code default is `dev`) |
| `APP_VERSION` | Version reported by `/api/v1/version` and used in backup file names | Read from the image's `VERSION` file. Do not set |
| `ACCESS_TOKEN_MINUTES` | Access token lifetime, in minutes | `15` |
| `REFRESH_TOKEN_HOURS` | Refresh token lifetime, in hours | `8` |
| `LOG_LEVEL` | API log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `CORS_ORIGINS` | JSON list of allowed browser origins. Defined but not applied by the 1.0.x API; the UI is served from the same origin, so no CORS is needed | `[]` |
| `RATE_LIMIT_AUTH` | Rate limit on sign-in, smart-card and token endpoints, per client address ([section 4](#4-ports-and-https)) | `10/minute` |
| `RATE_LIMIT_DEVICES` | Rate limit on device event ingest | `600/minute` |
| `RATE_LIMIT_MIGRATION` | Rate limit on migration uploads | `10/minute` |
| `UPLOAD_MAX_MB` | Largest migration file accepted, in MB | `25`. nginx also limits request bodies to 25 MB (`client_max_body_size` in `ops/nginx/default.conf.template`), so raising this alone has no effect |
| `SIP2_HOST` | Address the SIP2 listener binds to | `127.0.0.1`. Set `0.0.0.0` to accept connections from outside the container |
| `SIP2_PORT` | SIP2 listener port | `6001` |
| `SIP2_ALLOWED_HOSTS` | JSON list of client addresses allowed to connect to SIP2 | `[]`. An empty list refuses every connection (since 1.0.2, DEF-017) |
| `RUN_WORKER` | Run the outbox worker (notifications) and the SIP2 listener in the API process | `true` |
| `OUTBOX_DIR` | Folder for mock notification output | Fixed by compose: `/app/outbox` (volume `nexus_outbox`) |
| `BACKUP_DIR` | Backup folder | Fixed by compose: `/backups` (volume `nexus_backups`) |
| `LICENCE_FILE` | Licence file path | Fixed by compose: `/app/licence/licence.json` (host folder `licence/`, read-only) |
| `DEMO_PUBLIC_ACCOUNTS` | Public demonstration instances only: the login page lists sign-in details for Librarian, Circulation Clerk, Auditor and Patron `B00001`, never Admin; a warning is logged at start-up | `false` |
| `DEMO_PUBLIC_PASSWORD` | Password the seed gives those four accounts (at least 12 characters when `DEMO_PUBLIC_ACCOUNTS` is on); set it before the first `--demo` seed, and use it nowhere else | empty |

Rate limits use the `slowapi` format: `<count>/<second|minute|hour|day>`.

Two environment variables are read only by the operations tools (`python -m nexus_ops.backup`, `ops/integrity.py`), not by the API:

| Key | Meaning | Default |
|---|---|---|
| `OPS_DATABASE_URL` | Connection URL for backup, restore and integrity, instead of `OWNER_DATABASE_URL` | unset |
| `PG_TOOLS_CONTAINER` | On a development host without `pg_dump`/`pg_restore`, the name of the container to run them in | unset. The API image includes the PostgreSQL 16 client tools |

## 4. Ports and HTTPS

- `HTTPS_PORT` (default `8443`) is published to nginx's port 443 and is written into the redirect: `http://<host>:HTTP_PORT/...` answers `301` to `https://<host>:HTTPS_PORT/...`.
- `HTTP_PORT` (default `8080`) is published to nginx's port 80. It serves only the redirect.
- To use the standard ports set `HTTPS_PORT=443` and `HTTP_PORT=80` and run `docker compose up -d`.
- nginx accepts TLS 1.2 and 1.3 and sends HSTS, a `default-src 'self'` Content-Security-Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Requests to `/api/` (including WebSocket feeds) are proxied to the API.
- The certificate is read from `ops/nginx/certs/nexus.crt` and `ops/nginx/certs/nexus.key`. After replacing them, run `docker compose restart web`.
- nginx sets `X-Forwarded-For` to the address of the connection it received (`$remote_addr`) and discards any value the client sent (since 1.0.2, DEF-015). The API uses that address for the per-client rate limits and records it in the audit log. With Docker's port publishing on a development host this is usually the Docker gateway (for example `172.18.0.1`), so all clients share one address there. A further reverse proxy or load balancer in front of nginx would need the template changed to trust its header; that is not a supported configuration in 1.0.x.

## 5. SIP2 listener (optional)

The SIP2 listener is off by default. SIP2 has no transport security, so enable it only on a trusted network segment and only for named kiosks ([security design §6](../02-design/security-design.md#6-transport-and-network)).

1. In `.env` set:

   ```sh
   SIP2_LISTENER_ENABLED=true
   SIP2_HOST=0.0.0.0
   SIP2_ALLOWED_HOSTS=["10.10.20.31"]
   ```

   The list must name every kiosk. With an empty list the listener starts, logs the warning `SIP2_ALLOWED_HOSTS is empty: every SIP2 connection will be refused` and refuses every connection.

2. Publish the port. The shipped `docker-compose.yml` does not publish 6001; the `api` service needs `ports: ["6001:6001"]`.
3. Run `docker compose up -d`.

Limitations in 1.0.x:

- The install, update and rollback scripts always use `-f docker-compose.yml` only, and an update replaces `docker-compose.yml` with the bundle's copy. A published SIP2 port must therefore be re-applied after every update.
- The allow-list checks the address the container sees. With Docker's port publishing this may be the Docker gateway rather than the kiosk's own address, depending on the Docker networking mode. Check the `SIP2 connection refused from ...` log lines when setting the list.
- The SIP2 listener runs only when `RUN_WORKER=true`.

## 6. `ENVIRONMENT` and the insecure-secret guard

| Value | Where it is set | Effect |
|---|---|---|
| `production` | `ENV ENVIRONMENT=production` in `backend/Dockerfile` | Secret guard on; licence enforced |
| `dev` | `docker-compose.dev.yml` (development override only) | Secret guard off; licence not enforced; the fixed development passwords are accepted |
| `test` | test runs | Same as `dev` |

Any value other than `dev` or `test` is treated as production. Never set `ENVIRONMENT=dev` or `test` on an installation.

Outside `dev` and `test` the API refuses to start (DEF-009) when:

- `JWT_SECRET` or `LICENCE_KEY` starts with `dev-` or `replace`, or is shorter than 32 characters
- the password in `DATABASE_URL` or `OWNER_DATABASE_URL` is a development password (`devapp`, `devowner`) or starts with `replace`

The error names only the settings at fault, never their values. The API container exits, and the installer or update reports that the API is not healthy. Read the reason with:

```sh
docker compose logs api
```

Fix `.env` (or generate new values) and run `docker compose up -d`.

## 7. Switching adapters

Each external service is reached through an adapter chosen by an `ADAPTER_*` key (`backend/app/integrations/registry.py`):

| Key | Accepted values in 1.0.x |
|---|---|
| `ADAPTER_EMAIL` | `mock` |
| `ADAPTER_SMS` | `mock` |
| `ADAPTER_PRINT` | `mock` |
| `ADAPTER_CAMERA` | `mock` |
| `ADAPTER_CREDENTIALS` | `mock` |
| `ADAPTER_LEGACY` | `db` |

- To switch, set the key in `.env` and run `docker compose up -d`.
- The value is looked up when the adapter is used, not at start-up. An unknown value does not stop the API; the operation that needs the adapter fails with `500` and code `ERR_CONFIG`. Check the value after any change.
- A vendor adapter is added in code by registering a new value for its kind (`register(kind, name, factory)`) in a new release. Real vendor adapters (SMTP, SMS gateway, CCTV/VMS, RFID SDKs) are in the [production backlog](../09-limitations-and-backlog/production-backlog.md). The adapter contracts are in the [interface design](../02-design/interface-design.md).
- Mock notifications are written to the outbox volume (`/app/outbox` in the API container).

## 8. Licence file

| Item | Value |
|---|---|
| Host location | `licence/licence.json` in the installation folder |
| Container location | `/app/licence/licence.json` (read-only mount) |
| Verified with | `LICENCE_KEY` in `.env` (HMAC-SHA256) |
| Read | Once, when the API starts. Restart the API after replacing the file |
| Status | `licence` field of `/api/v1/version`: `valid`, `missing`, `invalid` or `expired` |

Installing and checking a licence is described in the [installation guide](installation-guide.md#6-licence).

## 9. Front-end build setting

The UI has one build-time setting, `VITE_CARD_READER` (default `CARD-01`): the device ID of the smart-card reader the sign-in page listens to. It is compiled into the `nexus-web` image when the bundle is built and cannot be changed in `.env`. The UI contains no secrets.

## 10. Device simulator (demonstration only)

The `devsim` service runs only with `--profile demo`. Its settings are fixed in `docker-compose.yml` (`SIM_API=http://api:8000/api/v1`, `SIM_PANEL_HOST=0.0.0.0`, published on `127.0.0.1:8100`) and it reads device keys from `ops/demo-credentials.txt`.
