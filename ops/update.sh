#!/bin/sh
# Apply an offline update bundle to this installation (FR 12, AC 09). Run from the installed folder:
#   sh ops/update.sh /path/to/nexus-1.0.1.zip     (or an unzipped bundle folder)
# Verifies the bundle, takes a backup, records the current release in ops/state.json, loads the new images and
# starts them. If the new release is not healthy within 120 s it rolls back automatically.
. "$(dirname "$0")/common.sh"
SRC="${1:?usage: update.sh <bundle.zip | bundle folder>}"
WORK=""
case "$SRC" in
  *.zip) WORK="$(mktemp -d)"; unzip -q "$SRC" -d "$WORK"; NEW="$(ls -d "$WORK"/nexus-*)" ;;
  *) NEW="$(cd "$SRC" && pwd)" ;;
esac
cleanup() { [ -n "$WORK" ] && rm -rf "$WORK"; return 0; }
trap cleanup EXIT

verify_bundle "$NEW" || { echo "Update bundle verification FAILED: nothing was changed."; exit 1; }
FROM="$(env_get NEXUS_VERSION)"; TO="$(cat "$NEW/VERSION")"
[ "$FROM" != "$TO" ] || { echo "already at $TO"; exit 0; }
FROM_REV="$(api_get /version | json_field alembic_rev)"
echo "== updating $FROM (schema $FROM_REV) to $TO"

echo "== backup before update"
BACKUP="$(dc exec -T api python -m nexus_ops.backup create --reason "pre-update-$FROM-$TO" | sed -n 's|^backup: .*/||p')"
[ -n "$BACKUP" ] || { echo "backup failed: nothing was changed"; exit 1; }

rm -rf ops/previous && mkdir -p ops/previous
cp docker-compose.yml VERSION RELEASE-NOTES.md ops/previous/ 2>/dev/null || true
printf '{"previous_version": "%s", "previous_alembic_rev": "%s", "current_version": "%s", "backup": "%s", "updated_at": "%s"}\n' \
  "$FROM" "$FROM_REV" "$TO" "$BACKUP" "$(date -u +%FT%TZ)" > ops/state.json

echo "== loading images for $TO"
docker load -i "$NEW/images.tar.gz"
cp "$NEW/docker-compose.yml" "$NEW/VERSION" "$NEW/RELEASE-NOTES.md" "$NEW/.env.example" .
for f in "$NEW"/ops/*.sh "$NEW"/ops/*.ps1 "$NEW"/ops/*.py; do cp "$f" ops/; done
cp "$NEW/ops/nginx/default.conf.template" ops/nginx/
env_set NEXUS_VERSION "$TO"

echo "== starting $TO"
dc up -d --no-build
if wait_healthy 120; then
  echo "updated to $TO: $(api_get /version)"
  echo "backup taken before the update: $BACKUP (rollback: sh ops/rollback.sh)"
else
  echo "== $TO is not healthy: rolling back to $FROM"
  sh ops/rollback.sh
  exit 1
fi
