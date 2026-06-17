"""AI Migration Advisor - rule engine with optional OpenAI augmentation."""

from __future__ import annotations

import os
from typing import Any

from ..models import LanDevice


def _rule_based_advice(devices: list[LanDevice]) -> str:
    if not devices:
        return (
            "No devices in inventory yet. Create a connector token in **PQC Wrapper**, "
            "download the LAN Connector, and run it inside your network. The first scan "
            "will populate this advisor automatically."
        )

    t1 = [d for d in devices if d.priority_tier == "tier-1"]
    t2 = [d for d in devices if d.priority_tier == "tier-2"]
    t3 = [d for d in devices if d.priority_tier == "tier-3"]
    wrapped = [d for d in devices if d.wrap_status == "wrapped"]
    weak = [d for d in devices if d.weak_protocol]
    coverage = 100 * len(wrapped) // max(1, len(devices))

    lines = [
        f"**Inventory:** {len(devices)} devices · **PQC coverage:** {coverage}%",
        "",
        "**Recommended onboarding waves (hybrid, staged):**",
        f"- **Wave 1 — Tier-1 ({len(t1)} devices), days 0-7:** highest risk / exposed "
        "services. Apply gateway wrap immediately; these cannot wait for native firmware.",
        f"- **Wave 2 — Tier-2 ({len(t2)} devices), weeks 2-4:** standard business systems. "
        "Wrap egress + B2B paths first, then schedule native PQC where supported.",
        f"- **Wave 3 — Tier-3 ({len(t3)} devices), weeks 5-12:** low-risk / IoT. Monitor and "
        "wrap opportunistically.",
    ]

    if weak:
        ips = ", ".join(d.ip for d in weak[:5])
        lines.append("")
        lines.append(
            f"**Urgent:** weak crypto found on {len(weak)} host(s) (e.g. {ips}). "
            "These are quantum-AND-classical risks today — wrap them first."
        )

    if t1:
        first = ", ".join(d.ip for d in sorted(t1, key=lambda d: d.risk_score, reverse=True)[:3])
        lines.append("")
        lines.append(f"**Start here:** wrap {first} — top risk scores in your estate.")

    lines.append("")
    lines.append(
        "**Principle:** protect every egress and B2B path with PQC now; keep trusted "
        "intra-LAN classical only where it is low risk; migrate endpoints to native PQC "
        "tier-by-tier to avoid a big-bang cutover."
    )
    return "\n".join(lines)


def migration_advice(devices: list[LanDevice]) -> dict[str, Any]:
    text = _rule_based_advice(devices)
    source = "rule-engine"

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("PQCG_OPENAI_API_KEY")
    if api_key and devices:
        try:
            import httpx

            summary = "\n".join(
                f"{d.ip} tier={d.priority_tier} risk={d.risk_score} svc={d.service} "
                f"tls={d.tls_version} weak={d.weak_protocol} wrap={d.wrap_status}"
                for d in devices[:40]
            )
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a post-quantum migration consultant. "
                            "Give concise, actionable, staged advice for a hybrid PQC rollout.",
                        },
                        {"role": "user", "content": f"Advise on PQC onboarding order:\n{summary}"},
                    ],
                    "max_tokens": 450,
                },
                timeout=20,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                source = "openai:gpt-4o-mini"
        except Exception:
            pass

    return {"advice": text, "source": source}
