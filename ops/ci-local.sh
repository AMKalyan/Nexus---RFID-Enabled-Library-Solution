#!/bin/sh
# Runs the same checks as .github/workflows/ci.yml on the development host.
# Requires the database container: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORTS="$ROOT/backend/reports"
mkdir -p "$REPORTS"

if [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then PY="$ROOT/backend/.venv/Scripts/python.exe"; else PY="$ROOT/backend/.venv/bin/python"; fi

echo "== backend: format, lint, types, static analysis, dependencies, tests"
cd "$ROOT/backend"
"$PY" -m ruff format --check .
"$PY" -m ruff check .
"$PY" -m mypy app
"$PY" -m bandit -q -r app -x app/db/migrations -f txt -o "$REPORTS/bandit.txt" || { cat "$REPORTS/bandit.txt"; exit 1; }
"$PY" -m pip_audit -r requirements.txt --progress-spinner off > "$REPORTS/pip-audit.txt" 2>&1 || { cat "$REPORTS/pip-audit.txt"; exit 1; }
"$PY" -m pytest -q --cov=app --cov-report=term --junitxml="$REPORTS/junit.xml" | tee "$REPORTS/pytest.txt"

echo "== device simulator: tests"
cd "$ROOT/device-sim"
"$PY" -m pytest -q -p no:cacheprovider test_sim.py

echo "== frontend: types, tests, dependencies, build"
cd "$ROOT/frontend"
npx tsc -b
npx vitest run
npm audit --audit-level=high > "$REPORTS/npm-audit.txt" 2>&1 || { cat "$REPORTS/npm-audit.txt"; exit 1; }
npm run build > /dev/null

echo "== all checks passed"
