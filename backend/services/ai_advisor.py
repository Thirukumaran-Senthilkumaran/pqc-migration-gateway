"""Simple AI Migration Advisor — rule-based with optional OpenAI."""

from __future__ import annotations

import os
from typing import Any

from ..models import LanDevice


def _rule_based_advice(devices: list[LanDevice]) -> str:
    if not devices:
        return (
            "No devices in inventory yet. Deploy the LAN Connector from the PQC Wrapper tab, "
            "run it inside your network, and wait for the first scan upload."
        )
    t1 = [d for d in devices if d.priority_tier == "tier-1"]
    t2 = [d for d in devices if d.priority_tier == "tier-2"]
    wrapped = [d for d in devices if d.wrap_status == "wrapped"]
    weak = [d for d in devices if d.weak_protocol]

    lines = [
        f"**Inventory summary:** {len(devices)} devices discovered.",
        f"**Tier-1 (critical):** {len(t1)} — onboard to PQC wrap within 7 days.",
        f"**Tier-2 (standard):** {len(t2)} — schedule within 30 days using hybrid gateway wrap.",
        f"**Currently PQC-wrapped:** {len(wrapped)} ({100*len(wrapped)//max(1,len(devices))}% coverage).",
    ]
    if weak:
        ips = ", ".join(d.ip for d in weak[:5])
        lines.append(f"**Weak crypto detected** on {len(weak)} host(s) e.g. {ips}. Prioritise gateway wrap immediately.")
    if t1:
        lines.append(
            f"**Recommended first wave:** wrap {', '.join(d.ip for d in t1[:3])} "
            "— highest risk scores and exposed services."
        )
    lines.append(
        "**Hybrid approach:** keep intra-LAN classical where trusted; apply PQC wrap on all "
        "egress and B2B paths first. Upgrade endpoints to native PQC tier-by-tier."
    )
    return "\n\n".join(lines)


def migration_advice(devices: list[LanDevice]) -> dict[str, Any]:
    text = _rule_based_advice(devices)
    source = "rule-engine"

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("PQCG_OPENAI_API_KEY")
    if api_key and devices:
        try:
            import httpx

            summary = "\n".join(
                f"{d.ip} tier={d.priority_tier} risk={d.risk_score} tls={d.tls_version} wrap={d.wrap_status}"
                for d in devices[:40]
            )
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a PQC migration consultant. Be concise, actionable."},
                        {"role": "user", "content": f"Advise on PQC onboarding order:\n{summary}"},
                    ],
                    "max_tokens": 400,
                },
                timeout=20,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                source = "openai"
        except Exception:
            pass

    return {"advice": text, "source": source}
