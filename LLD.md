# Low-Level Design (LLD) — PQC Migration Gateway

## 1. Module map

```
api/
  main.py            FastAPI app, routers, CORS, lifespan(init_db)
  config.py          Settings (env PQCG_*, Render DATABASE_URL/PORT)
  database.py        Engine/session, init_db
  models.py          ConnectorToken, LanDevice, ConnectorHeartbeat, RemoteGateway, AuditEvent
  schemas.py         Pydantic request/response
  auth.py            Bearer token: generate / hash(SHA-256) / verify
  routes/
    ingest.py        POST /api/ingest
    core.py          health, tokens, devices, wrapper, dashboard
    reports.py       advisor, reports/{fmt}
    gateway.py       pqc/backend, pqc/wrap-demo, remote-gateway
  services/
    classifier.py    risk score -> tier + PQC candidate
    ai_advisor.py    rule engine (+ optional OpenAI)
    reports.py       CSV/JSON/PDF/summaries
pqc/
  backend.py         PQCBackend interface; DemoBackend; OQSBackend; get_backend()
  tunnel.py          handshake + HKDF + AES-256-GCM AeadChannel; demonstrate_wrap()
  gateway.py         EgressGateway / IngressClient (TCP proxy); loopback_demo()
ui/
  app.py             5 tabs + settings
  api_client.py      URL resolution, embedded fallback
  embedded.py        in-process backend (mirrors HTTP responses)
  theme.py           CSS
connector/connector.py   LAN scanner + uploader
```

## 2. Data model

**connector_tokens**(id, name, token_hash, token_prefix, org_name, active, created_at, last_seen)
**lan_devices**(id, token_id→, ip, mac, hostname, service, port, tls_version, cert_type,
weak_protocol, pqc_candidate, vendor, risk_score, priority_tier, wrap_status, last_seen, updated_at)
**connector_heartbeats**(id, token_id→, subnet, devices_found, connector_version, status, received_at)
**remote_gateways**(id, name, peer_id, endpoint, status, b2b_enabled, created_at)
**audit_events**(id, ts, source, action, detail)

## 3. API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/health` | — | liveness + active PQC backend |
| POST | `/api/ingest` | Bearer | connector heartbeat / inventory upload |
| POST | `/api/tokens` | — (UI) | create connector token (returns raw once) |
| GET | `/api/tokens` | — | list tokens (prefix only) |
| DELETE | `/api/tokens/{id}` | — | revoke token |
| GET | `/api/devices` | — | inventory (risk-sorted) |
| POST | `/api/wrapper` | — | apply/remove wrap on device ids |
| GET | `/api/dashboard` | — | aggregate stats |
| GET | `/api/advisor` | — | AI migration advice |
| GET | `/api/reports/{fmt}` | — | csv/json/pdf/migration/hld/change-plan/risk |
| GET | `/api/pqc/backend` | — | active + available PQC backends |
| POST | `/api/pqc/wrap-demo` | — | run tunnel (memory|socket), return transcript |
| POST | `/api/remote-gateway` | — | ensure B2B peer |

> Management endpoints are unauthenticated in this DIY build for demo simplicity; in
> production they sit behind the dashboard's session auth / admin privilege model.

## 4. Connector ingest (sequence)

```
connector            API                         DB
   │  POST /ingest (heartbeat) ─▶ verify token ─▶ insert heartbeat
   │ ◀─ {ok}                      update last_seen
   │  scan subnet (threads, COMMON_PORTS, TLS probe)
   │  POST /ingest (inventory) ─▶ verify token
   │                              for each device: upsert by (token_id, ip)
   │                              classify_device(): risk -> tier -> pqc_candidate
   │ ◀─ {upserted: N}             insert heartbeat(scan_complete) + audit
```

`classify_device`: baseline risk by port; +weak TLS (SSLv3/TLSv1.x) ⇒ ≥8; +weak cert ⇒ ≥7.5.
Tier: ≥8 tier-1, ≥5 tier-2, else tier-3. Candidate from a service→algorithm map.

## 5. PQC tunnel protocol (`pqc/tunnel.py`)

Server-authenticated handshake (simplified TLS 1.3 shape):

```
server                                   client
  │ ServerHello = len|sig_pk len|kem_pk len|sig(sig_sk, sig_pk||kem_pk) ─▶
  │                                        verify(sig_pk, sig_pk||kem_pk, sig)  ✓
  │                                        (ct, ss) = KEM.encap(kem_pk)
  │ ◀─ kem_ct ──────────────────────────  derive key = HKDF(ss,"pqcg-tunnel-v1")
  │ ss = KEM.decap(kem_sk, kem_ct)
  │ derive key = HKDF(ss,"pqcg-tunnel-v1")
```

Record layer: `AeadChannel` = AES-256-GCM with **directional 12-byte nonces**
(prefix byte per direction ‖ 64-bit counter ‖ 3 zero bytes), monotonic per direction —
no nonce reuse. `seal()/open()` with AAD `b"pqcg"`.

`demonstrate_wrap()` runs the whole exchange in memory and returns
`{verified, keys_match, ciphertext_hex, recovered, kem_alg, sig_alg, quantum_safe}`.

## 6. Socket gateway (`pqc/gateway.py`)

```
legacy client ─plaintext─▶ IngressClient ══PQC tunnel══▶ EgressGateway ─plaintext─▶ upstream
```

- Frames are length-prefixed (`>I` + bytes).
- `EgressGateway` runs a threaded accept loop: per connection it performs the server
  handshake, then decrypts each record and forwards to the upstream TCP service, relaying
  encrypted replies.
- `loopback_demo()` wires an echo upstream + gateway + client on `127.0.0.1` and asserts a
  byte-exact round trip — proof the mechanism works over real sockets.

## 7. Pluggable backend (`pqc/backend.py`)

`get_backend()` resolves: `PQCG_PQC_BACKEND` → liboqs if importable → demo.

| | DemoBackend | OQSBackend |
|--|-------------|------------|
| KEM | hash-based, functional, ML-KEM-768 sizing | ML-KEM-768 |
| Signature | Ed25519 (real) | ML-DSA-65 |
| Quantum-safe | No | Yes |

Symmetric layer is identical (real AES-256-GCM), so swapping backends changes only the
asymmetric primitives — clean separation for the LLD.

## 8. Dashboard fallback (`ui/api_client.py`)

URL resolution: Streamlit secret `API_BASE_URL` → env → `http://127.0.0.1:8000`;
`localhost`/`0.0.0.0` normalised to `127.0.0.1`. Mode = auto|remote|embedded. On a
connection-class error in auto mode, the client transparently switches to the **embedded**
backend (`ui/embedded.py`) which runs the same services in-process — eliminating the
`errno 99` dead-end.

## 9. Failure handling

| Failure | Behaviour |
|---------|-----------|
| Bad/Revoked token | API 401; connector exits with message |
| Remote API unreachable | UI auto-falls back to embedded backend |
| liboqs missing | Engine silently uses demo backend |
| reportlab missing | PDF falls back to a hand-built valid PDF |
| Upstream timeout (gateway) | empty reply, connection closed cleanly |
