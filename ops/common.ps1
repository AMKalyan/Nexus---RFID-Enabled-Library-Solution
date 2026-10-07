# Shared helpers for install.ps1, update.ps1 and rollback.ps1 (Windows PowerShell 5.1 or later). Dot-sourced.
$ErrorActionPreference = "Stop"
$Ops = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Invoke-Native([scriptblock]$Command, [string]$What) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

function Invoke-Compose {
    & docker compose --project-directory $Root -f (Join-Path $Root "docker-compose.yml") @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($args -join ' ') failed (exit $LASTEXITCODE)" }
}

function Test-Bundle([string]$Dir) {
    $sums = Join-Path $Dir "SHA256SUMS"
    if (-not (Test-Path $sums)) { Write-Host "no SHA256SUMS in $Dir"; return $false }
    $ok = $true
    foreach ($line in [IO.File]::ReadAllLines($sums)) {
        if (-not $line.Trim()) { continue }
        $expected, $name = $line -split '\s+\*?', 2
        $file = Join-Path $Dir $name
        if (-not (Test-Path -LiteralPath $file)) { Write-Host "missing: $name"; $ok = $false; continue }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLower()
        if ($actual -ne $expected.ToLower()) { Write-Host "checksum mismatch: $name"; $ok = $false }
    }
    return $ok
}

function New-RandomHex([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($buffer); $rng.Dispose()
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Get-EnvValue([string]$Key) {
    $line = [IO.File]::ReadAllLines((Join-Path $Root ".env")) | Where-Object { $_ -like "$Key=*" } | Select-Object -Last 1
    if ($line) { return $line.Substring($Key.Length + 1) } else { return "" }
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $path = Join-Path $Root ".env"
    $lines = [Collections.Generic.List[string]]([IO.File]::ReadAllLines($path))
    $index = $lines.FindIndex([Predicate[string]] { param($l) $l -like "$Key=*" })
    if ($index -ge 0) { $lines[$index] = "$Key=$Value" } else { $lines.Add("$Key=$Value") }
    [IO.File]::WriteAllLines($path, $lines, $Utf8NoBom)
}

function Get-ApiStatus {
    $id = (& docker compose --project-directory $Root -f (Join-Path $Root "docker-compose.yml") ps -q api)
    if (-not $id) { return "missing" }
    return (& docker inspect -f "{{.State.Health.Status}}" $id)
}

function Wait-Healthy([int]$Seconds) {
    for ($i = 0; $i -lt $Seconds; $i += 3) {
        if ((Get-ApiStatus) -eq "healthy") { return $true }
        Start-Sleep -Seconds 3
    }
    Write-Host "API not healthy after $Seconds s (status: $(Get-ApiStatus))"
    return $false
}

function Get-Api([string]$Path) {
    $code = "import sys, urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1' + sys.argv[1]).read().decode())"
    return (& docker compose --project-directory $Root -f (Join-Path $Root "docker-compose.yml") exec -T api python -c $code $Path)
}
