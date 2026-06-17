# PQC Migration Gateway

> Wrap your LAN in post-quantum encryption — protect legacy devices that will never get a PQC upgrade.

Enterprise networks are full of systems that cannot be upgraded to post-quantum
cryptography (OT, IoT, appliances, EOL firmware). Instead of upgrading every device, this
platform deploys a **gateway** that wraps ingress/egress traffic in PQC, giving the whole
LAN quantum-safe coverage **now** — then migrating endpoints to native PQC tier-by-tier.
It also secures **B2B data transfer** over a PQC tunnel.

## Architecture

```
 LAN (inside customer network)                         Cloud
 ┌───────────────────────────┐      HTTPS POST        ┌──────────────────────┐
 │  connector.py             │  /api/ingest (Bearer)  │  FastAPI API (Render)│
 │  scans device metadata    │ ─────────────────────▶ │  SQLite / Postgres   │
 └───────────────────────────┘                        └─────────┬────────────┘
                                                                 │ HTTP
                                                       ┌─────────▼────────────┐
                                                       │ Streamlit Dashboard  │
                                                       │ (Streamlit Cloud)    │
                                                       └──────────────────────┘
```

Three pieces, one repo:

| Piece | Path | Role |
|-------|------|------|
| **API** | `api/` | FastAPI. Connector ingest, inventory, policy, reports, PQC demos. |
| **Dashboard** | `ui/` | Streamlit. 5 tabs + settings. Talks to the API (with an in-process fallback). |
| **Connector** | `connector/connector.py` | Downloadable LAN scanner; uploads metadata over HTTPS. |
| **PQC engine** | `pqc/` | Pluggable backend (demo or liboqs) + AES-256-GCM tunnel + socket gateway. |

## Quick start (local, Windows)

```
start.cmd
```

Then open:
- Dashboard: http://127.0.0.1:8501
- API health: http://127.0.0.1:8000/api/health

### Manual start

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements-local.txt

# Terminal 1 — API
.\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Dashboard
$env:API_BASE_URL="http://127.0.0.1:8000"
.\.venv\Scripts\streamlit run ui/app.py --server.port 8501
```

## Connector workflow

1. Dashboard → **PQC Wrapper** → create a connector token.
2. Download `connector.py`.
3. Inside your LAN: `pip install requests`
4. `python connector.py --token pqcg_XXXX --url <api-url>`
5. Inventory appears in **Dashboard** and **PQC Inventory**.

## Tabs

| Tab | Purpose |
|-----|---------|
| About | Author, motivation, contact |
| Dashboard | LAN/PQC state, coverage, B2B remote gateway |
| PQC Wrapper | Token + connector download, wrap/unwrap, **live PQC tunnel test** |
| PQC Inventory | Priority tiers (IP/Service/Port/TLS/Cert/Weak/PQC candidate) + **AI Advisor** |
| Reports | CSV, JSON, PDF, migration summary, HLD, change plan, risk |

## PQC engine

- **Demo backend** (default): functional KEM (matching shared secret, ML-KEM-768 sizing) +
  real Ed25519 signatures + real AES-256-GCM. Runs anywhere. *Not* quantum-safe.
- **liboqs backend**: real **ML-KEM-768** + **ML-DSA-65** when `oqs` is installed
  (`PQCG_PQC_BACKEND=liboqs`). Same interface.

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md). API → Render (`render.yaml`), UI → Streamlit Cloud
(`streamlit_app.py`, secret `API_BASE_URL`).

## Design docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — High-Level Design (HLD)
- [`LLD.md`](LLD.md) — Low-Level Design (protocol, data model, sequences)

## Author

**Thirukumaran Senthilkumaran** — MSc Applied Cybersecurity, University of South Wales
[LinkedIn](https://www.linkedin.com/in/thirukumaran-s-45588b43) ·
Thirukumaranarun98@gmail.com · +91 8098276733

MIT License.
