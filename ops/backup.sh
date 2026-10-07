#!/bin/sh
# Take a verified backup inside the running stack: ops/backup.sh [reason]
set -eu
cd "$(dirname "$0")/.."
docker compose exec -T api python -m nexus_ops.backup create --reason "${1:-manual}"
