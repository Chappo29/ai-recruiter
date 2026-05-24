# Run FastAPI via project .venv (avoids global Python missing slowapi, etc.)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Creating .venv ..."
    python -m venv (Join-Path $Root ".venv")
}

& (Join-Path $Root ".venv\Scripts\pip.exe") install -r (Join-Path $Root "requirements.txt") -q
Set-Location $Root
& $Python -m uvicorn app.main:app --reload @args
