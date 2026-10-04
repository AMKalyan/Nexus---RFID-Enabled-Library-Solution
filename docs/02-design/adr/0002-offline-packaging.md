# ADR-0002: Offline packaging with Docker image archives

- Status: Accepted
- Date: 2026-10-04

## Context
FR 12 and AC 09 require installation, update, upgrade and rollback without internet access, on Windows Server 2022 or later.

## Decision
- Each release is an offline bundle `nexus-<version>.zip` containing:
  - `docker save` archives of the versioned images (`nexus-api`, `nexus-web`, and the pinned `postgres` image)
  - `docker-compose.yml`
  - `.env.example`
  - install / update / rollback / backup / restore scripts (`.ps1` and `.sh`)
  - `SHA256SUMS`, the SBOM and release notes
- **Update:**
  1. Verify the checksums.
  2. Take a `pg_dump` backup.
  3. `docker load` the new images.
  4. Switch `NEXUS_VERSION` and run Alembic upgrade on start.
  5. Health check; roll back automatically on failure.
- **Rollback:** switch `NEXUS_VERSION` back to the previous tag, run Alembic downgrade to that release's recorded revision, or restore the pre-update backup when a downgrade isn't safe.

## Consequences
- Identical behaviour on any Docker host. No package managers are needed on site.
- On Windows Server, Linux containers require Docker with a Linux VM backend (or a Linux VM host). This is documented in the deployment guide; a native Windows-service packaging is listed in the production backlog.
- Bundle size is dominated by the images (about 400 MB). This is acceptable for removable-media delivery.
