#!/bin/sh
# Generates a self-signed certificate for the prototype. Production sites use their own PKI.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"
cd "$DIR"
if [ -f nexus.crt ]; then echo "certificate exists: $DIR/nexus.crt"; exit 0; fi
MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout nexus.key -out nexus.crt \
  -subj "/CN=nexus.local" -addext "subjectAltName=DNS:localhost,DNS:nexus.local,IP:127.0.0.1"
echo "created $DIR/nexus.crt"
