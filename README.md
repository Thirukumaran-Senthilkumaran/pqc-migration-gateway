# PQC Cloud Gateway

> Cloud-hosted post-quantum migration platform with LAN Connector architecture.

Protect entire LAN segments without upgrading every device. A lightweight **LAN Connector**
runs inside your network, uploads inventory to the cloud, and the dashboard manages
PQC wrap policies, staged migration, and consulting-grade reports.

## Architecture

```
LAN (connector.py)  ──HTTPS POST /api/ingest──▶  FastAPI Cloud API
                                                        ▲
Streamlit Dashboard  ──────────────────────────────── HTTP
```

## Quick start (local)

```powershell
.\start.bat
```

- **API:** http://localhost:8000
- **UI:** http://localhost:8501

## Tabs

| Tab | Purpose |
|-----|---------|
| About | Author, contact, motivation |
| Dashboard | PQC coverage, LAN stats, remote B2B gateway |
| PQC Wrapper | Token creation, connector download, wrap/unwrap |
| PQC Inventory | Priority tiers + AI Migration Advisor |
| Reports | PDF, CSV, JSON, HLD, change plan, risk |

## LAN Connector workflow

1. Open dashboard → **PQC Wrapper**
2. Create connector token
3. Download `connector.py`
4. Inside LAN: `pip install requests && python connector.py --token <token> --url http://localhost:8000`
5. Dashboard populates automatically

## Cloud deployment

| Component | Platform | Entry |
|-----------|----------|-------|
| API | Render / Railway | `uvicorn backend.main:app --port 8000` |
| UI | Streamlit Cloud | `streamlit_app.py`, requirements: `requirements-ui.txt` |

Set Streamlit secret: `API_BASE_URL = https://your-api.onrender.com`

## Author

**Thirukumaran Senthilkumaran**  
[LinkedIn](https://www.linkedin.com/in/thirukumaran-s-45588b43) · Thirukumaranarun98@gmail.com · +91 8098276733

MIT License
