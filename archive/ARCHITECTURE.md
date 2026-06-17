# PQC Cloud Gateway — Architecture

## Vision

A **cloud-hosted** post-quantum migration platform. Legacy LAN devices cannot run PQC natively.
A lightweight **LAN Connector** runs inside the customer network, scans metadata, and pushes
results to the cloud over HTTPS. The cloud dashboard inventories devices, applies wrap policies,
plans staged migration, and exports consulting-grade reports.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLOUD (this project)                          │
│  ┌─────────────────┐         ┌──────────────────────────────────┐  │
│  │  Streamlit UI   │  HTTP   │  FastAPI API                      │  │
│  │  5 tabs +       │────────▶│  /api/ingest  (connector)         │  │
│  │  Settings       │         │  /api/tokens  /api/devices        │  │
│  └─────────────────┘         │  /api/wrapper /api/reports        │  │
│                              │  SQLite database                   │  │
│                              └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    ▲
                    Authorization: Bearer <connector_token>
                    HTTPS POST /api/ingest
                                    │
┌───────────────────────────────────┴──────────────────────────────────┐
│  CUSTOMER LAN                                                         │
│  connector.py  →  ARP / port scan / TLS probe  →  upload inventory   │
└──────────────────────────────────────────────────────────────────────┘
```

## Connector workflow

1. User opens cloud dashboard
2. User creates a **connector token** (PQC Wrapper tab)
3. User downloads **connector.py** (pre-filled with cloud URL + token placeholder)
4. User runs connector inside LAN: `python connector.py --token <token>`
5. Connector scans network, POSTs inventory + heartbeat to `/api/ingest`
6. Dashboard shows LAN devices, PQC wrap status, migration inventory

## Remote gateway (B2B)

Optional **remote gateway endpoint** per organisation — a cloud-side logical tunnel peer ID
used when wrapping egress for B2B sensitive transfers. V1 stores configuration and status;
full wire protocol extends in v2.

## Tabs

| Tab | Purpose |
|-----|---------|
| About | Author, motivation, contact |
| Dashboard | LAN traffic summary, PQC adoption, remote gateway status |
| PQC Wrapper | Wrap/unwrap devices, token + connector download |
| PQC Inventory | Priority tiers, hybrid onboarding queue |
| Reports | PDF, CSV, JSON, migration/HLD/risk exports |

## AI element

**Migration Advisor** (Inventory tab): analyses device inventory and produces a plain-English
onboarding recommendation and priority narrative. Rule-based by default; optional OpenAI if
`OPENAI_API_KEY` is set.

## Deployment

| Component | Platform |
|-----------|----------|
| API | Render / Railway / Fly.io (`uvicorn backend.main:app`) |
| UI | Streamlit Community Cloud (`streamlit run ui/app.py`) |

Set `API_BASE_URL` in Streamlit secrets to point at the deployed API.
