# D7 Deployment Package

| Document | Contents |
|---|---|
| [Environment checklist](environment-checklist.md) | Host platform, prototype sizing, ports, certificate, time synchronisation and backup storage to prepare before installing |
| [Installation guide](installation-guide.md) | Step-by-step offline installation from `nexus-<version>.zip` with `ops/install.ps1` / `ops/install.sh`, options and licence activation |
| [Configuration guide](configuration-guide.md) | Every `.env` key with its meaning and default, adapter switching, `ENVIRONMENT` and the secret guard, ports, SIP2 and the licence file |
| [Backup and restore](backup-restore.md) | Backup schedule, backup, checksum verification, restore and the legacy integrity check |
| [Hosting options](hosting-options.md) | Putting a public demonstration online: a single VM (recommended), a split Netlify/Vercel UI with a container-hosted API, and why Netlify or Vercel alone cannot run Nexus |
| [Update and rollback](update-rollback.md) | Offline update with automatic rollback, `ops/state.json`, manual rollback and the restore fallback |
