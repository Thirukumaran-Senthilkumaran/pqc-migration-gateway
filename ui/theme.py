"""Light, polished, Sophos-inspired theme."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: #f5f7fb; }
.block-container { padding-top: 1.2rem; max-width: 1320px; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f1b34;
    border-right: 1px solid #0b1426;
}
section[data-testid="stSidebar"] * { color: #cdd7ec; }
section[data-testid="stSidebar"] .stRadio label { color: #e6ecf8; font-weight: 500; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #ffffff; }

/* Header bar */
.pqc-header {
    background: linear-gradient(100deg, #0a2540 0%, #1761d2 60%, #2f8bff 100%);
    color: #fff;
    padding: 1.0rem 1.4rem;
    border-radius: 14px;
    margin-bottom: 1.2rem;
    box-shadow: 0 8px 24px rgba(23,97,210,0.18);
    display: flex; align-items: center; justify-content: space-between;
}
.pqc-header .title { font-size: 1.25rem; font-weight: 800; letter-spacing: .2px; }
.pqc-header .subtitle { font-size: .82rem; opacity: .9; font-weight: 500; }

/* Cards */
.metric-card {
    background: #fff; border: 1px solid #e6ebf3; border-radius: 14px;
    padding: 1.1rem 1.2rem; box-shadow: 0 2px 10px rgba(16,40,80,0.05);
}
.card {
    background: #fff; border: 1px solid #e6ebf3; border-radius: 14px;
    padding: 1.2rem 1.3rem; box-shadow: 0 2px 10px rgba(16,40,80,0.05);
    margin-bottom: 1rem;
}
div[data-testid="stMetric"] {
    background: #fff; border: 1px solid #e6ebf3; border-radius: 14px;
    padding: 0.9rem 1rem; box-shadow: 0 2px 10px rgba(16,40,80,0.05);
}
div[data-testid="stMetricValue"] { color: #0a2540; font-weight: 800; }

/* Pills */
.pill { padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 700; }
.pill-t1 { background: #fde8e8; color: #c0282d; }
.pill-t2 { background: #fff3e0; color: #b76e00; }
.pill-t3 { background: #e9f0ff; color: #2456c8; }
.pill-ok { background: #e3f7ec; color: #1a7f4b; }
.pill-warn { background: #fff3e0; color: #b76e00; }

/* Buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: 10px; font-weight: 600; border: 1px solid #d7dff0;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: linear-gradient(100deg, #1761d2, #2f8bff); border: none;
}

/* Status chips */
.chip { display:inline-block; padding: 4px 12px; border-radius: 999px; font-weight:600; font-size:.8rem;}
.chip-green { background:#e3f7ec; color:#1a7f4b; }
.chip-red { background:#fde8e8; color:#c0282d; }
.chip-blue { background:#e9f0ff; color:#2456c8; }

a.contact-link { color:#1761d2; text-decoration:none; font-weight:600; }
a.contact-link:hover { text-decoration:underline; }

hr { margin: 0.8rem 0; border-color:#e6ebf3; }
</style>
"""
