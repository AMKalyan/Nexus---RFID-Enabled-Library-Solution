#!/bin/sh
# Restore a backup taken by ops/backup.sh: ops/restore.sh <backup-file-name>
# The API is stopped during the restore so no session writes to the database. It is started again afterwards,
# also when the restore fails (DEF-019), so a refused or broken backup never leaves the site down.
set -eu
[ $# -eq 1 ] || { echo "usage: ops/restore.sh <backup-file-name>  (see: docker compose exec api python -m nexus_ops.backup list)"; exit 2; }
cd "$(dirname "$0")/.."
docker compose stop web api
status=0
docker compose run --rm --no-deps api python -m nexus_ops.backup restore "$1" --yes || status=$?
docker compose start api web
if [ "$status" -ne 0 ]; then
  echo "Restore FAILED (exit $status): the previous data is still in place and the services were restarted."
  exit "$status"
fi
echo "Restore complete. Check: docker compose exec api python /app/ops/integrity.py snapshot"
