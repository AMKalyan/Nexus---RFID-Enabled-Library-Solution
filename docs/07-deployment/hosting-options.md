# Hosting Options for a Public Demonstration

How to put Nexus on the internet so that others can try it, and what each kind of host needs. This is for a **demonstration instance with synthetic data**. A real library installs offline from a bundle; see the [installation guide](installation-guide.md).

## What Nexus needs from a host

| Need | Why |
|---|---|
| A long-running API process | FastAPI/uvicorn serves the API, and runs the notification outbox worker and the device command bus inside the same process |
| WebSockets | The gate monitor, live inventory grid, tagging screen and smart-card sign-in use `/api/v1/ws/live` and `/api/v1/ws/card` |
| PostgreSQL 16 with its own roles and schemas | `legacy_ilms`, `nexus` and `staging` schemas; the roles `nexus_app`, `legacy_owner` and the read-only role are created by `ops/db/init/01-roles.sh`; triggers keep the search index current |
| `pg_dump` / `pg_restore` | Backups before every migration commit and update, and restores (shipped in the API image) |
| Persistent volumes | Database, backups, notification outbox |
| HTTPS | Tokens and passwords travel in requests; nginx terminates TLS and sets HSTS and CSP |

## Options

| Option | Works? | Summary |
|---|---|---|
| **A. One small virtual machine** (recommended) | Everything, with no code changes | Run the shipped Docker Compose stack on a VM with a domain name and a real certificate |
| **B. UI on Netlify or Vercel, API on a container host** | Yes, after code changes | Static UI on Netlify or Vercel; API container on Render, Railway, Fly.io or similar; a managed PostgreSQL |
| **C. Netlify or Vercel alone** | No | They host static files and short-lived serverless functions. There is nowhere to run the API process, its WebSockets, its background worker or PostgreSQL, so only the sign-in page would load |

### A. One small virtual machine (recommended)

**Requirements**

- **A Linux VM:** 2 vCPU, 4 GB RAM and 40 GB disk is enough for the demo. Any provider works, for example Hetzner, DigitalOcean, AWS Lightsail, or the Azure or Google Cloud entry tiers. Install Docker Engine and the Compose plugin, and enable Docker at boot. The stack restarts by itself (`restart: unless-stopped`).
- **A domain name** with an `A` record pointing at the VM, for example `nexus-demo.example.org`.
- **Firewall:** open TCP 443 and 80. Do not publish 5432 or 6001 (PostgreSQL stays internal; the SIP2 listener is off).
- **A certificate** from Let's Encrypt in place of the self-signed one.

**Steps**

1. Build the bundle on any machine with the repository (`sh ops/build_bundle.sh <version>`), copy `ops/bundles/nexus-<version>.zip` to the VM and unzip it.
2. Install once. This generates `.env` with new secrets and starts the stack:

   ```sh
   sh ops/install.sh
   ```

3. Add the public-demo settings to the generated `.env`, then run the installer again with demonstration data. This also issues a 30-day demonstration licence:

   ```sh
   cat >> .env <<'END'
   HTTPS_PORT=443
   HTTP_PORT=80
   DEMO_PUBLIC_ACCOUNTS=true
   DEMO_PUBLIC_PASSWORD=<a new password used nowhere else, at least 12 characters>
   END
   sh ops/install.sh --demo
   ```

   The seed gives the Librarian, Circulation Clerk, Auditor and Patron `B00001` accounts the `DEMO_PUBLIC_PASSWORD`, and the login page lists them. The Admin password stays random and is only in `ops/demo-credentials.txt` on the VM. The password is applied only to accounts the seed creates, so set it before the first `--demo` run.
4. Replace the self-signed certificate. nginx reads `ops/nginx/certs/nexus.crt` and `nexus.key`. With certbot's standalone mode, port 80 must be free while it runs:

   ```sh
   docker compose stop web
   certbot certonly --standalone -d nexus-demo.example.org
   cp /etc/letsencrypt/live/nexus-demo.example.org/fullchain.pem ops/nginx/certs/nexus.crt
   cp /etc/letsencrypt/live/nexus-demo.example.org/privkey.pem  ops/nginx/certs/nexus.key
   docker compose start web
   ```

   Renew from cron with the same stop, copy and start steps as certbot's pre and post hooks.
5. Reset the demo every night, so visitors' changes do not accumulate:
   1. Right after installing, take a clean backup: `sh ops/backup.sh clean-demo`.
   2. Schedule a nightly restore of it: `sh ops/restore.sh <clean-demo file>`.
6. Monitor `https://nexus-demo.example.org/api/v1/health`. It returns 200 when healthy and 503 when a check fails.

### B. UI on Netlify or Vercel, API on a container host

This splits the stack across origins. The UI works as a static site:

- build command: `npm ci && npm run build` in `frontend/`
- publish directory: `frontend/dist`
- a rewrite of all routes to `/index.html` for the single-page app

The API and database go to a container host such as Render, Railway or Fly.io, with that platform's PostgreSQL or a provider such as Neon.

**Code changes this needs (not in the current release):**

| Change | Why |
|---|---|
| A configurable API and WebSocket base URL (for example `VITE_API_BASE`) | `frontend/src/api/client.ts` uses the relative `/api/v1`, and `frontend/src/lib/live.ts` builds WebSocket URLs from the page's own host. Netlify and Vercel rewrites can forward HTTP but do not proxy WebSockets, so the UI must connect to the API's domain directly |
| Apply `CORS_ORIGINS` | The setting exists in `app/core/config.py` but no CORS middleware uses it. A cross-origin UI needs it to allow the UI's domain |
| Trusted-proxy configuration | The image runs uvicorn with `--forwarded-allow-ips='*'`, which is safe only because our nginx overwrites `X-Forwarded-For` (DEF-015). Behind another platform's proxy, trust only that proxy's addresses, or rate limits and audit addresses become spoofable again |
| Database roles | Managed PostgreSQL services restrict superuser rights. `ops/db/init/01-roles.sh` must be adapted to create the roles and grants the platform allows, keeping the application role read-only on `legacy_ilms` |
| One API instance | The command bus, live hub, smart-card challenges and rate-limit counters are held in process (production backlog NX-063). Do not scale the API beyond one instance |
| Backups | `ops/backup.*` expects the Compose stack; use the platform's database backups instead, and test a restore |

## Publication checklist

- [ ] Only synthetic data. The seed and the migration sample generator create it; never load real member data.
- [ ] `ENVIRONMENT=production`, which is the image default. The API refuses development or placeholder secrets.
- [ ] Secrets generated for this instance; `.env` and `ops/demo-credentials.txt` never committed or published.
- [ ] `DEMO_PUBLIC_ACCOUNTS=true` only on the demonstration instance, with a `DEMO_PUBLIC_PASSWORD` used nowhere else.
- [ ] Admin is never listed on the login page and keeps a random password.
- [ ] A licence is installed (`--demo` issues a 30-day one). Without a licence, the API is read-only for everyone except Admin.
- [ ] A real certificate; HTTP only redirects to HTTPS.
- [ ] A nightly reset from a clean backup.
- [ ] Health monitoring on `/api/v1/health`.
- [ ] Rate limits are on by default: sign-in 10 per minute per client.

## What visitors can and cannot try

Every screen works for the listed roles: OPAC, circulation desk, catalogue, tagging, inventory, gate monitor, members, reports and dashboard.

There is no RFID hardware on a hosted demo. Tag reads, handheld sweeps, gate passages and card taps come from the device simulator:

```sh
SIM_API=https://nexus-demo.example.org/api/v1 python device-sim/sim.py gate --epc <EPC>
```

The operator can run it against the public URL during a presentation. Otherwise, those flows are shown in the [UAT screenshots](../06-testing/uat-checklist.md).
