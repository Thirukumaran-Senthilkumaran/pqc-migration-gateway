# Architecture

## 1. Goals & Non-goals

**Goals**

- Provide quantum-safe confidentiality + integrity for traffic leaving the LAN, **without modifying endpoints**.
- Be deployable as a single appliance (or VM / container) that an operator can drop-in and manage from a browser.
- Provide an **operational migration path** — i.e., it is not just a tunnel, it is a *programme manager* for moving the LAN to native PQC stage by stage.

**Non-goals (for v1)**

- Replacing the LAN switch / router. The gateway is an *L7 forwarder*, not an L2 bridge.
- Performing PQC inside resource-constrained endpoints. That is exactly what we offload.
- Acting as a CA / PKI for the public internet. We use a self-managed PQC PKI for tunnel peers only.

---

## 2. Logical components

```
            ┌──────────────────────────────────────────────────────┐
            │                Web Dashboard (React)                 │
            └─────────────────────────┬────────────────────────────┘
                                      │   REST / WS
            ┌─────────────────────────▼────────────────────────────┐
            │                   FastAPI gateway                    │
            │                                                      │
            │  ┌───────────────┐   ┌────────────────┐              │
            │  │ Discovery svc │──▶│  Node registry │◀─────┐       │
            │  └───────────────┘   └────────────────┘      │       │
            │  ┌───────────────┐                ▲          │       │
            │  │  Classifier   │────────────────┘          │       │
            │  └───────────────┘                           │       │
            │  ┌───────────────┐   ┌────────────────┐      │       │
            │  │ PQC Engine    │   │ Migration plan │──────┘       │
            │  └─────▲─────────┘   └────────────────┘              │
            │        │                                             │
            │  ┌─────┴─────────┐   ┌────────────────┐              │
            │  │ Gateway/proxy │──▶│ Traffic monitor│              │
            │  └───────────────┘   └────────────────┘              │
            └──────────────────────────────────────────────────────┘
```

### 2.1 Discovery service
- Periodic ARP sweep (build IP↔MAC table).
- mDNS / SSDP listener (catches IoT advertisements).
- Light TCP fingerprint on common ports (22, 80, 443, 502, 1883, 8883, …) — used purely to *identify* the node, never to attack.
- Persists to `nodes` table; emits `node.seen` events on the bus.

### 2.2 Classifier
- Scores every node on three axes:
  - **PQC-readiness** (0–10): based on detected TLS stack, OS, declared capabilities.
  - **Criticality** (0–10): operator-tagged business importance (overrideable).
  - **Risk** (0–10): exposure × sensitivity (e.g., a camera that streams PHI).
- Produces a **priority bucket** (`tier-1` / `tier-2` / `tier-3`).

### 2.3 PQC Engine
- Abstraction with pluggable backends (`pqcrypto`, `oqs` if available, `pure-py` fallback).
- Operations exposed:
  - `kem_keypair() / kem_encaps(pk) / kem_decaps(sk, ct)` → ML-KEM-768
  - `sig_keypair() / sig_sign(sk, m) / sig_verify(pk, m, sig)` → ML-DSA-65
  - `tunnel_handshake(...)` → derives 256-bit AES key via HKDF-SHA-384.
- **Hybrid mode** (default): the wire key = KDF(X25519_shared ‖ ML-KEM_shared). Protects against both classical *and* PQC implementation flaws.

### 2.4 Gateway / proxy
- asyncio TCP forwarder. For each LAN node configured in *wrap mode*:
  1. Listens on a virtual port assigned for that node's egress.
  2. Establishes (or reuses) a PQC tunnel session to the upstream peer (another gateway, or a PQC-aware server).
  3. Bidirectionally pumps bytes inside AES-256-GCM frames keyed by the handshake.
- Per-session AEAD nonces are 96-bit (32-bit salt ‖ 64-bit counter). Re-key after `2^32` frames or 1 h.

### 2.5 Migration planner
- Reads node registry + classifier output.
- Produces a Gantt-style migration plan (stages, batch windows, blast-radius limits).
- Tracks per-stage progress, exports a CSV report for compliance.

### 2.6 Traffic monitor
- Counts bytes/packets/sessions per node, per direction, per cipher suite.
- Pushes 1-second buckets onto a ring buffer; UI subscribes via WebSocket.

---

## 3. Data model (simplified)

```text
Node(id, mac, ip, hostname, os_guess, vendor, first_seen, last_seen,
     pqc_ready, criticality, risk, priority_tier, status)

GatewaySession(id, node_id, listen_port, upstream_host, upstream_port,
               cipher_suite, kem_alg, sig_alg, started_at, bytes_in,
               bytes_out, status)

MigrationStage(id, name, ordinal, target_tier, started_at, completed_at,
               progress_pct)

MigrationTask(id, stage_id, node_id, action, status, notes)

Event(id, ts, level, source, message, data_json)
```

---

## 4. Wire protocol (PQC tunnel)

```
client (gateway A)                         server (gateway B / PQC peer)
  |  ── HELLO  | nonce_a | sig_pk_A   ──▶                          |
  |                                                                |
  |  ◀──  HELLO_ACK | nonce_b | kem_pk_B | sig(B, transcript)  ──  |
  |                                                                |
  |  ── KEM_CT | encaps(kem_pk_B) | sig(A, transcript)         ──▶ |
  |                                                                |
  |        derive K = HKDF-SHA384(ss_kem ‖ ss_x25519, transcript)   |
  |                                                                |
  |  ──  AEAD frames (AES-256-GCM, K, ctr) ◀────▶                   |
```

- Every frame is `[ 4-byte length | 12-byte nonce | ciphertext+tag ]`.
- Re-keying = repeat from `KEM_CT` step inside the existing tunnel.

---

## 5. Threat model

| Threat | Mitigation |
|--------|------------|
| Quantum adversary records-now-decrypts-later | ML-KEM-768 key agreement |
| Forged peer | ML-DSA-65 mutual auth + pinned PKI |
| Replay | per-frame counter nonce + 1 h re-key |
| Downgrade to classical | hybrid X25519+ML-KEM, no negotiation of "off" |
| Compromised LAN node | gateway has its own egress identity; node never sees the long-term PQC key |

---

## 6. Plug-and-play deliverables

1. **Single launcher** (`start.bat` / `start.sh`) that boots backend + serves built UI on port 8080.
2. **Auto-detected interface** — the discovery service finds the active LAN interface and asks the operator to confirm in the wizard.
3. **First-run wizard** — pick interface, enter upstream peer, generate gateway PQC keypair, save.
4. **Self-test page** — runs a `kem_encaps/decaps` round-trip and a tunnel echo to confirm PQC is functional.

---

## 7. Future hardening

- Hardware appliance build (Yocto / Alpine).
- Active/standby failover with shared session table.
- HSM-backed long-term ML-DSA key.
- Optional inline NIDS hooks.
