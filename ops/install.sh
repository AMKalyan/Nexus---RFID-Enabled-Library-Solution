#!/bin/sh
# Offline installation from an unzipped bundle (FR 12, AC 09). Run from the folder the bundle was unzipped into:
#   sh ops/install.sh [--verify-only] [--demo] [--licence FILE --licence-key-file KEY_FILE]
# --verify-only  check SHA256SUMS and stop       --demo  seed synthetic data and issue a 30-day demo licence
# --licence FILE --licence-key-file KEY_FILE  install the site licence and the key it was signed with
# No network access is needed: images come from images.tar.gz and secrets are generated locally.
. "$(dirname "$0")/common.sh"
VERIFY_ONLY=""; DEMO=""; LICENCE=""; LICENCE_KEY_FILE=""; LICENCE_CHANGED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=1 ;;
    --demo) DEMO=1 ;;
    --licence) LICENCE="$2"; shift ;;
    --licence-key-file) LICENCE_KEY_FILE="$2"; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done

verify_bundle "$ROOT" || { echo "Bundle verification FAILED: do not install this copy."; exit 1; }
echo "bundle verified ($(wc -l < SHA256SUMS) files)"
[ -n "$VERIFY_ONLY" ] && exit 0

V="$(cat VERSION)"
echo "== loading images for $V"
docker load -i images.tar.gz

if [ ! -f .env ]; then
  echo "== generating .env with new secrets"
  cp .env.example .env
  for token in replace-owner-password replace-app-password replace-readonly-password \
               replace-with-64-random-hex-chars replace-with-licence-hmac-key; do
    sed -i "s/$token/$(rand_hex 32)/g" .env
  done
fi
env_set NEXUS_VERSION "$V"
# The site licence must verify against the key it was issued with (DEF-020).
[ -n "$LICENCE_KEY_FILE" ] && env_set LICENCE_KEY "$(tr -d '\r\n' < "$LICENCE_KEY_FILE")"

mkdir -p ops/nginx/certs licence
if [ ! -f ops/nginx/certs/nexus.crt ]; then
  echo "== generating a self-signed TLS certificate (replace with the site's own certificate)"
  MSYS_NO_PATHCONV=1 docker run --rm --user 0 -v "$(host_path ops/nginx/certs):/certs" --entrypoint openssl "nexus-api:$V" \
    req -x509 -nodes -newkey rsa:2048 -days 825 -keyout /certs/nexus.key -out /certs/nexus.crt \
    -subj "/CN=nexus.local" -addext "subjectAltName=DNS:localhost,DNS:nexus.local,IP:127.0.0.1"
fi

if [ -n "$LICENCE" ]; then
  cp "$LICENCE" licence/licence.json
  LICENCE_CHANGED=1
elif [ -n "$DEMO" ] && [ ! -f licence/licence.json ]; then
  echo "== issuing a 30-day demonstration licence"
  MSYS_NO_PATHCONV=1 docker run --rm --user 0 -e LICENCE_KEY="$(env_get LICENCE_KEY)" -v "$(host_path licence):/out" \
    --entrypoint python "nexus-api:$V" /app/ops/licence.py issue --site "Demonstration site" \
    --expires "$(date -d '+30 days' +%F)" --out /out/licence.json
  LICENCE_CHANGED=1
fi

echo "== starting Nexus $V"
dc up -d --no-build
# The licence is read when the API starts: restart it so a newly installed licence takes effect.
[ -n "$LICENCE_CHANGED" ] && dc restart api
wait_healthy 180

if [ -n "$DEMO" ]; then
  echo "== seeding synthetic demonstration data"
  dc exec -T api python -m app.db.seed --legacy 2000 --demo > /dev/null
  dc cp api:/app/ops/demo-credentials.txt ops/demo-credentials.txt
  echo "demo sign-in details: ops/demo-credentials.txt (keep private)"
fi
echo "version: $(api_get /version)"
echo "Nexus $V is running at https://localhost:$(env_get HTTPS_PORT | grep . || echo 8443)/"
