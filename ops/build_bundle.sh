#!/bin/sh
# Build the offline installation bundle for one release (FR 12, AC 09).
#   sh ops/build_bundle.sh 1.0.0   ->   ops/bundles/nexus-1.0.0.zip
# The working tree must be at that release: VERSION must match and there must be no uncommitted changes.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?usage: build_bundle.sh <version>}"
cd "$ROOT"
[ "$(cat VERSION)" = "$V" ] || { echo "VERSION is $(cat VERSION), not $V"; exit 2; }
if [ -z "${ALLOW_DIRTY:-}" ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "uncommitted changes: commit or stash them (ALLOW_DIRTY=1 overrides for test builds)"; exit 2
fi
if [ -x backend/.venv/Scripts/python.exe ]; then PY=backend/.venv/Scripts/python.exe; else PY=backend/.venv/bin/python; fi

OUT="$ROOT/ops/bundles"
STAGE="$OUT/nexus-$V"
rm -rf "$STAGE" "$OUT/nexus-$V.zip"
mkdir -p "$STAGE/ops/tests" "$STAGE/sbom"

echo "== building images for $V"
NEXUS_VERSION="$V" docker compose --profile demo build api web devsim
echo "== saving images"
docker save "nexus-api:$V" "nexus-web:$V" "nexus-devsim:$V" postgres:16.4-alpine | gzip -1 > "$STAGE/images.tar.gz"

echo "== copying deployment files"
cp docker-compose.yml .env.example VERSION RELEASE-NOTES.md "$STAGE/"
cp ops/install.sh ops/install.ps1 ops/update.sh ops/update.ps1 ops/rollback.sh ops/rollback.ps1 \
   ops/backup.sh ops/backup.ps1 ops/restore.sh ops/restore.ps1 ops/integrity.py ops/licence.py \
   ops/common.sh ops/common.ps1 "$STAGE/ops/"
cp ops/tests/security_smoke.py "$STAGE/ops/tests/"
mkdir -p "$STAGE/ops/db" "$STAGE/ops/nginx"
cp -r ops/db/init "$STAGE/ops/db/"
cp ops/nginx/default.conf.template ops/nginx/gen-cert.sh "$STAGE/ops/nginx/"
cp backend/requirements.txt "$STAGE/sbom/backend-requirements.txt"
cp frontend/package-lock.json "$STAGE/sbom/frontend-package-lock.json"
if [ -f docs/04-repository/sbom-and-licences.md ]; then cp docs/04-repository/sbom-and-licences.md "$STAGE/sbom/"; fi
git rev-parse HEAD > "$STAGE/sbom/source-commit.txt"

echo "== checksums"
(cd "$STAGE" && find . -type f ! -name SHA256SUMS | sed 's|^\./||' | LC_ALL=C sort | xargs -d '\n' sha256sum > SHA256SUMS)

echo "== archive"
(cd "$OUT" && "$ROOT/$PY" -m zipfile -c "nexus-$V.zip" "nexus-$V")
rm -rf "$STAGE"
ls -l "$OUT/nexus-$V.zip"
