# AC 09 offline rehearsal runner. Place it in a folder that holds the unzipped 1.0.0 bundle (nexus-1.0.0\)
# and the update bundle (media\nexus-1.0.1.zip), switch networking OFF, then run:
#   powershell -ExecutionPolicy Bypass -File rehearse-ac09.ps1
# Everything is recorded in ac09-transcript.txt next to this script.
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$site = Join-Path $here "nexus-1.0.0"
$update = Join-Path $here "media\nexus-1.0.1.zip"
Start-Transcript -Path (Join-Path $here "ac09-transcript.txt") -Force | Out-Null

function Step($text) { Write-Host ""; Write-Host "===== $text  [$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))]" }
function Counts {
    $sql = "select 'bibs=' || (select count(*) from nexus.bib) || ' items=' || (select count(*) from nexus.item) || ' members=' || (select count(*) from nexus.member) || ' legacy_catalogue=' || (select count(*) from legacy_ilms.catalogue)"
    $user = Get-EnvValue "POSTGRES_USER"; $db = Get-EnvValue "POSTGRES_DB"
    & docker compose exec -T db psql -U $user -d $db -tAc $sql
}
function Snapshot($label) {
    $out = & docker compose exec -T api python /app/ops/integrity.py snapshot --out /backups/reports --label $label
    $out | Write-Host
    return (($out | Where-Object { $_ -like "report: *" }) -replace '^report: ', '')
}

try {
    Step "0. Network state (expect no connected adapters and no route to the internet)"
    Get-NetAdapter | Select-Object Name, Status, MediaConnectionState | Format-Table -AutoSize | Out-String | Write-Host
    Write-Host "internet reachable (pypi.org:443): $(Test-NetConnection pypi.org -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)"
    Write-Host "registry reachable (registry-1.docker.io:443): $(Test-NetConnection registry-1.docker.io -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)"
    Write-Host "images present before install:"; docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -match "^nexus|^postgres" }

    Step "1. Install 1.0.0 from the bundle (offline)"
    Set-Location $site
    & (Join-Path $site "ops\install.ps1") -Demo
    if ($LASTEXITCODE -ne 0) { throw "install failed" }
    . (Join-Path $site "ops\common.ps1")
    Write-Host "version: $(Get-Api '/version')"
    Write-Host "counts:  $(Counts)"
    $before = Snapshot "after-install-1.0.0"

    Step "2. Update to 1.0.1 from the update bundle (offline)"
    & (Join-Path $site "ops\update.ps1") $update
    if ($LASTEXITCODE -ne 0) { throw "update failed" }
    Write-Host "version: $(Get-Api '/version')"
    Write-Host "counts:  $(Counts)"
    Write-Host "state.json: $([IO.File]::ReadAllText((Join-Path $site 'ops\state.json')))"
    docker compose ps --format "table {{.Service}}\t{{.Image}}\t{{.Status}}" | Write-Host

    Step "3. Roll back to 1.0.0"
    & (Join-Path $site "ops\rollback.ps1")
    if ($LASTEXITCODE -ne 0) { throw "rollback failed" }
    Write-Host "version: $(Get-Api '/version')"
    Write-Host "counts:  $(Counts)"
    docker compose ps --format "table {{.Service}}\t{{.Image}}\t{{.Status}}" | Write-Host
    $after = Snapshot "after-rollback-1.0.0"

    Step "4. Legacy integrity: fingerprints after install vs after rollback"
    & docker compose exec -T api python /app/ops/integrity.py compare $before $after | Write-Host
    Write-Host "compare exit code: $LASTEXITCODE"

    Step "5. Network state at the end"
    Write-Host "internet reachable (pypi.org:443): $(Test-NetConnection pypi.org -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)"
    Write-Host "AC 09 REHEARSAL COMPLETED"
} catch {
    Write-Host "AC 09 REHEARSAL STOPPED: $_"
} finally {
    Stop-Transcript | Out-Null
}
