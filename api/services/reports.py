"""Report generation - CSV, JSON, text summaries, and a dependency-free PDF."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from ..models import LanDevice

COLUMNS = [
    "IP", "Service", "Port", "TLS Version", "Certificate Type",
    "Weak Protocol", "PQC Candidate", "Priority Tier", "Wrap Status", "Risk Score",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def devices_to_csv(devices: list[LanDevice]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for d in devices:
        w.writerow([
            d.ip, d.service, d.port, d.tls_version, d.cert_type,
            d.weak_protocol, d.pqc_candidate, d.priority_tier, d.wrap_status, d.risk_score,
        ])
    return buf.getvalue()


def devices_to_json(devices: list[LanDevice]) -> str:
    return json.dumps(
        {
            "generated": datetime.now(timezone.utc).isoformat(),
            "device_count": len(devices),
            "devices": [
                {
                    "ip": d.ip, "hostname": d.hostname, "service": d.service, "port": d.port,
                    "tls_version": d.tls_version, "cert_type": d.cert_type,
                    "weak_protocol": d.weak_protocol, "pqc_candidate": d.pqc_candidate,
                    "priority_tier": d.priority_tier, "wrap_status": d.wrap_status,
                    "risk_score": d.risk_score,
                }
                for d in devices
            ],
        },
        indent=2,
    )


def migration_summary(devices: list[LanDevice]) -> str:
    t1 = sum(1 for d in devices if d.priority_tier == "tier-1")
    t2 = sum(1 for d in devices if d.priority_tier == "tier-2")
    t3 = sum(1 for d in devices if d.priority_tier == "tier-3")
    wrapped = sum(1 for d in devices if d.wrap_status == "wrapped")
    cov = 100 * wrapped // max(1, len(devices))
    return (
        "PQC MIGRATION SUMMARY\n"
        "=====================\n"
        f"Generated:        {_now()}\n"
        f"Total devices:    {len(devices)}\n"
        f"Tier-1 (critical):{t1:>4}\n"
        f"Tier-2 (standard):{t2:>4}\n"
        f"Tier-3 (low/IoT): {t3:>4}\n"
        f"PQC-wrapped:      {wrapped:>4}  ({cov}% coverage)\n\n"
        "Approach: hybrid gateway wrap now, staged native PQC per tier.\n"
    )


def hld_summary(devices: list[LanDevice]) -> str:
    return (
        "HIGH-LEVEL DESIGN (HLD)\n"
        "=======================\n"
        f"Generated: {_now()}\n\n"
        "1. Solution overview\n"
        "   Cloud-hosted PQC Migration Gateway. A LAN Connector inside the customer\n"
        "   network uploads device/crypto inventory over HTTPS. The cloud plane manages\n"
        "   PQC wrap policy, staged migration, and reporting.\n\n"
        "2. Components\n"
        "   - LAN Connector (connector.py): metadata scanner, HTTPS POST /api/ingest.\n"
        "   - Cloud API (FastAPI): ingest, inventory, policy, reports. Bearer-token auth.\n"
        "   - Dashboard (Streamlit): operations UI.\n"
        "   - PQC engine: ML-KEM-768 + ML-DSA-65 (liboqs) or functional demo; AES-256-GCM.\n\n"
        "3. Crypto suite\n"
        "   KEM: ML-KEM-768   SIG: ML-DSA-65   AEAD: AES-256-GCM   KDF: HKDF-SHA256\n\n"
        "4. Migration phases\n"
        f"   Phase 0 - Deploy connector, baseline inventory ({len(devices)} endpoints).\n"
        "   Phase 1 - Wrap all egress + B2B via PQC gateway.\n"
        "   Phase 2 - Tier-1 native PQC upgrade.\n"
        "   Phase 3 - Tier-2 / Tier-3 rollout.\n"
        "   Phase 4 - Gateway standby for residual legacy.\n\n"
        "5. Security\n"
        "   Tokens hashed at rest (SHA-256). Metadata-only collection (no payloads).\n"
        "   TLS in transit. Server-authenticated PQC handshake (signed transcript).\n"
    )


def change_plan_draft(devices: list[LanDevice]) -> str:
    lines = ["CHANGE PLAN DRAFT", "=================", f"Generated: {_now()}", ""]
    for tier, window in [("tier-1", "Week 1-2"), ("tier-2", "Week 3-6"), ("tier-3", "Week 7-12")]:
        subset = [d for d in devices if d.priority_tier == tier]
        lines.append(f"{window} - {tier.upper()} ({len(subset)} devices)")
        for d in subset[:12]:
            lines.append(f"   - {d.ip:16} {d.service or 'unknown':10} -> {d.pqc_candidate}")
        if len(subset) > 12:
            lines.append(f"   ... and {len(subset) - 12} more")
        lines.append("")
    lines += [
        "Rollback: each wave is reversible (Remove wrap) with no endpoint changes.",
        "Validation: confirm tunnel handshake + AEAD round-trip per wave.",
    ]
    return "\n".join(lines)


def risk_report(devices: list[LanDevice]) -> str:
    high = sorted(devices, key=lambda d: d.risk_score, reverse=True)[:25]
    lines = ["RISK REPORT (top 25)", "====================", f"Generated: {_now()}", ""]
    for d in high:
        lines.append(
            f"{d.ip:16} risk={d.risk_score:>4.1f}  tier={d.priority_tier:7}  "
            f"tls={d.tls_version or 'n/a':8}  weak={d.weak_protocol or 'none'}"
        )
    if not high:
        lines.append("(no devices)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  PDF - try reportlab, else a correctly-offset minimal PDF                    #
# --------------------------------------------------------------------------- #
def devices_to_pdf(devices: list[LanDevice]) -> bytes:
    title = "PQC Gateway - Inventory Report"
    body_lines = [
        f"Generated: {_now()}",
        f"Total devices: {len(devices)}",
        "",
        f"{'IP':16}{'SERVICE':10}{'PORT':6}{'TLS':9}{'TIER':8}{'WRAP':8}",
    ]
    for d in devices[:45]:
        body_lines.append(
            f"{d.ip:16}{(d.service or '-'):10}{str(d.port or '-'):6}"
            f"{(d.tls_version or '-'):9}{d.priority_tier:8}{d.wrap_status:8}"
        )

    try:
        return _pdf_reportlab(title, body_lines)
    except Exception:
        return _pdf_minimal(title, body_lines)


def _pdf_reportlab(title: str, lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 28
    c.setFont("Courier", 9)
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont("Courier", 9)
            y = height - 50
        c.drawString(50, y, line[:110])
        y -= 13
    c.showPage()
    c.save()
    return buf.getvalue()


def _pdf_minimal(title: str, lines: list[str]) -> bytes:
    """Build a single-page PDF by hand with a correct xref table."""
    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content_parts = ["BT", "/F1 14 Tf", "50 800 Td", f"({esc(title)}) Tj", "/F1 9 Tf"]
    content_parts.append("0 -22 Td")
    for line in lines[:60]:
        content_parts.append(f"({esc(line[:110])}) Tj")
        content_parts.append("0 -13 Td")
    content_parts.append("ET")
    stream = "\n".join(content_parts)

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf.encode("latin-1", "replace")))
        pdf += f"{i} 0 obj\n{obj}\nendobj\n"

    xref_pos = len(pdf.encode("latin-1", "replace"))
    pdf += f"xref\n0 {len(objects) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n"
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    )
    return pdf.encode("latin-1", "replace")


REPORT_KINDS = {
    "csv": ("inventory.csv", "text/csv", False),
    "json": ("inventory.json", "application/json", False),
    "pdf": ("inventory.pdf", "application/pdf", True),
    "migration": ("migration-summary.txt", "text/plain", False),
    "hld": ("hld-summary.txt", "text/plain", False),
    "change-plan": ("change-plan.txt", "text/plain", False),
    "risk": ("risk-report.txt", "text/plain", False),
}


def render_report(fmt: str, devices: list[LanDevice]):
    """Return (content, is_binary) for a given report format."""
    if fmt == "csv":
        return devices_to_csv(devices), False
    if fmt == "json":
        return devices_to_json(devices), False
    if fmt == "pdf":
        return devices_to_pdf(devices), True
    if fmt == "migration":
        return migration_summary(devices), False
    if fmt == "hld":
        return hld_summary(devices), False
    if fmt == "change-plan":
        return change_plan_draft(devices), False
    if fmt == "risk":
        return risk_report(devices), False
    raise ValueError(f"Unknown report format: {fmt}")
