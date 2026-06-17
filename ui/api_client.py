"""
API client used by the dashboard.

Resolves the API base URL (Streamlit secret -> env -> default), normalises
loopback addresses to avoid the 'errno 99 / cannot assign requested address'
class of bugs, and transparently falls back to the embedded in-process backend
when a remote API is unreachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st

_SECRET_PATHS = (
    Path.home() / ".streamlit" / "secrets.toml",
    Path.cwd() / ".streamlit" / "secrets.toml",
    Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml",
)


def _secret(key: str) -> str | None:
    """Read a Streamlit secret only if a secrets file exists (avoids noisy warnings)."""
    if not any(p.exists() for p in _SECRET_PATHS):
        return None
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        return None
    return None

_FALLBACK_MARKERS = (
    "99", "cannot assign", "addrnotavail", "connection refused",
    "failed to connect", "connect error", "name or service not known",
    "timed out", "all connection attempts failed",
)


def normalize_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    u = u.replace("://localhost", "://127.0.0.1").replace("://0.0.0.0", "://127.0.0.1")
    return u


def default_url() -> str:
    secret = _secret("API_BASE_URL")
    if secret:
        return normalize_url(secret)
    return normalize_url(os.getenv("API_BASE_URL", os.getenv("PQCG_API_URL", "http://127.0.0.1:8000")))


def current_url() -> str:
    override = (st.session_state.get("api_url_override") or "").strip()
    return normalize_url(override) if override else default_url()


def _mode() -> str:
    return st.session_state.get("api_mode", "auto")


def _embedded_active() -> bool:
    m = _mode()
    if m == "embedded":
        return True
    if m == "remote":
        return False
    return bool(st.session_state.get("_embedded_fallback"))


def _should_fallback(err: Exception) -> bool:
    msg = str(err).lower()
    return any(marker in msg for marker in _FALLBACK_MARKERS)


def _enable_fallback() -> None:
    st.session_state["_embedded_fallback"] = True


# --- public surface -------------------------------------------------------- #
def status() -> tuple[bool, str]:
    """Return (connected, mode_label)."""
    if _embedded_active():
        return True, "built-in"
    url = current_url()
    try:
        r = httpx.get(f"{url}/api/health", timeout=5)
        return (r.status_code == 200), "remote"
    except Exception as e:
        if _mode() == "auto" and _should_fallback(e):
            _enable_fallback()
            return True, "built-in (auto)"
        return False, "remote"


def get(path: str):
    if _embedded_active():
        from . import embedded

        try:
            return embedded.get(path)
        except Exception as e:
            st.error(f"Built-in backend error: {e}")
            return None
    url = current_url()
    try:
        r = httpx.get(f"{url}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if _mode() == "auto" and _should_fallback(e):
            _enable_fallback()
            return get(path)
        st.error(f"API unreachable (`{url}`): {e}")
        return None


def post(path: str, body: dict):
    if _embedded_active():
        from . import embedded

        try:
            return embedded.post(path, body)
        except Exception as e:
            st.error(f"Built-in backend error: {e}")
            return None
    url = current_url()
    try:
        r = httpx.post(f"{url}{path}", json=body, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if _mode() == "auto" and _should_fallback(e):
            _enable_fallback()
            return post(path, body)
        st.error(f"API error (`{url}`): {e}")
        return None


def get_report(fmt: str):
    """Return (content, is_binary) or (None, None)."""
    path = f"/api/reports/{fmt}"
    if _embedded_active():
        from . import embedded

        try:
            return embedded.get_report(fmt)
        except Exception:
            return None, None
    url = current_url()
    try:
        r = httpx.get(f"{url}{path}", timeout=15)
        if r.status_code == 200:
            return (r.content, True) if fmt == "pdf" else (r.text, False)
    except Exception as e:
        if _mode() == "auto" and _should_fallback(e):
            _enable_fallback()
            return get_report(fmt)
    return None, None
