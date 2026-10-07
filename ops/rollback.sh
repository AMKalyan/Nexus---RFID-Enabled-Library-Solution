#!/bin/sh
# Return to the release recorded in ops/state.json by the last update (FR 12, AC 09):
#   sh ops/rollback.sh
# 1. Downgrade the schema with the newer image (only it has the newer migration scripts).
# 2. Restore the previous compose file and switch NEXUS_VERSION back.
# 3. If the downgrade fails, restore the backup taken before the update instead.
. "$(dirname "$0")/common.sh"
[ -f ops/state.json ] || { echo "no ops/state.json: nothing to roll back"; exit 1; }
field() { sed -n "s/.*\"$1\": \"\([^\"]*\)\".*/\1/p" ops/state.json; }
PREV="$(field previous_version)"; PREV_REV="$(field previous_alembic_rev)"; CUR="$(field current_version)"; BACKUP="$(field backup)"
echo "== rolling back $CUR to $PREV (schema $PREV_REV)"

env_set NEXUS_VERSION "$CUR"
dc stop web api
if dc run --rm --no-deps api alembic downgrade "$PREV_REV"; then
  echo "schema downgraded to $PREV_REV"
  RESTORE=""
else
  echo "schema downgrade failed: restoring backup $BACKUP"
  RESTORE=1
fi

[ -f ops/previous/docker-compose.yml ] && cp ops/previous/docker-compose.yml ops/previous/VERSION .
env_set NEXUS_VERSION "$PREV"
if [ -n "$RESTORE" ]; then
  dc run --rm --no-deps api python -m nexus_ops.backup restore "$BACKUP" --yes
fi

dc up -d --no-build
wait_healthy 120
echo "rolled back to $PREV: $(api_get /version)"
mv ops/state.json "ops/state-rolled-back-$(date -u +%Y%m%dT%H%M%SZ).json"
