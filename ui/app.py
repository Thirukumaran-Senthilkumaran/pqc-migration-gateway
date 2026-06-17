"""PQC Migration Gateway - Streamlit dashboard (5 tabs + settings)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import api_client as api  # noqa: E402
from ui.theme import CSS  # noqa: E402

PROFILE_IMG = ROOT / "static" / "profile.jpg"
CONNECTOR_SRC = ROOT / "connector" / "connector.py"

st.set_page_config(page_title="PQC Migration Gateway", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  Shared chrome                                                              #
# --------------------------------------------------------------------------- #
def header_bar():
    c1, c2 = st.columns([6, 1])
    with c1:
        st.markdown(
            '<div class="pqc-header">'
            '<div><div class="title">🛡️ PQC Migration Gateway</div>'
            '<div class="subtitle">Wrap your LAN in post-quantum encryption — protect legacy '
            'devices that will never get a PQC upgrade</div></div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        with st.popover("⚙️ Settings", use_container_width=True):
            st.markdown("##### Notifications")
            st.checkbox("Email on new high-risk devices", value=True, key="n1")
            st.checkbox("Connector offline alerts", value=True, key="n2")
            st.checkbox("Weekly migration summary", value=False, key="n3")
            st.divider()
            st.markdown("##### Admin & privileges")
            st.text_input("Admin user", value="admin", disabled=True)
            st.selectbox("Privilege level", ["Viewer", "Operator", "Administrator"], index=2)
            st.toggle("Require MFA for policy changes", value=True)
            st.divider()
            st.markdown("##### Security & privacy")
            st.caption(
                "Connector tokens are hashed (SHA-256) at rest. Only network **metadata** is "
                "collected — never packet payloads. Data is encrypted in transit (HTTPS). "
                "Tokens can be revoked anytime from the PQC Wrapper tab."
            )


def tier_pill(tier: str) -> str:
    cls = {"tier-1": "pill-t1", "tier-2": "pill-t2", "tier-3": "pill-t3"}.get(tier, "pill-t3")
    return f'<span class="pill {cls}">{tier}</span>'


# --------------------------------------------------------------------------- #
#  TAB 1 — About                                                              #
# --------------------------------------------------------------------------- #
def page_about():
    col_img, col_txt = st.columns([1, 3])
    with col_img:
        if PROFILE_IMG.exists():
            st.image(str(PROFILE_IMG), width=190)
        else:
            st.image(
                "https://ui-avatars.com/api/?name=Thirukumaran+S&size=190&background=1761d2&color=fff&bold=true",
                width=190,
            )
    with col_txt:
        st.markdown("## Thirukumaran Senthilkumaran")
        st.markdown("**Network Security & IAM Enthusiast**")
        st.markdown("MSc Applied Cybersecurity — *University of South Wales*")
        st.markdown(
            '🔗 <a class="contact-link" href="https://www.linkedin.com/in/thirukumaran-s-45588b43" '
            'target="_blank">LinkedIn</a>',
            unsafe_allow_html=True,
        )

    st.markdown("""
I am a cybersecurity practitioner focused on **network security**, **identity & access
management**, and building defences that organisations can actually operate. My MSc gave me
a foundation in threat modelling and secure architecture; what drives me is turning that into
systems that **solve real business problems**.

Cybersecurity must be **proactive** — woven into infrastructure, not owned by one team.
As we enter the **AI era**, attack surfaces evolve faster than policy. Networks must be
resilient: ready to detect, adapt, and recover without halting the business.
""")

    st.markdown("### Why I built this")
    st.markdown("""
NIST has standardised **ML-KEM** and **ML-DSA**. Critical infrastructure is already
inventorying its cryptography — but **SMBs and legacy estates risk being left behind**.
Hundreds of devices will never receive native PQC firmware. A **gateway-based migration**
delivers quantum-safe coverage *now*, then upgrades endpoints tier-by-tier — no big-bang
cutover. It also secures **B2B data transfer** between organisations over a PQC tunnel.
""")

    st.markdown("### Contact")
    st.markdown(
        '- 🔗 <a class="contact-link" href="https://www.linkedin.com/in/thirukumaran-s-45588b43" target="_blank">www.linkedin.com/in/thirukumaran-s-45588b43</a>  \n'
        '- ✉️ <a class="contact-link" href="mailto:Thirukumaranarun98@gmail.com">Thirukumaranarun98@gmail.com</a>  \n'
        '- 💬 WhatsApp: <a class="contact-link" href="https://wa.me/918098276733" target="_blank">+91 8098276733</a>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
#  TAB 2 — Dashboard                                                          #
# --------------------------------------------------------------------------- #
def page_dashboard():
    stats = api.get("/api/dashboard")
    devices = api.get("/api/devices") or []

    if stats:
        m = st.columns(5)
        m[0].metric("LAN devices", stats["total_devices"])
        m[1].metric("PQC wrapped", stats["wrapped_devices"])
        m[2].metric("PQC coverage", f"{stats['pqc_coverage_pct']}%")
        m[3].metric("Tier-1 critical", stats["tier1_devices"])
        m[4].metric("Connectors online", stats["connectors_online"])

        safe = stats.get("quantum_safe")
        chip = ('<span class="chip chip-green">quantum-safe (liboqs)</span>' if safe
                else '<span class="chip chip-blue">demo PQC engine</span>')
        st.markdown(
            f"PQC engine: **{stats.get('pqc_backend','demo')}** &nbsp; {chip}",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("#### LAN traffic & PQC state")
        if devices:
            df = pd.DataFrame(devices)
            wrap_counts = df["wrap_status"].value_counts().rename(
                {"wrapped": "PQC wrapped", "none": "Unprotected"}
            )
            st.bar_chart(wrap_counts, color="#1761d2", height=240)
            st.caption("Devices by priority tier")
            st.bar_chart(df["priority_tier"].value_counts().sort_index(), color="#2f8bff", height=200)
        else:
            st.info("No inventory yet. Deploy the LAN Connector from the **PQC Wrapper** tab.")

    with c2:
        st.markdown("#### Remote gateway (B2B)")
        st.caption("Secure business-to-business data transfer over a PQC-wrapped cloud tunnel.")
        rg = api.post("/api/remote-gateway", {})
        if rg:
            st.markdown(
                f'<span class="chip chip-green">{rg["status"]}</span>', unsafe_allow_html=True
            )
            st.code(f"Peer ID: {rg['peer_id']}", language=None)
            st.caption("Share this peer ID with a B2B partner to establish a PQC data path.")
        if stats and stats.get("last_ingest"):
            st.caption(f"Last connector ingest: {stats['last_ingest']}")


# --------------------------------------------------------------------------- #
#  TAB 3 — PQC Wrapper                                                        #
# --------------------------------------------------------------------------- #
def page_wrapper():
    devices = api.get("/api/devices") or []
    tokens = api.get("/api/tokens") or []

    st.markdown("#### Step 1 — Create a connector token")
    st.caption("The token authenticates your LAN Connector to the cloud (Authorization: Bearer ...).")
    with st.form("create_token"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Connector name", value="Office LAN Connector")
        org = c2.text_input("Organisation", value="My Organisation")
        if st.form_submit_button("Generate token", type="primary"):
            res = api.post("/api/tokens", {"name": name, "org_name": org})
            if res:
                st.success("Token created — copy it now, it won't be shown again!")
                st.code(res["token"], language=None)

    if tokens:
        st.markdown("**Active connectors**")
        st.dataframe(
            pd.DataFrame(tokens)[["name", "org_name", "token_prefix", "device_count", "last_seen", "active"]],
            use_container_width=True, hide_index=True,
        )

    st.markdown("---")
    st.markdown("#### Step 2 — Download & run the LAN Connector")
    api_url = api.current_url()
    st.markdown(f"""
The **LAN Connector** is a small Python script that runs **inside your network**. It scans
device & crypto metadata (no payloads) and uploads it to the cloud over HTTPS.

```
Your LAN  →  connector.py  →  HTTPS POST /api/ingest  →  Cloud dashboard
                             Authorization: Bearer <token>
```

**Run it:**
1. Copy a token from Step 1.
2. Download `connector.py` below.
3. On a machine inside your LAN: `pip install requests`
4. `python connector.py --token <token> --url {api_url}`
""")

    if CONNECTOR_SRC.exists():
        st.download_button(
            "⬇️ Download connector.py",
            CONNECTOR_SRC.read_text(encoding="utf-8"),
            file_name="connector.py",
            mime="text/x-python",
            type="primary",
        )
    st.code(f"python connector.py --token pqcg_YOUR_TOKEN --url {api_url}", language="bash")

    st.markdown("---")
    st.markdown("#### Step 3 — Apply / remove PQC wrap on LAN devices")
    if not devices:
        st.warning("No devices in inventory yet. Run the connector first.")
    else:
        df = pd.DataFrame(devices)
        df_view = df[["id", "ip", "service", "priority_tier", "risk_score", "wrap_status"]].copy()
        df_view.insert(0, "select", False)
        edited = st.data_editor(
            df_view, use_container_width=True, hide_index=True,
            column_config={"select": st.column_config.CheckboxColumn("✓", width="small")},
            disabled=["id", "ip", "service", "priority_tier", "risk_score", "wrap_status"],
            key="wrap_editor",
        )
        selected = edited[edited["select"]]["id"].tolist()
        c1, c2, c3 = st.columns([1, 1, 4])
        if c1.button("🔒 Apply wrap", type="primary", disabled=not selected):
            res = api.post("/api/wrapper", {"device_ids": selected, "action": "apply"})
            if res:
                st.success(f"Wrapped {res['updated']} device(s).")
                st.rerun()
        if c2.button("🔓 Remove wrap", disabled=not selected):
            res = api.post("/api/wrapper", {"device_ids": selected, "action": "remove"})
            if res:
                st.success(f"Unwrapped {res['updated']} device(s).")
                st.rerun()

    st.markdown("---")
    st.markdown("#### Live PQC tunnel — prove the wrap actually works")
    st.caption("Runs a real post-quantum handshake (KEM + signed transcript) and AES-256-GCM "
               "record, then verifies the data is recovered. This is the gateway mechanism.")
    c1, c2 = st.columns([3, 1])
    msg = c1.text_input("Plaintext to wrap", value="Confidential LAN payload", label_visibility="collapsed")
    mode = c2.selectbox("Mode", ["memory", "socket"], label_visibility="collapsed")
    if st.button("Run PQC wrap test"):
        res = api.post("/api/pqc/wrap-demo", {"message": msg, "mode": mode})
        if res:
            if mode == "socket":
                ok = res.get("ok")
                st.markdown(
                    f'{"✅" if ok else "❌"} Socket tunnel round-trip on port '
                    f'**{res.get("gateway_port")}** — `{res.get("response")}`'
                )
                st.json(res.get("transcript", {}))
            else:
                st.markdown(
                    f'{"✅" if res.get("verified") else "❌"} **Verified** — '
                    f'{res.get("kem_alg")} / {res.get("sig_alg")} '
                    f'({"quantum-safe" if res.get("quantum_safe") else "demo"})'
                )
                d1, d2 = st.columns(2)
                d1.metric("Ciphertext bytes", res.get("ciphertext_bytes"))
                d2.metric("Keys match", "yes" if res.get("keys_match") else "no")
                st.text_input("Wrapped (AES-256-GCM, hex)", value=res.get("ciphertext_hex", "")[:120] + " ...")
                st.text_input("Recovered plaintext", value=res.get("recovered", ""))


# --------------------------------------------------------------------------- #
#  TAB 4 — PQC Inventory                                                      #
# --------------------------------------------------------------------------- #
def page_inventory():
    devices = api.get("/api/devices") or []
    st.markdown("#### PQC onboarding priority")
    st.caption("Devices are tiered by risk so you can migrate in waves — a hybrid rollout, "
               "not a single-day cutover.")

    if not devices:
        st.info("No inventory yet. Deploy the LAN Connector from **PQC Wrapper**.")
        return

    df = pd.DataFrame(devices)
    cols = ["ip", "service", "port", "tls_version", "cert_type", "weak_protocol",
            "pqc_candidate", "wrap_status", "risk_score"]
    rename = {
        "ip": "IP", "service": "Service", "port": "Port", "tls_version": "TLS Version",
        "cert_type": "Certificate Type", "weak_protocol": "Weak Protocol",
        "pqc_candidate": "PQC Candidate", "wrap_status": "Wrap", "risk_score": "Risk",
    }

    tiers = [
        ("tier-1", "Tier 1 — Critical (wrap within 7 days)", "🔴"),
        ("tier-2", "Tier 2 — Standard (within 30 days)", "🟠"),
        ("tier-3", "Tier 3 — Low / IoT (monitor & schedule)", "⚪"),
    ]
    for tier, label, icon in tiers:
        subset = df[df["priority_tier"] == tier]
        st.markdown(f"##### {icon} {label} — {len(subset)} device(s)")
        if len(subset):
            st.dataframe(subset[cols].rename(columns=rename), use_container_width=True, hide_index=True)
        else:
            st.caption("None in this tier.")
        st.markdown("")

    st.markdown("---")
    st.markdown("### 🤖 AI Migration Advisor")
    st.caption("Analyses your inventory and recommends a staged onboarding order. "
               "Rule-based by default; uses OpenAI if an API key is configured.")
    if st.button("Generate recommendation", type="primary"):
        advice = api.get("/api/advisor")
        if advice:
            st.info(f"Source: {advice['source']}")
            st.markdown(advice["advice"])


# --------------------------------------------------------------------------- #
#  TAB 5 — Reports                                                            #
# --------------------------------------------------------------------------- #
def page_reports():
    st.markdown("#### Reports & export")
    st.caption("Consulting-grade documentation: implementation planning, HLD, change control, "
               "and customer reporting.")

    reports = [
        ("inventory.csv", "CSV inventory", "csv"),
        ("inventory.json", "JSON (connector output)", "json"),
        ("inventory.pdf", "PDF report", "pdf"),
        ("migration-summary.txt", "Migration summary", "migration"),
        ("hld-summary.txt", "HLD-style summary", "hld"),
        ("change-plan.txt", "Change plan draft", "change-plan"),
        ("risk-report.txt", "Risk report", "risk"),
    ]
    cols = st.columns(3)
    for i, (fname, label, fmt) in enumerate(reports):
        with cols[i % 3]:
            content, is_binary = api.get_report(fmt)
            if content is not None:
                st.download_button(f"⬇️ {label}", content, file_name=fname,
                                   mime="application/octet-stream", key=f"dl_{fmt}",
                                   use_container_width=True)
            else:
                st.button(f"{label} (unavailable)", disabled=True, key=f"off_{fmt}",
                          use_container_width=True)


# --------------------------------------------------------------------------- #
#  Sidebar + routing                                                          #
# --------------------------------------------------------------------------- #
def sidebar() -> str:
    with st.sidebar:
        st.markdown("## PQC Gateway")
        page = st.radio("Navigation", ["About", "Dashboard", "PQC Wrapper", "PQC Inventory", "Reports"],
                        label_visibility="collapsed")
        st.divider()

        connected, label = api.status()
        if connected and "built-in" in label:
            st.success("Backend: built-in (in-process)")
        elif connected:
            st.success("API connected")
        else:
            st.error("API offline")
        st.caption(f"URL: `{api.current_url()}`")

        with st.expander("Connection settings"):
            mode_labels = {"auto": "Auto (recommended)", "embedded": "Built-in only", "remote": "Remote API only"}
            current = st.session_state.get("api_mode", "auto")
            choice = st.radio("Backend mode", list(mode_labels.values()),
                              index=list(mode_labels).index(current))
            new_mode = {v: k for k, v in mode_labels.items()}[choice]
            if new_mode != current:
                st.session_state["api_mode"] = new_mode
                st.session_state.pop("_embedded_fallback", None)
                st.rerun()
            url = st.text_input("Remote API URL", value=st.session_state.get("api_url_override") or api.default_url())
            if st.button("Apply URL"):
                st.session_state["api_url_override"] = api.normalize_url(url)
                st.session_state.pop("_embedded_fallback", None)
                st.rerun()
            st.caption("Local: `http://127.0.0.1:8000` · Cloud: your Render API URL")

        if st.button("↻ Refresh"):
            st.rerun()
        st.caption("DIY post-quantum LAN protection")
    return page


PAGES = {
    "About": page_about,
    "Dashboard": page_dashboard,
    "PQC Wrapper": page_wrapper,
    "PQC Inventory": page_inventory,
    "Reports": page_reports,
}


def main():
    header_bar()
    PAGES[sidebar()]()


main()
