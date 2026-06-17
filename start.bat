@echo off
setlocal
cd /d %~dp0

echo ============================================================
echo   PQC Cloud Gateway - starting API + UI
echo ============================================================

if not exist .venv (
    echo Creating virtualenv...
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat

pip install -q -r requirements.txt

echo.
echo [1/2] Starting API on http://localhost:8000
start "PQC API" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Starting UI on http://localhost:8501
set API_BASE_URL=http://localhost:8000
streamlit run ui/app.py --server.port 8501

endlocal
