# High-Level Design (HLD) — PQC Migration Gateway

## 1. Purpose & problem statement

Post-quantum cryptography (PQC) standards (NIST ML-KEM / ML-DSA) are finalised, but most
enterprise estates contain devices that **cannot** be upgraded: OT/SCADA, IoT, medical
devices, appliances, and EOL systems. A device-by-device migration is infeasible.

**Solution:** a gateway that **wraps LAN ingress/egress traffic in PQC**, delivering
quantum-safe coverage across the whole segment immediately, then migrating endpoints to
native PQC in prioritised waves (a hybrid rollout). The same tunnel secures **B2B data
transfer** between organisations.

## 2. Solution overview

```
 ┌──────────────────────── Customer LAN ────────────────────────┐
 │  legacy devices    connector.py (metadata scan)               │
 └───────────────────────────┬──────────────────────────────────┘
                              │ HTTPS POST /api/ingest  (Bearer token)
                  ┌───────────▼───────────┐
                  │  Cloud API (FastAPI)  │  inventory, policy, reports, PQC demos
                  │  SQLite | Postgres    │
                  └───────────┬───────────┘
                              │ HTTP (JSON)
                  ┌───────────▼───────────┐
                  │ Streamlit Dashboard   │  operations & reporting UI
                  └───────────────────────┘
```

## 3. Components

| Component | Tech | Responsibility |
|-----------|------|----------------|
| LAN Connector | Python stdlib + `requests` | Discover device/crypto metadata, upload over HTTPS |
| Cloud API | FastAPI + SQLAlchemy | AuthN (Bearer), ingest, classify, store, serve, report |
| Dashboard | Streamlit | Visualise inventory/coverage, manage wrap policy, run PQC demos, export |
| PQC engine | `pqc/` (liboqs or demo) | KEM, signatures, AES-GCM tunnel, socket gateway |

## 4. Cryptographic suite

| Function | Algorithm |
|----------|-----------|
| Key encapsulation (KEM) | ML-KEM-768 (liboqs) / functional demo |
| Authentication (signature) | ML-DSA-65 (liboqs) / Ed25519 (demo) |
| Record encryption (AEAD) | AES-256-GCM |
| Key derivation | HKDF-SHA256 |

Handshake is **server-authenticated**: the gateway signs `sig_pk || kem_pk`; the client
verifies before encapsulating, preventing MITM.

## 5. Security architecture

- **Connector auth:** per-connector Bearer token; only SHA-256 hash stored.
- **Least data:** metadata only (IP, port, service, TLS version, cert type) — no payloads.
- **In transit:** HTTPS to the API; PQC tunnel for wrapped traffic.
- **Token lifecycle:** create / list / revoke from the dashboard; audit events recorded.
- **Privilege model (UI):** Viewer / Operator / Administrator, optional MFA on policy change.

## 6. Migration methodology (hybrid, staged)

| Phase | Action |
|-------|--------|
| 0 | Deploy connector, baseline inventory |
| 1 | Wrap all egress + B2B paths via PQC gateway |
| 2 | Tier-1 (critical) native PQC upgrade |
| 3 | Tier-2 / Tier-3 rollout |
| 4 | Gateway standby for residual legacy |

Devices are tiered by a risk score (service exposure + weak protocol + weak certs).

## 7. Deployment topology

- **API** → Render web service (`render.yaml`), binds `0.0.0.0:$PORT`, SQLite (free) or
  Postgres (`DATABASE_URL`).
- **Dashboard** → Streamlit Community Cloud (`streamlit_app.py`), secret `API_BASE_URL`.
- **Connector** → runs inside the customer LAN; only needs outbound HTTPS.

## 8. Why the previous `errno 99` happened (and is now designed out)

`[Errno 99] Cannot assign requested address` occurs when a client tries to connect to an
address it cannot bind/route to — typically pointing the UI at `0.0.0.0` or a LAN/public IP
from within a cloud runtime. Fixes:
- API always binds `0.0.0.0` (server) — UI always *connects* to a routable URL
  (`127.0.0.1` locally, the Render URL in cloud); loopback aliases are normalised.
- Dashboard has an **in-process backend fallback** so it degrades gracefully instead of
  erroring when a remote API is unreachable.

## 9. Non-goals (current version)

- Not a full line-rate inline traffic interceptor; the gateway is a TCP-proxy pattern
  demonstrated end to end (see LLD), suitable for service-level wrapping and B2B paths.
- Demo PQC backend is for portability, not production security; use liboqs for real PQC.
