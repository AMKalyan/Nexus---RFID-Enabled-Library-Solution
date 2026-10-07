#!/bin/sh
# Bundle integrity test (FR 12, AC 09): build a bundle, check its contents and checksums, and prove that a
# corrupted image archive is refused before anything is installed.
#   bash ops/tests/test_bundle_scripts.sh [version]   (default: contents of VERSION)
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(cat "$ROOT/VERSION")}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

sh "$ROOT/ops/build_bundle.sh" "$VERSION" || fail "build_bundle.sh exited non-zero"
ZIP="$ROOT/ops/bundles/nexus-$VERSION.zip"
[ -f "$ZIP" ] || fail "missing $ZIP"

(cd "$WORK" && unzip -q "$ZIP") || fail "cannot unzip"
DIR="$WORK/nexus-$VERSION"
for f in SHA256SUMS images.tar.gz docker-compose.yml .env.example VERSION RELEASE-NOTES.md \
         ops/install.sh ops/install.ps1 ops/update.sh ops/update.ps1 ops/rollback.sh ops/rollback.ps1 \
         ops/common.sh ops/common.ps1 ops/backup.sh ops/restore.sh ops/integrity.py ops/licence.py ops/db/init/01-roles.sh \
         ops/nginx/default.conf.template; do
  [ -e "$DIR/$f" ] || fail "bundle lacks $f"
done
[ "$(cat "$DIR/VERSION")" = "$VERSION" ] || fail "VERSION in bundle is not $VERSION"
(cd "$DIR" && sha256sum -c --quiet SHA256SUMS) || fail "checksums do not verify"
sh "$DIR/ops/install.sh" --verify-only || fail "verify-only rejected an intact bundle"

# Flip one byte in the middle of the image archive: verification must refuse the bundle.
SIZE=$(wc -c < "$DIR/images.tar.gz")
printf 'X' | dd of="$DIR/images.tar.gz" bs=1 seek=$((SIZE / 2)) conv=notrunc 2>/dev/null
if sh "$DIR/ops/install.sh" --verify-only; then fail "verify-only accepted a corrupted images.tar.gz"; fi

echo "PASS: bundle nexus-$VERSION builds, verifies, and refuses a corrupted archive"
