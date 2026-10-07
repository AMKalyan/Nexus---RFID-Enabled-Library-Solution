# Windows wrapper: runs ops/ci-local.sh with Git Bash.
$ErrorActionPreference = "Stop"
& bash "$PSScriptRoot/ci-local.sh"
exit $LASTEXITCODE
