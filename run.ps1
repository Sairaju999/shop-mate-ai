$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    python -m venv venv
}

.\venv\Scripts\python.exe -m pip install -r requirements.txt

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
    if ($health.status -eq "healthy") {
        Write-Host "ShopMate AI is already running at http://127.0.0.1:8000"
        exit 0
    }
} catch {
    # Port is free or the existing process is not this app; uvicorn will report any real bind errors.
}

.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
