#!/bin/sh
# Creates the application roles on first database start.
# nexus_owner (POSTGRES_USER) owns the schemas and runs migrations; the API uses nexus_app.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="$NEXUS_APP_PASSWORD" -v ro_pw="$NEXUS_READONLY_PASSWORD" <<'SQL'
CREATE ROLE nexus_app LOGIN PASSWORD :'app_pw';
CREATE ROLE nexus_readonly LOGIN PASSWORD :'ro_pw';
CREATE ROLE legacy_owner NOLOGIN;
SQL
