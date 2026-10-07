#!/bin/sh
# Restore a backup taken by ops/backup.sh: ops/restore.sh <backup-file-name>
# The API is stopped during the restore so no session writes to the database, then started again.
set -eu
[ $# -eq 1 ] || { echo "usage: ops/restore.sh <backup-file-name>  (see: docker compose exec api python -m nexus_ops.backup list)"; exit 2; }
cd "$(dirname "$0")/.."
docker compose stop web api
docker compose run --rm --no-deps api python -m nexus_ops.backup restore "$1" --yes
docker compose start api web
echo "Restore complete. Check: docker compose exec api python /app/ops/integrity.py snapshot"
