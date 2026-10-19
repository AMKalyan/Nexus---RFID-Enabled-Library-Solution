# Security Design

This document implements NFR 02 and SOP §10, with the rules from `docs/00-project-control/engineering-standards.md` applied to the design.

## 1. Assets and trust boundaries

| Asset | Sensitivity | Where it lives |
|---|---|---|
| Existing ILMS records | Critical (integrity) | `legacy_ilms` schema |
| Member personal data (name, email, phone, card UID) | High (privacy) | `nexus.member`, outbox |
| Circulation and fine history | High | `nexus.loan`, `nexus.fine` |
| Staff credentials and tokens | High | Hashes in `staff_user`, `refresh_token` |
| Audit log | High (integrity) | `nexus.audit_log` |
| Device API keys, JWT signing key, DB passwords | Secret | `.env` on the server only |

Trust boundaries:
1. Browser ↔ nginx (TLS)
2. Devices / NCIP / SIP2 clients ↔ nginx (TLS + device or agency key)
3. API ↔ PostgreSQL (internal Docker network, per-role credentials)
4. Migration upload ↔ staging (untrusted file content)

## 2. Threats and controls (STRIDE summary)

| Threat | Example | Control | Verified by |
|---|---|---|---|
| Spoofing | Stolen password; fake device posting events | argon2id hashes; rate-limited login; short JWT (15 min) + rotating refresh (8 h); per-device API keys | Auth tests; rate-limit test |
| Tampering | Modifying legacy records; editing audit history | DB grants: `SELECT` only on `legacy_ilms`, `INSERT/SELECT` only on `audit_log`; ORM parameter binding | Permission-denied tests; integrity checksums |
| Repudiation | Staff denies issuing an item | Audit entry for every admin, circulation, fine, tagging, migration and gate action, with actor, channel, IP and correlation ID | Audit assertions in acceptance tests |
| Information disclosure | Patron reads another patron's loans; stack trace in response; PII in logs | RBAC + ownership check on every parameterised route; global sanitised error handler; log masking filter | IDOR test; error-leak test; log-mask unit test |
| Denial of service | Login brute force; event flood; 1 GB upload | `slowapi` limits on auth, device ingest and migration; upload size limit (25 MB) and row cap (100k) | Rate-limit tests |
| Elevation of privilege | Clerk calls admin endpoint; token role tampering | Signed JWT with server-side permission lookup per request; permission declared per route | RBAC matrix tests |

## 3. RBAC matrix

| Permission | Admin | Librarian | Circulation Clerk | Auditor | Patron |
|---|:-:|:-:|:-:|:-:|:-:|
| `catalog.read` | ✔ | ✔ | ✔ | ✔ | (OPAC only) |
| `catalog.write` | ✔ | ✔ | | | |
| `tagging.write` | ✔ | ✔ | | | |
| `members.read` | ✔ | ✔ | ✔ | ✔ | self |
| `members.write`, `members.block` | ✔ | ✔ | | | |
| `member.pii.read` | ✔ | ✔ | ✔ | | self |
| `circulation.read` | ✔ | ✔ | ✔ | ✔ | self |
| `circulation.checkout` / `checkin` | ✔ | ✔ | ✔ | | |
| `circulation.renew` | ✔ | ✔ | ✔ | | self |
| `fines.read` | ✔ | ✔ | ✔ | ✔ | self |
| `fines.write` | ✔ | ✔ | | | |
| `inventory.read` / `inventory.write` | ✔ | ✔ | | ✔ / — | |
| `gate.read` | ✔ | ✔ | ✔ | ✔ | |
| `devices.read` | ✔ | ✔ | | ✔ | |
| `notifications.read` | ✔ | ✔ | | ✔ | |
| `reports.read` | ✔ | ✔ | | ✔ | |
| `audit.read` | ✔ | | | ✔ | |
| `migration.run` | ✔ | | | | |
| `admin.users.write`, `admin.roles.write`, `admin.policies.write`, `admin.settings.write`, `admin.devices.write`, `admin.health` | ✔ | | | | |

"self" means the request is allowed only when the target member ID equals the authenticated patron's ID.

## 4. Authentication details

- **Password login:** argon2id with time cost 3, 64 MiB memory and parallelism 2. A generic `INVALID_CREDENTIALS` response avoids revealing whether a username exists.
- **Tokens:** access JWT (HS256, 15 min) with claims `sub`, `typ` (`staff`/`patron`), `role`, `jti`. Permissions are re-read from the database on each request, so role changes take effect immediately. Refresh tokens are opaque random values stored as SHA-256 hashes and rotated on every use; reusing an old one revokes the whole token family.
- **Smart card:** challenge-response handshake (interface design §2.4). Challenges are single-use, last 60 s, and are bound to the reader code. Unknown or deactivated cards are refused and audited.
- **Devices and NCIP agencies:** API keys of 32 random bytes, stored hashed and rotatable by an Admin.

## 5. Data protection

- **Logs:** structured JSON. A masking filter replaces emails (`a***@example.org`), phone numbers (last 2 digits kept), card UIDs and names before output.
- **Audit details** store entity IDs and changed field names. Values are stored only for non-PII fields.
- **Report exports** omit or mask PII unless the caller has `member.pii.read`.
- **Backups** contain PII. They are stored on the server's backup volume, never inside the repository or the update bundles.

## 6. Transport and network

- nginx terminates TLS 1.2+ using a certificate generated at install (self-signed for the prototype; site PKI in production). It sends HSTS and a strict CSP (`default-src 'self'`).
- PostgreSQL is reachable only on the internal Docker network.
- The SIP2 TCP listener is off by default. When it is enabled, it is restricted by IP allow-list, since SIP2 itself has no transport security.

## 7. Supply chain

- Dependencies are pinned. `pip-audit` and `npm audit` run in the build pipeline, and `bandit` covers Python static analysis.
- Container base images are pinned by exact tag (for example `python:3.12.7-slim`, `postgres:16.4-alpine`), and the offline bundle carries SHA-256 checksums of every artefact. Pinning by digest is in the production backlog.
- Offline activation uses an HMAC-signed licence file. Its key is distributed out-of-band (A-12).
