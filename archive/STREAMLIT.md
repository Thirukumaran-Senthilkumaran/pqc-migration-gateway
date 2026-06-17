# Streamlit Cloud deployment — Thirukumaran-Senthilkumaran

## Repository

https://github.com/Thirukumaran-Senthilkumaran/pqc-migration-gateway

## Streamlit app settings

| Setting | Value |
|---------|-------|
| Main file path | `streamlit_app.py` |
| Requirements file | `requirements.txt` *(default — UI only, 3 packages)* |
| Python version | **3.12** (set in app Advanced settings if needed) |

> **Do not** point Streamlit at `requirements-local.txt` or `requirements-api.txt` —
> those include FastAPI/pydantic and will fail on Streamlit Cloud.

## Secrets (Streamlit Cloud → App → Settings → Secrets)

```toml
API_BASE_URL = "https://YOUR-API-URL.onrender.com"
```

The UI calls this API for all data. Without it, tabs show "API unreachable".

## API (Render — free tier)

1. Go to https://render.com → New → Blueprint
2. Connect repo `Thirukumaran-Senthilkumaran/pqc-migration-gateway`
3. Render reads `render.yaml` and deploys the API
4. Copy the API URL (e.g. `https://pqc-gateway-api.onrender.com`)
5. Paste into Streamlit secrets as `API_BASE_URL`

## Push updates

```powershell
git add .
git commit -m "Your message"
git push origin main
```

Streamlit auto-redeploys on push to `main`.

## Profile photo

Add `static/profile.jpg` to show your LinkedIn photo on the About tab.
