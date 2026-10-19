# Release 1.0.2 rehearsal (network on; the offline mechanism was proven in the AC 09 rehearsal).
# Runs beside the development stack: separate compose project (own volumes) on ports 9443/9080.
# Native tools write progress to stderr; with "Stop", redirecting it would abort the runner (PS 5.1).
$ErrorActionPreference = "Continue"
$here = $PSScriptRoot
$repo = "D:\AC\Nexus - RFID-enabled library solution"
$py = Join-Path $repo "backend\.venv\Scripts\python.exe"
$env:COMPOSE_PROJECT_NAME = "nexus-rehearsal"; $env:HTTPS_PORT = "9443"; $env:HTTP_PORT = "9080"
Start-Transcript -Path (Join-Path $here "r102-transcript.txt") -Force | Out-Null
function Step($t) { Write-Host ""; Write-Host "===== $t  [$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))]" }
function Api($path) {
    & docker compose exec -T api python -c "import sys, urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1' + sys.argv[1]).read().decode())" $path
}
function Snapshot($label) {
    $out = & docker compose exec -T api python /app/ops/integrity.py snapshot --out /backups/reports --label $label
    $out | Write-Host
    return (($out | Where-Object { $_ -like "report: *" }) -replace '^report: ', '')
}
function Fresh($zip, $name) {
    $dir = Join-Path $here $name
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    Expand-Archive -LiteralPath $zip -DestinationPath $dir
    return (Get-ChildItem $dir -Directory -Filter "nexus-*" | Select-Object -First 1).FullName
}

try {
    Step "A1. Install 1.0.1 from its bundle"
    $site = Fresh (Join-Path $repo "ops\bundles\nexus-1.0.1.zip") "r102-upgrade"
    Set-Location $site
    & (Join-Path $site "ops\install.ps1") -Demo
    if ($LASTEXITCODE -ne 0) { throw "install 1.0.1 failed" }
    Write-Host "version: $(Api '/version')"
    $before = Snapshot "before-update"

    Step "A2. Update 1.0.1 -> 1.0.2"
    & (Join-Path $site "ops\update.ps1") (Join-Path $repo "ops\bundles\nexus-1.0.2.zip")
    if ($LASTEXITCODE -ne 0) { throw "update failed" }
    Write-Host "version: $(Api '/version')"
    docker compose ps --format "table {{.Service}}\t{{.Image}}\t{{.Status}}" | Write-Host

    Step "A3. Roll back to 1.0.1"
    & (Join-Path $site "ops\rollback.ps1")
    if ($LASTEXITCODE -ne 0) { throw "rollback failed" }
    Write-Host "version: $(Api '/version')"
    $after = Snapshot "after-rollback"
    & docker compose exec -T api python /app/ops/integrity.py compare $before $after | Write-Host
    Write-Host "compare exit code: $LASTEXITCODE"
    docker compose down -v *> $null

    Step "B1. Fresh 1.0.2 install with a licence issued beforehand and its key (DEF-020)"
    $site = Fresh (Join-Path $repo "ops\bundles\nexus-1.0.2.zip") "r102-fresh"
    Set-Location $site
    $keyFile = Join-Path $here "site.key"; $licFile = Join-Path $here "site-licence.json"
    $bytes = New-Object byte[] 32; (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    [IO.File]::WriteAllText($keyFile, (-join ($bytes | ForEach-Object { $_.ToString("x2") })))
    & $py (Join-Path $repo "ops\licence.py") issue --site "Rehearsal site" --expires (Get-Date).AddDays(60).ToString("yyyy-MM-dd") --key-file $keyFile --out $licFile
    & (Join-Path $site "ops\install.ps1") -Demo -Licence $licFile -LicenceKeyFile $keyFile
    if ($LASTEXITCODE -ne 0) { throw "install 1.0.2 failed" }
    Write-Host "version: $(Api '/version')"
    Write-Host "restart policies:"; docker inspect -f "{{.Name}}={{.HostConfig.RestartPolicy.Name}}" (docker compose ps -q) | Write-Host

    Step "B2. Security smoke checks against the 1.0.2 install (DEF-015 included)"
    & $py (Join-Path $repo "ops\tests\security_smoke.py") --base https://localhost:9443 --http http://localhost:9080 `
        --ca (Join-Path $site "ops\nginx\certs\nexus.crt") --credentials (Join-Path $site "ops\demo-credentials.txt") | Write-Host
    Write-Host "smoke exit code: $LASTEXITCODE"

    Step "B3. Health reports 503 while the database is down (DEF-016)"
    docker compose stop db *> $null
    Start-Sleep -Seconds 5
    Write-Host "health with db stopped: HTTP $(& curl.exe -sk -o NUL -w '%{http_code}' https://localhost:9443/api/v1/health)"
    docker compose start db *> $null
    for ($i = 0; $i -lt 40; $i++) { if ((& curl.exe -sk -o NUL -w "%{http_code}" https://localhost:9443/api/v1/health) -eq "200") { break }; Start-Sleep 3 }
    Write-Host "health after db start: HTTP $(& curl.exe -sk -o NUL -w '%{http_code}' https://localhost:9443/api/v1/health)"
    docker compose down -v *> $null
    Write-Host "RELEASE 1.0.2 REHEARSAL COMPLETED"
} catch {
    Write-Host "RELEASE 1.0.2 REHEARSAL STOPPED: $_"
} finally {
    Stop-Transcript | Out-Null
}
