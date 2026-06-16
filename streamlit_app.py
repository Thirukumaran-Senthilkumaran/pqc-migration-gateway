"""PQC Migration Gateway — Streamlit portal.

Deploy this file on Streamlit Community Cloud for a public About page and
project overview. The full gateway (LAN discovery, TCP proxy) runs locally or
on a VPS via `python -m backend.main` — see README.md.

Set GATEWAY_API_URL in Streamlit secrets to show live API status (optional).
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

st.set_page_config(
    page_title="PQC Migration Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("GATEWAY_API_URL", "").rstrip("/")

# ── Custom CSS (dark theme aligned with React dashboard) ─────────────────────
st.markdown(
    """
    <style>
    .main { background: linear-gradient(180deg, #0b0d12 0%, #11141b 100%); }
    .block-container { padding-top: 2rem; max-width: 960px; }
    h1, h2, h3 { color: #e2e8f0 !important; }
    p, li { color: #94a3b8; line-height: 1.7; }
    .hero {
        background: linear-gradient(135deg, rgba(124,92,255,0.15), rgba(16,185,129,0.08));
        border: 1px solid rgba(124,92,255,0.3);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    .badge {
        display: inline-block;
        background: rgba(124,92,255,0.2);
        border: 1px solid rgba(124,92,255,0.4);
        color: #a18bff;
        padding: 0.25rem 0.75rem;
        border-radius: 8px;
        font-size: 0.85rem;
        margin-right: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar navigation ───────────────────────────────────────────────────────
page = st.sidebar.radio(
    "Navigate",
    ["About", "Project", "Live status"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Author**")
st.sidebar.markdown("Thirukumaran Senthilkumaran")
st.sidebar.markdown("*Network Security & IAM*")
st.sidebar.markdown("---")
st.sidebar.caption("Deploy full gateway locally with start.bat")

# ── Pages ────────────────────────────────────────────────────────────────────
if page == "About":
    st.markdown(
        '<div class="hero"><h1>🛡️ PQC Migration Gateway</h1>'
        "<p>Quantum-safe coverage for every device on your LAN — without touching each node.</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown("## Thirukumaran Senthilkumaran")
    st.markdown(
        '<span class="badge">Network Security & IAM</span>'
        '<span class="badge">MSc Applied Cybersecurity</span>'
        '<span class="badge">University of South Wales</span>',
        unsafe_allow_html=True,
    )

    st.markdown("")
    st.markdown(
        """
I am a cybersecurity practitioner with a deep interest in **network security**,
**identity and access management (IAM)**, and the practical side of building
defences that organisations can actually operate — not just admire on paper.
My MSc in Applied Cybersecurity from the **University of South Wales** gave me
a rigorous foundation in threat modelling, secure architecture, and applied
research; what drives me day to day is turning that knowledge into systems that
**solve real business problems**.

I believe cybersecurity engineering should be **proactive**, not reactive.
Security is not a checkbox owned only by a specialist team — it must be woven
into infrastructure, processes, and product design from the start. As we move
deeper into the **AI era**, attack surfaces will shift faster than policies can
follow. Networks, endpoints, and cloud estates need to be built with resilience
in mind: ready to detect anomalies, adapt to new threats, and recover without
bringing the business to a halt.

That mindset — security as an enabler, infrastructure as a first-class
participant in defence — is what led me to build tools like this gateway
rather than only writing about the problem.
        """
    )

    st.markdown("---")
    st.markdown("### Motivation to build this")

    st.markdown(
        """
**Enterprises must be ready for the post-quantum era.** NIST has finalised
post-quantum cryptography standards (ML-KEM, ML-DSA), and nation-states,
regulators, and large vendors are already mapping migration roadmaps.
**Critical infrastructure** — energy, healthcare, finance, transport — has
begun inventorying cryptographic dependencies and planning staged rollouts
because the cost of waiting is measured in decades of *harvest-now,
decrypt-later* exposure.

**Small and medium businesses cannot afford to be left behind.** Most SMBs run
hundreds of legacy devices — printers, sensors, PLCs, cameras — that will
never receive a firmware update capable of native PQC. Replacing every node is
unrealistic; ignoring the problem is worse. A **gateway-based migration path**
lets an organisation gain quantum-safe coverage immediately, then upgrade
endpoints in priority order without a big-bang cutover.

This project is my answer to that gap: a plug-and-play PQC migration gateway
that discovers LAN nodes, classifies them by readiness and criticality, wraps
traffic in NIST-aligned cryptography, and plans a stage-by-stage rollout — so
that security teams and business owners can move in the same direction, at a
pace the infrastructure can sustain.
        """
    )

elif page == "Project":
    st.markdown("## Project overview")

    col1, col2, col3 = st.columns(3)
    col1.metric("PQC KEM", "ML-KEM-768")
    col2.metric("Signature", "ML-DSA-65")
    col3.metric("Bulk cipher", "AES-256-GCM")

    st.markdown(
        """
### What it does

1. **Discover** — auto-detects devices on your LAN (ARP, port scan, hostname).
2. **Classify** — scores each node for PQC-readiness, risk, and migration priority.
3. **Wrap** — forwards traffic through a PQC-secured tunnel (hybrid X25519 + ML-KEM).
4. **Migrate** — six-stage rollout plan from wrap-all to native PQC per tier.
5. **Adapt** — crypto policy engine upgrades cipher suite on anomaly detection.

### Run locally (full gateway)

```powershell
.\\start.bat
```

Open **http://localhost:8080** for the full React dashboard with live discovery,
gateway sessions, and traffic charts.

### Architecture

The gateway sits between LAN nodes and upstream peers. Classical TCP from legacy
devices enters the gateway; ciphertext leaves on the wire. No firmware changes
on endpoints required.

### Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, asyncio, SQLite |
| PQC | ML-KEM-768, ML-DSA-65, AES-256-GCM, HKDF-SHA-384 |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Portal | Streamlit (this page) |
        """
    )

else:  # Live status
    st.markdown("## Live API status")

    if not API_URL:
        st.info(
            "No remote gateway configured. Set **GATEWAY_API_URL** in Streamlit "
            "secrets (e.g. `https://your-vps:8080`) to poll a deployed instance.\n\n"
            "The full gateway requires network access and is intended to run "
            "locally or on a VPS — Streamlit Cloud hosts this portal only."
        )
        st.code("GATEWAY_API_URL = \"https://your-gateway.example.com\"", language="toml")
    else:
        try:
            with httpx.Client(timeout=5.0) as client:
                health = client.get(f"{API_URL}/api/health").json()
                stats = client.get(f"{API_URL}/api/stats/dashboard").json()
                engine = client.get(f"{API_URL}/api/pqc/info").json()

            st.success(f"Connected to `{API_URL}`")
            st.json(health)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LAN nodes", stats.get("total_nodes", "—"))
            c2.metric("PQC wrapped", stats.get("wrapped_nodes", "—"))
            c3.metric("Active sessions", stats.get("active_sessions", "—"))
            c4.metric("Migration", f"{stats.get('overall_progress_pct', 0):.0f}%")

            st.markdown("### PQC engine")
            st.json(engine)
        except Exception as e:
            st.error(f"Could not reach gateway at `{API_URL}`: {e}")
