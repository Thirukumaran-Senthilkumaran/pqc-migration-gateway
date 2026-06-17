"""Node classifier.

Computes:
    pqc_ready   – likelihood the device can do PQC itself (0–10)
    risk        – exposure × sensitivity (0–10)
    priority    – overall migration priority score
    tier        – tier-1 / tier-2 / tier-3

Heuristics — intentionally readable & overridable. The dashboard lets the
operator nudge any of these manually; the classifier never overrides
operator-set values without explicit consent.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from ..database import session_scope
from ..models import Node, PriorityTier

logger = logging.getLogger(__name__)


# Categories of services / ports → readiness & risk weights
SERVICE_PROFILE: dict[int, dict[str, float]] = {
    22:   {"name": "ssh",       "ready": 7.0, "risk": 6.0},
    23:   {"name": "telnet",    "ready": 1.0, "risk": 9.0},
    53:   {"name": "dns",       "ready": 4.0, "risk": 6.0},
    80:   {"name": "http",      "ready": 3.0, "risk": 4.0},
    102:  {"name": "iso-tsap",  "ready": 1.0, "risk": 9.0},
    443:  {"name": "https",     "ready": 6.0, "risk": 5.0},
    502:  {"name": "modbus",    "ready": 0.5, "risk": 9.0},
    1883: {"name": "mqtt",      "ready": 2.0, "risk": 7.0},
    5060: {"name": "sip",       "ready": 3.0, "risk": 6.0},
    8080: {"name": "http-alt",  "ready": 3.5, "risk": 4.0},
    8443: {"name": "https-alt", "ready": 6.5, "risk": 5.0},
    8883: {"name": "mqtts",     "ready": 5.0, "risk": 6.0},
}


def _parse_ports(csv: str | None) -> list[int]:
    if not csv:
        return []
    out = []
    for p in csv.split(","):
        try:
            out.append(int(p.strip()))
        except ValueError:
            continue
    return out


def _vendor_readiness(vendor: str | None) -> float | None:
    if not vendor:
        return None
    v = vendor.lower()
    if any(k in v for k in ("apple", "google", "microsoft", "raspberry")):
        return 6.5  # actively maintained → upgrade path likely
    if any(k in v for k in ("siemens", "schneider", "honeywell", "espressif")):
        return 2.0  # industrial / IoT → constrained
    return None


def classify_node(node: Node) -> Node:
    ports = _parse_ports(node.open_ports)
    services = [SERVICE_PROFILE[p]["name"] for p in ports if p in SERVICE_PROFILE]
    node.services = ",".join(services) if services else None

    # readiness (only auto-set if operator hasn't pinned)
    if node.pqc_ready in (0.0, None):
        readiness_scores: list[float] = []
        for p in ports:
            prof = SERVICE_PROFILE.get(p)
            if prof:
                readiness_scores.append(prof["ready"])
        v_ready = _vendor_readiness(node.vendor)
        if v_ready is not None:
            readiness_scores.append(v_ready)
        node.pqc_ready = round(
            sum(readiness_scores) / len(readiness_scores) if readiness_scores else 3.0,
            2,
        )

    # risk (only auto-set if untouched / default)
    if node.risk in (5.0, None):
        risk_scores = [SERVICE_PROFILE[p]["risk"] for p in ports if p in SERVICE_PROFILE]
        node.risk = round(
            sum(risk_scores) / len(risk_scores) if risk_scores else 5.0, 2
        )

    # priority = criticality * 1.5  +  risk  -  pqc_ready
    score = (node.criticality or 5.0) * 1.5 + (node.risk or 5.0) - (node.pqc_ready or 3.0)
    node.priority_score = round(score, 2)

    if score >= 14:
        node.priority_tier = PriorityTier.TIER_1
    elif score >= 9:
        node.priority_tier = PriorityTier.TIER_2
    else:
        node.priority_tier = PriorityTier.TIER_3

    return node


async def reclassify_all() -> int:
    """Re-run the classifier across every node. Returns count updated."""
    n = 0
    async with session_scope() as db:
        rows = (await db.execute(select(Node))).scalars().all()
        for row in rows:
            classify_node(row)
            n += 1
    logger.info("Reclassified %d nodes", n)
    return n
