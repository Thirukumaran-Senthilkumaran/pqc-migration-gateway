# Deploying PQC Migration Gateway

## Streamlit Community Cloud (About portal + live status)

Streamlit Cloud hosts the **portal** (`streamlit_app.py`) — your About page, project overview, and optional API health checks. It does **not** run LAN discovery or the TCP gateway (those need local network access).

### Steps

1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** → select your repo.
4. Set **Main file path** to `streamlit_app.py`.
5. Set **Requirements file** to `requirements-streamlit.txt` (Advanced settings).
6. Deploy.

Your app will be live at `https://<app-name>.streamlit.app`.

### Optional: link to a remote gateway

If you deploy the FastAPI backend on a VPS (Render, Railway, Azure VM, etc.), add a Streamlit secret:

```toml
GATEWAY_API_URL = "https://your-gateway.example.com"
```

The **Live status** page will poll `/api/health`, `/api/stats/dashboard`, and `/api/pqc/info`.

---

## Full gateway (local or VPS)

The complete stack (discovery, PQC tunnel, React UI) runs via:

```powershell
.\start.bat
```

Open http://localhost:8080

For production VPS deployment, run `python -m backend.main` behind a reverse proxy (nginx/Caddy) with TLS. Build the frontend first (`cd frontend && npm run build`).

---

## GitHub

```powershell
git init
git add .
git commit -m "Initial commit: PQC Migration Gateway"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/pqc-migration-gateway.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub handle.
