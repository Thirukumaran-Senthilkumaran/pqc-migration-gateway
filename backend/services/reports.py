"""Report generation — CSV, JSON, PDF."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from ..models import LanDevice


def devices_to_csv(devices: list[LanDevice]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "IP", "Service", "Port", "TLS Version", "Certificate Type",
        "Weak Protocol", "PQC Candidate", "Priority Tier", "Wrap Status", "Risk Score",
    ])
    for d in devices:
        w.writerow([
            d.ip, d.service, d.port, d.tls_version, d.cert_type,
            d.weak_protocol, d.pqc_candidate, d.priority_tier, d.wrap_status, d.risk_score,
        ])
    return buf.getvalue()


def devices_to_json(devices: list[LanDevice]) -> str:
    return json.dumps([
        {
            "ip": d.ip, "service": d.service, "port": d.port,
            "tls_version": d.tls_version, "cert_type": d.cert_type,
            "weak_protocol": d.weak_protocol, "pqc_candidate": d.pqc_candidate,
            "priority_tier": d.priority_tier, "wrap_status": d.wrap_status,
            "risk_score": d.risk_score,
        }
        for d in devices
    ], indent=2)


def migration_summary(devices: list[LanDevice]) -> str:
    t1 = sum(1 for d in devices if d.priority_tier == "tier-1")
    t2 = sum(1 for d in devices if d.priority_tier == "tier-2")
    t3 = sum(1 for d in devices if d.priority_tier == "tier-3")
    wrapped = sum(1 for d in devices if d.wrap_status == "wrapped")
    return f"""PQC Migration Summary
Generated: {datetime.now(timezone.utc).isoformat()}
Total devices: {len(devices)}
Tier-1 (critical): {t1}
Tier-2 (standard): {t2}
Tier-3 (low/IoT): {t3}
PQC-wrapped: {wrapped}
Coverage: {100*wrapped//max(1,len(devices))}%
Approach: Hybrid gateway wrap → staged native PQC per tier
"""


def hld_summary(devices: list[LanDevice]) -> str:
    return f"""High-Level Design Summary
=========================
Architecture: Cloud PQC Gateway + LAN Connector
- Connector runs inside customer LAN (HTTPS POST /api/ingest)
- Cloud dashboard: inventory, wrap policy, migration planning
- PQC algorithms: ML-KEM-768, ML-DSA-65, AES-256-GCM (hybrid)

Inventory: {len(devices)} endpoints
Migration phases:
  Phase 0: Deploy connector, baseline inventory
  Phase 1: Wrap all egress via cloud gateway
  Phase 2: Tier-1 native PQC upgrade
  Phase 3: Tier-2 / Tier-3 rollout
  Phase 4: Gateway standby for residual legacy
"""


def change_plan_draft(devices: list[LanDevice]) -> str:
    lines = ["Change Plan Draft", "================", ""]
    for tier, label in [("tier-1", "Week 1-2"), ("tier-2", "Week 3-6"), ("tier-3", "Week 7-12")]:
        subset = [d for d in devices if d.priority_tier == tier]
        lines.append(f"{label} — {tier.upper()} ({len(subset)} devices)")
        for d in subset[:10]:
            lines.append(f"  - {d.ip} ({d.service or 'unknown'}) → {d.pqc_candidate}")
        if len(subset) > 10:
            lines.append(f"  ... and {len(subset)-10} more")
        lines.append("")
    return "\n".join(lines)


def risk_report(devices: list[LanDevice]) -> str:
    high = sorted(devices, key=lambda d: d.risk_score, reverse=True)[:20]
    lines = ["Risk Report", "============", ""]
    for d in high:
        lines.append(
            f"{d.ip:16} risk={d.risk_score:.1f}  tls={d.tls_version or 'n/a'}  "
            f"weak={d.weak_protocol or 'none'}  tier={d.priority_tier}"
        )
    return "\n".join(lines)


def devices_to_pdf(devices: list[LanDevice]) -> bytes:
    """Minimal PDF using raw PDF syntax (no reportlab dependency)."""
    lines = [
        "PQC Gateway Inventory Report",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Total devices: {len(devices)}",
        "",
    ]
    for d in devices[:50]:
        lines.append(
            f"{d.ip} | {d.service or '-'} | {d.port or '-'} | {d.tls_version or '-'} | "
            f"{d.pqc_candidate or '-'} | {d.wrap_status}"
        )
    text = "\\n".join(lines[:60])
    # Minimal valid PDF
    content = f"BT /F1 10 Tf 50 750 Td ({text[:3000].replace('(', '\\(').replace(')', '\\)')}) Tj ET"
    pdf = f"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length {len(content)} >>stream
{content}
endstream endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
400
%%EOF"""
    return pdf.encode("latin-1", errors="replace")
