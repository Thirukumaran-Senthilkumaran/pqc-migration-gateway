# Deployment Guide

Two cloud services: the **API** on Render and the **Dashboard** on Streamlit Cloud.
The connector runs inside the customer LAN and only needs outbound HTTPS.

```
connector (LAN) ──HTTPS──▶ API (Render) ◀──HTTP── Dashboard (Streamlit Cloud) ◀── you
```

## 1. Deploy the API on Render

1. Push this repo to GitHub.
2. Render → **New** → **Blueprint** → select the repo. Render reads `render.yaml`:
   - build: `pip install -r requirements-api.txt`
   - start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - `PQCG_SECRET_KEY` is generated automatically.
3. Deploy. Copy the service URL, e.g. `https://pqc-gateway-api.onrender.com`.
4. Verify: open `https://<your-api>.onrender.com/api/health` → `{"status":"ok", ...}`.

**Persistence:** the free plan uses ephemeral SQLite (resets on redeploy). For durable
storage add a Render Postgres instance and set `DATABASE_URL` — the app picks it up and
converts `postgres://` → `postgresql://` automatically. (Add `psycopg2-binary` to
`requirements-api.txt` if you use Postgres.)

## 2. Deploy the Dashboard on Streamlit Cloud

1. share.streamlit.io → **New app** → this repo.
2. **Main file path:** `streamlit_app.py`
3. **Python version:** 3.12 (Advanced settings).
4. **Secrets:**
   ```toml
   API_BASE_URL = "https://pqc-gateway-api.onrender.com"
   ```
5. Deploy. The dashboard calls the Render API. If the API is ever unreachable the UI
   automatically uses its built-in in-process backend.

> Requirements: Streamlit Cloud installs `requirements.txt` (UI + backend libs, pinned for
> Python 3.12). Do **not** point it at `requirements-api.txt`.

## 3. Run the connector (inside the LAN)

```
pip install requests
python connector.py --token pqcg_XXXX --url https://pqc-gateway-api.onrender.com
# optional: --subnet 192.168.1.0/24
```

## 4. Local development

```
start.cmd        # API on :8000, Dashboard on :8501 (Windows)
```
or the manual commands in `README.md`.

## 5. Real PQC (optional)

Install liboqs Python bindings on the API host and set `PQCG_PQC_BACKEND=liboqs`:
```
pip install oqs        # requires liboqs system library
```
The dashboard health/Dashboard tab will then report **quantum-safe (liboqs)**.

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `errno 99 / cannot assign requested address` | UI pointed at `0.0.0.0` / LAN IP | Use `127.0.0.1` locally or the Render URL; sidebar → Connection settings |
| UI shows "API offline" | Render API down or wrong `API_BASE_URL` | Check `/api/health`; fix the secret; or switch sidebar to **Built-in only** |
| Connector 401 | Wrong/revoked token | Generate a new token in PQC Wrapper |
| 0 devices found | Firewall / wrong subnet | Pass `--subnet <your-lan>/24` |
| Streamlit build fails | Wrong Python / requirements | Pin Python 3.12; use `requirements.txt` |
