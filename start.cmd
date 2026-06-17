@echo off
setlocal
cd /d %~dp0

echo ============================================================
echo   PQC Migration Gateway  -  starting API + Dashboard
echo ============================================================

if not exist .venv (
    echo Creating virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
)

echo Installing dependencies (first run may take a minute)...
.venv\Scripts\pip.exe install -q -r requirements-local.txt

echo.
echo [1/2] Starting API on http://127.0.0.1:8000
start "PQC API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

timeout /t 4 /nobreak >nul

echo [2/2] Starting Dashboard on http://127.0.0.1:8501
start "PQC Dashboard" cmd /k "set API_BASE_URL=http://127.0.0.1:8000 && .venv\Scripts\streamlit.exe run ui\app.py --server.port 8501"

echo.
echo Open in your browser:
echo   Dashboard : http://127.0.0.1:8501
echo   API health: http://127.0.0.1:8000/api/health
echo.
pause
endlocal
