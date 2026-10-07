# Offline installation from an unzipped bundle (FR 12, AC 09). Run from the folder the bundle was unzipped into:
#   powershell -ExecutionPolicy Bypass -File ops\install.ps1 [-VerifyOnly] [-Demo] [-Licence FILE]
# -VerifyOnly  check SHA256SUMS and stop      -Demo  seed synthetic data and issue a 30-day demo licence
# No network access is needed: images come from images.tar.gz and secrets are generated locally.
param([switch]$VerifyOnly, [switch]$Demo, [string]$Licence = "")
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Bundle $Root)) { Write-Host "Bundle verification FAILED: do not install this copy."; exit 1 }
Write-Host "bundle verified"
if ($VerifyOnly) { exit 0 }

$V = ([IO.File]::ReadAllText((Join-Path $Root "VERSION"))).Trim()
Write-Host "== loading images for $V"
Invoke-Native { docker load -i (Join-Path $Root "images.tar.gz") } "docker load"

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "== generating .env with new secrets"
    $text = [IO.File]::ReadAllText((Join-Path $Root ".env.example"))
    foreach ($token in "replace-owner-password", "replace-app-password", "replace-readonly-password",
                       "replace-with-64-random-hex-chars", "replace-with-licence-hmac-key") {
        $text = $text.Replace($token, (New-RandomHex 32))
    }
    [IO.File]::WriteAllText($envFile, $text, $Utf8NoBom)
}
Set-EnvValue "NEXUS_VERSION" $V

$certs = Join-Path $Root "ops\nginx\certs"
$licenceDir = Join-Path $Root "licence"
New-Item -ItemType Directory -Force $certs, $licenceDir | Out-Null
if (-not (Test-Path (Join-Path $certs "nexus.crt"))) {
    Write-Host "== generating a self-signed TLS certificate (replace with the site's own certificate)"
    Invoke-Native { docker run --rm --user 0 -v "${certs}:/certs" --entrypoint openssl "nexus-api:$V" `
        req -x509 -nodes -newkey rsa:2048 -days 825 -keyout /certs/nexus.key -out /certs/nexus.crt `
        -subj "/CN=nexus.local" -addext "subjectAltName=DNS:localhost,DNS:nexus.local,IP:127.0.0.1" } "certificate"
}

if ($Licence) {
    Copy-Item $Licence (Join-Path $licenceDir "licence.json") -Force
} elseif ($Demo -and -not (Test-Path (Join-Path $licenceDir "licence.json"))) {
    Write-Host "== issuing a 30-day demonstration licence"
    $expires = (Get-Date).AddDays(30).ToString("yyyy-MM-dd")
    $key = Get-EnvValue "LICENCE_KEY"
    Invoke-Native { docker run --rm --user 0 -e "LICENCE_KEY=$key" -v "${licenceDir}:/out" --entrypoint python "nexus-api:$V" `
        /app/ops/licence.py issue --site "Demonstration site" --expires $expires --out /out/licence.json } "licence"
}

Write-Host "== starting Nexus $V"
Invoke-Compose up -d --no-build
if (-not (Wait-Healthy 180)) { exit 1 }

if ($Demo) {
    Write-Host "== seeding synthetic demonstration data"
    Invoke-Compose exec -T api python -m app.db.seed --legacy 2000 --demo | Out-Null
    Invoke-Compose cp api:/app/ops/demo-credentials.txt (Join-Path $Root "ops\demo-credentials.txt")
    Write-Host "demo sign-in details: ops\demo-credentials.txt (keep private)"
}
Write-Host "version: $(Get-Api '/version')"
$port = Get-EnvValue "HTTPS_PORT"; if (-not $port) { $port = "8443" }
Write-Host "Nexus $V is running at https://localhost:$port/"
