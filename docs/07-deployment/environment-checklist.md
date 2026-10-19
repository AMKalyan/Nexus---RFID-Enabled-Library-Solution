# Environment Checklist

Complete this checklist before running the installer ([installation guide](installation-guide.md)). Nexus runs as four Linux containers (`db`, `api`, `web` and the optional `devsim`) under Docker Compose. Everything it needs comes from the offline bundle, so the host needs no internet access.

## 1. Host platform

| Check | Requirement | Notes |
|---|---|---|
| Operating system | Windows Server 2022 or a Linux VM (any current distribution with Docker Engine) | Nexus has no native Windows service. It runs only as Linux containers. A native service package is in the [production backlog](../09-limitations-and-backlog/production-backlog.md) |
| Container runtime | Docker that runs **Linux containers**, with the Compose v2 plugin (`docker compose`, not `docker-compose`) | On Windows this means a WSL 2 or Hyper-V Linux backend. Windows containers mode does not work |
| Docker starts at boot | Docker Desktop set to start when the host signs in, or the Docker Engine service enabled at boot (`systemctl enable docker` on Linux) | The services have `restart: unless-stopped` (since 1.0.2, DEF-018), so they come back after a host or Docker restart, but only once Docker itself is running |
| Docker access | The installing account can run `docker` without a prompt (local Administrators / `docker-users` on Windows, the `docker` group or root on Linux) | The scripts call `docker load`, `docker run` and `docker compose` |
| Shell, Windows | Windows PowerShell 5.1 or later | The `.ps1` scripts are run with `powershell -ExecutionPolicy Bypass -File ...` |
| Shell, Linux | POSIX `sh` with GNU coreutils and GNU `sed`/`date`, plus `sha256sum`, `od` and `unzip` | The `.sh` scripts use `sed -i`, `date -d` and `sha256sum -c`. `unzip` is needed by `update.sh` when it is given a `.zip` |
| Rehearsed platform | Windows 11 with Docker Desktop (WSL 2) | The full offline install, update and rollback was rehearsed there with the PowerShell scripts ([AC 09 record](../../ops/tests/ac09_offline_lifecycle.md)). Windows Server 2022 and the shell scripts' full lifecycle were not rehearsed |

## 2. Hardware (prototype sizing)

These figures are recommendations for running the prototype. They are **not measured capacity figures**.

| Resource | Minimum | Recommended | Basis |
|---|---|---|---|
| CPU | 2 vCPU | 4 vCPU | The API is one Python process. Under load it uses about one core (about 115% CPU at 50 users) and handles about 86 req/s ([performance results](../06-testing/performance-results.md)). Extra cores mostly help PostgreSQL and nginx |
| RAM | 4 GB available to Docker | 8 GB available to Docker | PostgreSQL, the API, nginx and the WSL 2 / VM overhead |
| Disk | 20 GB free | 50 GB free | Each bundle is about 230 MB and its loaded images several times that. Images of the previous release stay loaded after an update, for rollback. Database volume, backups and integrity reports grow with use |

Known limit: at 50 concurrent users the latency targets are missed because the single API process saturates (DEF-008 in the [defect log](../00-project-control/defect-log.md)). Plan for about 10 concurrent staff users per installation. Running more API workers is not a supported configuration yet.

## 3. Network and ports

| Port (host) | Protocol | Purpose | Set by | Default |
|---|---|---|---|---|
| `HTTPS_PORT` | TCP, HTTPS | Staff UI, OPAC and API (nginx terminates TLS 1.2/1.3) | `.env` | `8443` |
| `HTTP_PORT` | TCP, HTTP | Redirect only: answers every request with `301` to `https://<host>:HTTPS_PORT` | `.env` | `8080` |
| `6001` | TCP, SIP2 | Optional SIP2 listener for self-service kiosks. Off by default (`SIP2_LISTENER_ENABLED=false`) | `.env` | not published |
| `127.0.0.1:8100` | TCP, HTTP | Device simulator panel, demonstration only (`--profile demo`) | `docker-compose.yml` | loopback only |

- To serve on the standard ports, set `HTTPS_PORT=443` and `HTTP_PORT=80` ([configuration guide](configuration-guide.md#4-ports-and-https)).
- PostgreSQL is not published on the host. It is reachable only on the internal Docker network. Only the development override (`docker-compose.dev.yml`) publishes it, on `5433`.
- The shipped `docker-compose.yml` does **not** publish port 6001. Enabling SIP2 needs a site compose change as well as the `.env` settings. See the [configuration guide](configuration-guide.md#5-sip2-listener-optional).
- Open the HTTPS port (and the HTTP redirect port, if used) in the host firewall for the staff and OPAC networks. Keep 6001 limited to the kiosk addresses.

## 4. Certificate

| Check | Notes |
|---|---|
| Site certificate and key in PEM format | Installed as `ops/nginx/certs/nexus.crt` and `ops/nginx/certs/nexus.key` in the installation folder |
| Subject alternative names cover the host name staff will use | The installer only creates a self-signed certificate when `nexus.crt` is missing. It covers `localhost`, `nexus.local` and `127.0.0.1` only, and is valid for 825 days |
| Clients trust the issuing CA | With the self-signed certificate, browsers show a warning until the certificate is trusted |
| Renewal date recorded | nginx reads the files at start-up. Replace both files and run `docker compose restart web` |

## 5. Time synchronisation

The containers use the host clock. Keep the host synchronised to the site's time source (Windows Time service joined to the domain or an NTP server; `chronyd` or `systemd-timesyncd` on Linux).

Clock errors affect:

- access token expiry (15 minutes by default) and refresh token expiry (8 hours)
- licence expiry, which is checked against the current date
- audit log, loan, fine and backup timestamps (backup file names use UTC)

## 6. Backup storage

| Check | Notes |
|---|---|
| Space for backups | Backups are written to the Docker volume `nexus_backups` (mounted at `/backups` in the API container), on the same disk as Docker's data. Nothing prunes old backups |
| Off-host copy | A location outside the host (network share or removable media) for copies of the dumps and their `.sha256` files. See [backup and restore](backup-restore.md#copying-backups-off-the-host) |
| Secure storage for site secrets | `.env`, `licence/licence.json` and `ops/nginx/certs/` are not in the database dump. Keep a protected copy |

## 7. Before you start

- [ ] Host platform, Docker with Linux containers and Compose v2 checked, and Docker set to start at boot (section 1)
- [ ] CPU, RAM and disk meet at least the minimum (section 2)
- [ ] HTTPS and redirect ports chosen and opened; port 6001 only if SIP2 is needed (section 3)
- [ ] Site certificate ready, or the self-signed certificate accepted for evaluation (section 4)
- [ ] Host time synchronised (section 5)
- [ ] Backup storage and secure storage for secrets agreed (section 6)
- [ ] Offline bundle `nexus-<version>.zip` copied to the host, and a licence file if one was issued for the site
