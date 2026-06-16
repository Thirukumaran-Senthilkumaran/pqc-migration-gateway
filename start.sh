#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  PQC Migration Gateway - Linux/macOS plug-and-play launcher
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  PQC Migration Gateway — bootstrapping..."
echo "============================================================"

# ---------- Python venv ----------------------------------------------------
if [[ ! -d .venv ]]; then
    echo "[1/5] Creating Python virtualenv (.venv)..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/5] Installing backend dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements-backend.txt

# ---------- Frontend -------------------------------------------------------
if command -v npm >/dev/null 2>&1; then
    if [[ ! -d frontend/node_modules ]]; then
        echo "[3/5] Installing frontend dependencies (first run only)..."
        (cd frontend && npm install --silent)
    fi
    if [[ ! -f frontend/dist/index.html ]]; then
        echo "[4/5] Building frontend dashboard..."
        (cd frontend && npm run build)
    fi
else
    echo "[!] npm not found - skipping UI build (API will still work)."
    echo "    Install Node.js 18+ to enable the dashboard."
fi

echo
echo "[5/5] Starting PQC Migration Gateway on http://localhost:8080"
echo "     (Ctrl+C to stop)"
echo

exec python -m backend.main
