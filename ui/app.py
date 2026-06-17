"""
PQC Cloud Gateway — Streamlit UI
Sophos-inspired light theme · 5 tabs · Settings panel
Run: streamlit run ui/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

# ── Config ───────────────────────────────────────────────────────────────────
API = os.getenv("API_BASE_URL", os.getenv("PQCG_API_URL", "http://localhost:8000")).rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
PROFILE_IMG = ROOT / "static" / "profile.jpg"

st.set_page_config(
    page_title="PQC Cloud Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Light Sophos-style theme ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #f4f6f9; }
.block-container { padding-top: 1rem; max-width: 1400px; }
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
}
section[data-testid="stSidebar"] .stRadio label {
    font-weight: 500;
    color: #334155;
}
.sophos-header {
    background: linear-gradient(90deg, #0052cc 0%, #0065ff 100%);
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.metric-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.tier-1 { color: #dc2626; font-weight: 600; }
.tier-2 { color: #d97706; font-weight: 600; }
.tier-3 { color: #64748b; }
.contact-link { color: #0052cc; text-decoration: none; }
.contact-link:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)


def api_get(path: str):
    try:
        r = httpx.get(f"{API}{path}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API unreachable ({API}): {e}")
        return None


def api_post(path: str, body: dict):
    try:
        r = httpx.post(f"{API}{path}", json=body, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def header_bar():
    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(
            '<div class="sophos-header"><span style="font-size:1.1rem;font-weight:600;">'
            '🛡️ PQC Cloud Gateway</span>'
            '<span style="font-size:0.8rem;opacity:0.9;">Post-Quantum LAN Protection</span></div>',
            unsafe_allow_html=True,
        )
    with c2:
        with st.popover("⚙️ Settings", use_container_width=True):
            st.markdown("#### Notification settings")
            st.checkbox("Email alerts on new high-risk devices", value=True, key="n1")
            st.checkbox("Connector offline alerts", value=True, key="n2")
            st.checkbox("Weekly migration summary", value=False, key="n3")
            st.divider()
            st.markdown("#### Admin access")
            st.text_input("Admin username", value="admin", disabled=True)
            st.selectbox("Privilege level", ["Viewer", "Operator", "Administrator"], index=2)
            st.divider()
            st.markdown("#### Security & privacy")
            st.caption(
                "Connector tokens are hashed at rest. Inventory data is encrypted in transit (HTTPS). "
                "No packet payloads are stored — only network metadata. "
                "Revoke tokens anytime from PQC Wrapper tab."
            )


# ── TAB 1: About ─────────────────────────────────────────────────────────────
def page_about():
    col_img, col_text = st.columns([1, 3])
    with col_img:
        if PROFILE_IMG.exists():
            st.image(str(PROFILE_IMG), width=180)
        else:
            st.image("https://ui-avatars.com/api/?name=Thirukumaran+S&size=180&background=0052cc&color=fff&bold=true", width=180)
    with col_text:
        st.markdown("## Thirukumaran Senthilkumaran")
        st.markdown("**Network Security & IAM Enthusiast**")
        st.markdown("MSc Applied Cybersecurity — *University of South Wales*")

    st.markdown("""
I am a cybersecurity practitioner focused on **network security**, **identity and access
management (IAM)**, and building defences that organisations can actually operate.
My MSc gave me a foundation in threat modelling and secure architecture; what drives me
is turning that into systems that **solve real business problems**.

Cybersecurity must be **proactive** — woven into infrastructure and processes, not owned
only by a specialist team. As we enter the **AI era**, attack surfaces evolve faster than
policies. Networks and cloud estates must be resilient: ready to detect anomalies, adapt,
and recover without halting the business.

Security is an enabler. Infrastructure must be ready to face threats that emerge as
technology accelerates — that belief shaped this platform.
    """)

    st.markdown("### Motivation to build this")
    st.markdown("""
**Enterprises must be ready for the post-quantum era.** NIST has standardised ML-KEM and
ML-DSA. Critical infrastructure — energy, healthcare, finance — is already inventorying
cryptographic dependencies. **SMBs cannot be left behind.** Hundreds of legacy devices will
never receive native PQC firmware. A **gateway-based migration** delivers quantum-safe
coverage now, then upgrades endpoints tier-by-tier without a big-bang cutover.

This cloud platform lets you deploy a **LAN Connector** inside your network, discover
every device, wrap traffic in PQC, and plan a hybrid staged rollout — at a pace your
infrastructure can sustain.
    """)

    st.markdown("### Contact")
    st.markdown(
        "- 🔗 [LinkedIn](https://www.linkedin.com/in/thirukumaran-s-45588b43)  \n"
        "- ✉️ [Thirukumaranarun98@gmail.com](mailto:Thirukumaranarun98@gmail.com)  \n"
        "- 💬 WhatsApp: [+91 8098276733](https://wa.me/918098276733)"
    )


# ── TAB 2: Dashboard ─────────────────────────────────────────────────────────
def page_dashboard():
    stats = api_get("/api/dashboard")
    devices = api_get("/api/devices") or []

    if stats:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("LAN Devices", stats["total_devices"])
        m2.metric("PQC Wrapped", stats["wrapped_devices"])
        m3.metric("PQC Coverage", f"{stats['pqc_coverage_pct']}%")
        m4.metric("Tier-1 Critical", stats["tier1_devices"])
        m5.metric("Connectors Online", stats["connectors_online"])

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### LAN traffic & PQC state")
        if devices:
            df = pd.DataFrame(devices)
            wrap_counts = df["wrap_status"].value_counts()
            st.bar_chart(wrap_counts)
            tier_counts = df["priority_tier"].value_counts()
            st.markdown("**Devices by priority tier**")
            st.bar_chart(tier_counts)
        else:
            st.info("No inventory yet. Deploy the LAN Connector from the **PQC Wrapper** tab.")

    with c2:
        st.markdown("#### Remote gateway (B2B)")
        st.caption("Secure business data transfer between organisations via cloud PQC tunnel peer.")
        rg = api_post("/api/remote-gateway", {})
        if rg:
            st.success(f"Remote gateway **{rg['status']}**")
            st.code(f"Peer ID: {rg['peer_id']}", language=None)
            st.caption("Share this peer ID with B2B partners to establish a PQC-wrapped data path.")
        if stats:
            st.caption(f"Last connector ingest: {stats.get('last_ingest', 'never')}")


# ── TAB 3: PQC Wrapper ───────────────────────────────────────────────────────
def page_wrapper():
    st.markdown("#### PQC Wrapper — apply or remove quantum-safe wrap on LAN devices")

    devices = api_get("/api/devices") or []
    tokens = api_get("/api/tokens") or []

    # Connector token section
    st.markdown("##### Step 1 — Create connector token")
    with st.form("create_token"):
        tname = st.text_input("Connector name", value="Office LAN Connector")
        org = st.text_input("Organisation", value="My Organisation")
        if st.form_submit_button("Generate token", type="primary"):
            result = api_post("/api/tokens", {"name": tname, "org_name": org})
            if result:
                st.success("Token created — copy it now, it won't be shown again!")
                st.code(result["token"], language=None)
                st.session_state["last_token"] = result["token"]

    if tokens:
        st.markdown("**Active connectors**")
        st.dataframe(pd.DataFrame(tokens), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### Step 2 — Download LAN Connector")
    st.markdown("""
The **LAN Connector** is a small Python script that runs **inside your network**.
It scans local devices and uploads inventory to the cloud via HTTPS.

```
Your LAN  →  connector.py  →  HTTPS POST /api/ingest  →  Cloud Dashboard
                              Authorization: Bearer <token>
```

**How to use:**
1. Generate a token above
2. Download `connector.py` below
3. On a machine inside your LAN: `pip install requests`
4. Run: `python connector.py --token <token> --url <cloud-api-url>`
    """)

    connector_src = (ROOT / "connector" / "connector.py").read_text(encoding="utf-8")
    st.download_button(
        "⬇️ Download connector.py",
        connector_src,
        file_name="connector.py",
        mime="text/x-python",
        type="primary",
    )
    st.code(f"python connector.py --token YOUR_TOKEN --url {API}", language="bash")

    st.markdown("---")
    st.markdown("##### Step 3 — Wrap / unwrap devices")

    if not devices:
        st.warning("No devices in inventory. Run the connector first.")
        return

    df = pd.DataFrame(devices)
    st.dataframe(
        df[["id", "ip", "hostname", "service", "wrap_status", "priority_tier", "risk_score"]],
        use_container_width=True, hide_index=True,
    )

    selected = st.multiselect(
        "Select devices",
        options=df["id"].tolist(),
        format_func=lambda i: f"{df[df['id']==i]['ip'].values[0]} ({df[df['id']==i]['wrap_status'].values[0]})",
    )
    c1, c2 = st.columns(2)
    if c1.button("✅ Apply PQC Wrap", type="primary", disabled=not selected):
        r = api_post("/api/wrapper", {"device_ids": selected, "action": "apply"})
        if r:
            st.success(f"Wrapped {r['updated']} device(s)")
            st.rerun()
    if c2.button("❌ Remove Wrap", disabled=not selected):
        r = api_post("/api/wrapper", {"device_ids": selected, "action": "remove"})
        if r:
            st.success(f"Unwrapped {r['updated']} device(s)")
            st.rerun()


# ── TAB 4: PQC Inventory ─────────────────────────────────────────────────────
def page_inventory():
    st.markdown("#### PQC Inventory — staged hybrid onboarding")

    devices = api_get("/api/devices") or []
    if not devices:
        st.info("Run the LAN Connector to populate inventory.")
        return

    df = pd.DataFrame(devices)
    display_cols = [
        "ip", "service", "port", "tls_version", "cert_type",
        "weak_protocol", "pqc_candidate", "priority_tier", "wrap_status", "risk_score",
    ]
    existing = [c for c in display_cols if c in df.columns]

    for tier, label, color in [
        ("tier-1", "🔴 Tier 1 — Critical (onboard first)", "tier-1"),
        ("tier-2", "🟡 Tier 2 — Standard (week 3–6)", "tier-2"),
        ("tier-3", "⚪ Tier 3 — Low priority / IoT (week 7+)", "tier-3"),
    ]:
        subset = df[df["priority_tier"] == tier]
        st.markdown(f"### {label} ({len(subset)} devices)")
        if len(subset):
            st.dataframe(subset[existing], use_container_width=True, hide_index=True)
        else:
            st.caption("No devices in this tier.")

    st.markdown("---")
    st.markdown("#### 🤖 AI Migration Advisor")
    st.caption("Analyses your inventory and recommends onboarding order. Rule-based by default; uses OpenAI if API key is configured.")
    if st.button("Generate recommendation"):
        advice = api_get("/api/advisor")
        if advice:
            st.info(f"*Source: {advice['source']}*")
            st.markdown(advice["advice"])


# ── TAB 5: Reports ───────────────────────────────────────────────────────────
def page_reports():
    st.markdown("#### Reports & export")
    st.caption("Documentation for implementation planning, customer reporting, and HLD/LLD drafts.")

    reports = [
        ("inventory.csv", "CSV inventory", "csv"),
        ("inventory.json", "JSON connector output", "json"),
        ("inventory.pdf", "PDF report", "pdf"),
        ("migration.txt", "Migration summary", "migration"),
        ("hld.txt", "HLD-style summary", "hld"),
        ("change-plan.txt", "Change plan draft", "change-plan"),
        ("risk.txt", "Risk report", "risk"),
    ]

    cols = st.columns(3)
    for i, (fname, label, fmt) in enumerate(reports):
        with cols[i % 3]:
            try:
                r = httpx.get(f"{API}/api/reports/{fmt}", timeout=10)
                if r.status_code == 200:
                    st.download_button(
                        f"⬇️ {label}",
                        r.content if fmt == "pdf" else r.text,
                        file_name=fname,
                        mime="application/octet-stream",
                        key=f"dl_{fmt}",
                    )
            except Exception:
                st.button(f"{label} (API offline)", disabled=True, key=f"off_{fmt}")


# ── Main navigation ──────────────────────────────────────────────────────────
def main():
    header_bar()

    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio(
            "Go to",
            ["About", "Dashboard", "PQC Wrapper", "PQC Inventory", "Reports"],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption(f"API: `{API}`")
        if st.button("↻ Refresh data"):
            st.rerun()

    pages = {
        "About": page_about,
        "Dashboard": page_dashboard,
        "PQC Wrapper": page_wrapper,
        "PQC Inventory": page_inventory,
        "Reports": page_reports,
    }
    pages[page]()


main()
