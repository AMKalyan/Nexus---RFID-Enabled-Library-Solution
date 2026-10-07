# Take a verified backup inside the running stack: ops\backup.ps1 [-Reason manual]
param([string]$Reason = "manual")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose exec -T api python -m nexus_ops.backup create --reason $Reason
exit $LASTEXITCODE
