#!/bin/sh
# Shared helpers for install.sh, update.sh and rollback.sh. Sourced, not run.
set -eu
OPS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$OPS/.." && pwd)"
cd "$ROOT"

dc() { docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" "$@"; }

# Windows path for docker bind mounts when running under Git Bash; the plain path elsewhere.
host_path() { (cd "$1" && pwd -W 2>/dev/null) || (cd "$1" && pwd); }

verify_bundle() {  # verify_bundle <bundle dir>: every file listed in SHA256SUMS must match
  [ -f "$1/SHA256SUMS" ] || { echo "no SHA256SUMS in $1"; return 1; }
  (cd "$1" && sha256sum -c --quiet SHA256SUMS)
}

rand_hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }

env_get() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1; }

env_set() {  # env_set KEY VALUE: replace or append in .env
  if grep -q "^$1=" "$ROOT/.env"; then sed -i "s|^$1=.*|$1=$2|" "$ROOT/.env"; else printf '%s=%s\n' "$1" "$2" >> "$ROOT/.env"; fi
}

api_status() { docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q api)" 2>/dev/null || echo missing; }

wait_healthy() {  # wait_healthy <seconds>
  i=0
  while [ "$i" -lt "$1" ]; do
    [ "$(api_status)" = healthy ] && return 0
    sleep 3; i=$((i + 3))
  done
  echo "API not healthy after $1 s (status: $(api_status))"; return 1
}

api_get() {  # api_get <path>: GET http://localhost:8000/api/v1<path> from inside the API container
  dc exec -T api python -c "import sys, urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1' + sys.argv[1]).read().decode())" "$1"
}

json_field() {  # json_field <field>: read one top-level field from JSON on stdin
  sed -n "s/.*\"$1\": *\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" | head -1
}
