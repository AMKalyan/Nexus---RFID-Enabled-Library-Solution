# Return to the release recorded in ops\state.json by the last update (FR 12, AC 09):
#   powershell -ExecutionPolicy Bypass -File ops\rollback.ps1
# 1. Downgrade the schema with the newer image (only it has the newer migration scripts).
# 2. Restore the previous compose file and switch NEXUS_VERSION back.
# 3. If the downgrade fails, restore the backup taken before the update instead.
. (Join-Path $PSScriptRoot "common.ps1")
$statePath = Join-Path $Root "ops\state.json"
if (-not (Test-Path $statePath)) { Write-Host "no ops\state.json: nothing to roll back"; exit 1 }
$state = [IO.File]::ReadAllText($statePath) | ConvertFrom-Json
Write-Host "== rolling back $($state.current_version) to $($state.previous_version) (schema $($state.previous_alembic_rev))"

Set-EnvValue "NEXUS_VERSION" $state.current_version
Invoke-Compose stop web api
$restore = $false
& docker compose --project-directory $Root -f (Join-Path $Root "docker-compose.yml") run --rm --no-deps api alembic downgrade $state.previous_alembic_rev
if ($LASTEXITCODE -eq 0) { Write-Host "schema downgraded to $($state.previous_alembic_rev)" }
else { Write-Host "schema downgrade failed: restoring backup $($state.backup)"; $restore = $true }

$previous = Join-Path $Root "ops\previous"
if (Test-Path (Join-Path $previous "docker-compose.yml")) {
    Copy-Item (Join-Path $previous "docker-compose.yml"), (Join-Path $previous "VERSION") $Root -Force
}
Set-EnvValue "NEXUS_VERSION" $state.previous_version
if ($restore) { Invoke-Compose run --rm --no-deps api python -m nexus_ops.backup restore $state.backup --yes }

Invoke-Compose up -d --no-build
if (-not (Wait-Healthy 120)) { exit 1 }
Write-Host "rolled back to $($state.previous_version): $(Get-Api '/version')"
Move-Item $statePath (Join-Path $Root ("ops\state-rolled-back-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + ".json"))
