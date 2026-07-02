@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    python -m venv venv
)

"venv\Scripts\python.exe" -m pip install -r requirements.txt

powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($h.status -eq 'healthy') { Write-Host 'ShopMate AI is already running at http://127.0.0.1:8000'; exit 100 } } catch { exit 0 }"
if %ERRORLEVEL%==100 exit /b 0

"venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
