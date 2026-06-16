@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM PQC Migration Gateway - Windows plug-and-play launcher
REM ---------------------------------------------------------------------------

cd /d %~dp0

echo ============================================================
echo   PQC Migration Gateway -- bootstrapping...
echo ============================================================
echo.

REM ---- Python venv ----------------------------------------------------------
if not exist .venv (
    echo [1/5] Creating Python virtualenv ^(.venv^)...
    where py >nul 2>&1
    if !errorlevel! == 0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if !errorlevel! NEQ 0 (
        echo  ! Could not create virtualenv. Is Python 3.11+ installed?
        exit /b 1
    )
) else (
    echo [1/5] Python virtualenv already exists.
)

call .venv\Scripts\activate.bat

echo [2/5] Installing backend dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements-backend.txt
if !errorlevel! NEQ 0 (
    echo  ! Backend dependency install failed.
    exit /b 1
)

REM ---- Frontend -------------------------------------------------------------
echo [3/5] Checking frontend build...
where npm >nul 2>&1
if !errorlevel! NEQ 0 (
    echo  ! npm not found. Skipping UI build -- API will still work.
    echo    Install Node.js 18+ to enable the dashboard.
    goto :run
)

if not exist frontend\node_modules (
    echo [4/5] Installing frontend dependencies ^(first run only^)...
    pushd frontend
    call npm install --silent
    popd
)

if not exist frontend\dist\index.html (
    echo [4/5] Building frontend dashboard...
    pushd frontend
    call npm run build
    popd
)

:run
echo.
echo [5/5] Starting PQC Migration Gateway on http://localhost:8080
echo      ^(Ctrl+C to stop^)
echo.

python -m backend.main

endlocal
