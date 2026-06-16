# PQC Migration Gateway

> **A plug-and-play web gateway that brings Post-Quantum Cryptography (PQC) to every device on your local network — without touching the devices themselves.**

![status](https://img.shields.io/badge/status-prototype-blue) ![pqc](https://img.shields.io/badge/PQC-ML--KEM--768%20%2B%20ML--DSA--65-success) ![license](https://img.shields.io/badge/license-MIT-green)

---

## The Problem

Local-area networks are full of devices that **cannot** be upgraded to post-quantum cryptography:

- Industrial sensors, PLCs, HVAC controllers
- IP cameras, printers, smart-TVs
- Embedded medical / point-of-sale devices
- Legacy PCs running outdated TLS stacks

Updating each node individually is operationally impossible at scale, and many of them have CPUs too weak to run lattice-based crypto anyway.

## The Solution

A **gateway** that:

1. **Discovers** every node on the LAN automatically.
2. **Classifies** each node by PQC-readiness, criticality, and traffic profile.
3. **Wraps** outbound classical traffic in a PQC-secured tunnel (ML-KEM-768 key exchange + ML-DSA-65 authentication + AES-256-GCM bulk).
4. **Plans a stage-by-stage migration**: high-priority devices get native PQC first; the gateway covers the rest until they are upgraded — and quietly retires once everyone is migrated.
5. Is **plug-and-play**: drop the box on your network, open the dashboard, done.

---

## Architecture (high level)

```
              ┌────────────────────────────────────┐
              │          Web Dashboard             │
              │   React + Tailwind, real-time WS   │
              └────────────────┬───────────────────┘
                               │ REST / WebSocket
              ┌────────────────▼───────────────────┐
              │            FastAPI Core            │
              ├────────────────────────────────────┤
              │ Discovery │ Classifier │ Migration │
              │  Engine   │   Engine   │  Planner  │
              ├───────────┴────────────┴───────────┤
              │   PQC Engine  (ML-KEM + ML-DSA)    │
              │   Gateway / Proxy (asyncio)        │
              │   Monitor  (traffic stats)         │
              └────────────────┬───────────────────┘
                               │
        ┌──────────────────────┼─────────────────────┐
        │                      │                     │
   ┌────▼────┐            ┌────▼────┐           ┌────▼────┐
   │  Node A │   . . .    │  Node N │           │ Upstream│
   │ (legacy)│            │ (IoT)   │           │  / WAN  │
   └─────────┘            └─────────┘           └─────────┘
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the deep dive.

---

## Quick Start (plug-and-play)

### Windows

```powershell
.\start.bat
```

### Linux / macOS

```bash
chmod +x start.sh && ./start.sh
```

The launcher will:

1. Create a Python virtualenv.
2. Install backend dependencies.
3. Install frontend dependencies & build the dashboard.
4. Start the gateway on `http://localhost:8080`.

Open [http://localhost:8080](http://localhost:8080) in your browser.

> First-run discovery scan starts automatically. Default credentials: `admin / admin` — change them in **Settings**.

---

## Tech Stack

| Layer | Tech |
|------|------|
| Backend  | Python 3.11, FastAPI, asyncio, SQLAlchemy, SQLite |
| PQC      | ML-KEM-768 (FIPS 203), ML-DSA-65 (FIPS 204), AES-256-GCM, HKDF-SHA-384 |
| Networking | Raw sockets, asyncio TCP proxy, ARP/mDNS/SSDP discovery |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Recharts, Zustand |
| Realtime | WebSockets (FastAPI) |

---

## Migration Stages

The gateway is designed around a **staged rollout** model:

| Stage | Description | Action |
|-------|-------------|--------|
| **0 — Discovery** | All nodes inventoried, gateway in monitor mode | Auto |
| **1 — Wrap-All** | All outbound traffic goes through PQC tunnel | Auto |
| **2 — Native PQC, Tier-1** | Critical/high-value nodes upgraded to native PQC | Manual schedule |
| **3 — Native PQC, Tier-2** | Standard endpoints upgraded | Manual schedule |
| **4 — Native PQC, Tier-3** | IoT / low-priority nodes upgraded or retired | Manual schedule |
| **5 — Gateway Standby** | Gateway only protects last-mile legacy devices | Auto |

Priority is computed automatically from: device class, traffic volume, exposed services, OS fingerprint, declared business criticality.

---

## Folder Layout

```
.
├── backend/              # FastAPI service (PQC + gateway + APIs)
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── pqc/              # PQC engine (KEM, signatures, tunnel)
│   ├── network/          # discovery, classifier, gateway, monitor
│   ├── migration/        # stage planner
│   └── api/              # REST + WebSocket routers
├── frontend/             # React + Vite + Tailwind dashboard
├── data/                 # SQLite DB & runtime artifacts (auto-created)
├── requirements.txt
├── start.bat / start.sh
├── ARCHITECTURE.md
└── README.md
```

---

## Author

**Thirukumaran Senthilkumaran** — Network Security & IAM enthusiast.  
MSc Applied Cybersecurity, University of South Wales.

See the **About** page in the dashboard (`/about`) or the [Streamlit portal](DEPLOYMENT.md) for motivation and background.

---

## Deploy online

| Target | What runs | Guide |
|--------|-----------|-------|
| **Streamlit Cloud** | About page, project overview, optional API status | [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Local / VPS** | Full gateway (discovery, PQC tunnel, React UI) | `start.bat` or `start.sh` |

---

## License

MIT — see `LICENSE`.
