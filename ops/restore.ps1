# Restore a backup taken by ops\backup.ps1: ops\restore.ps1 -File <backup-file-name>
param([Parameter(Mandatory = $true)][string]$File)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose stop web api
docker compose run --rm --no-deps api python -m nexus_ops.backup restore $File --yes
if ($LASTEXITCODE -ne 0) { docker compose start api web; exit $LASTEXITCODE }
docker compose start api web
Write-Host "Restore complete. Check: docker compose exec api python /app/ops/integrity.py snapshot"
