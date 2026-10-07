# Apply an offline update bundle to this installation (FR 12, AC 09). Run from the installed folder:
#   powershell -ExecutionPolicy Bypass -File ops\update.ps1 C:\media\nexus-1.0.1.zip   (or an unzipped folder)
# Verifies the bundle, takes a backup, records the current release in ops\state.json, loads the new images and
# starts them. If the new release is not healthy within 120 s it rolls back automatically.
param([Parameter(Mandatory = $true)][string]$Bundle)
. (Join-Path $PSScriptRoot "common.ps1")

$work = $null
if ($Bundle -like "*.zip") {
    $work = Join-Path ([IO.Path]::GetTempPath()) ("nexus-update-" + [guid]::NewGuid())
    Expand-Archive -LiteralPath $Bundle -DestinationPath $work
    $new = (Get-ChildItem $work -Directory -Filter "nexus-*" | Select-Object -First 1).FullName
} else {
    $new = (Resolve-Path $Bundle).Path
}
try {
    if (-not (Test-Bundle $new)) { Write-Host "Update bundle verification FAILED: nothing was changed."; exit 1 }
    $from = Get-EnvValue "NEXUS_VERSION"
    $to = ([IO.File]::ReadAllText((Join-Path $new "VERSION"))).Trim()
    if ($from -eq $to) { Write-Host "already at $to"; exit 0 }
    $fromRev = ((Get-Api "/version") | ConvertFrom-Json).alembic_rev
    Write-Host "== updating $from (schema $fromRev) to $to"

    Write-Host "== backup before update"
    $out = Invoke-Compose exec -T api python -m nexus_ops.backup create --reason "pre-update-$from-$to"
    $backup = (($out | Where-Object { $_ -like "backup: *" }) -replace '^backup: .*/', '')
    if (-not $backup) { throw "backup failed: nothing was changed" }

    $previous = Join-Path $Root "ops\previous"
    if (Test-Path $previous) { Remove-Item -Recurse -Force $previous }
    New-Item -ItemType Directory $previous | Out-Null
    Copy-Item (Join-Path $Root "docker-compose.yml"), (Join-Path $Root "VERSION"), (Join-Path $Root "RELEASE-NOTES.md") $previous
    $state = [ordered]@{ previous_version = $from; previous_alembic_rev = $fromRev; current_version = $to;
                         backup = $backup; updated_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" }
    [IO.File]::WriteAllText((Join-Path $Root "ops\state.json"), ($state | ConvertTo-Json), $Utf8NoBom)

    Write-Host "== loading images for $to"
    Invoke-Native { docker load -i (Join-Path $new "images.tar.gz") } "docker load"
    foreach ($f in "docker-compose.yml", "VERSION", "RELEASE-NOTES.md", ".env.example") { Copy-Item (Join-Path $new $f) $Root -Force }
    Copy-Item (Join-Path $new "ops\*") (Join-Path $Root "ops") -Include *.sh, *.ps1, *.py -Force
    Copy-Item (Join-Path $new "ops\nginx\default.conf.template") (Join-Path $Root "ops\nginx") -Force
    Set-EnvValue "NEXUS_VERSION" $to

    Write-Host "== starting $to"
    Invoke-Compose up -d --no-build
    if (Wait-Healthy 120) {
        Write-Host "updated to ${to}: $(Get-Api '/version')"
        Write-Host "backup taken before the update: $backup (rollback: ops\rollback.ps1)"
    } else {
        Write-Host "== $to is not healthy: rolling back to $from"
        & (Join-Path $Root "ops\rollback.ps1")
        exit 1
    }
} finally {
    if ($work) { Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue }
}
