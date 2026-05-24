# Run Telegram bot-worker via project .venv
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Creating .venv ..."
    python -m venv (Join-Path $Root ".venv")
}

& (Join-Path $Root ".venv\Scripts\pip.exe") install -r (Join-Path $Root "requirements.txt") -q
Set-Location $Root
& $Python -m bot @args
