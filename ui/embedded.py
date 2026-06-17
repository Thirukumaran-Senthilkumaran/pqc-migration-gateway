"""
Embedded backend access.

Lets the dashboard run the full backend in-process when a separate API service
is unreachable (e.g. pure-local demo, or the classic 'errno 99' when the UI is
pointed at an address it cannot reach). Mirrors the HTTP API responses.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from api.auth import create_connector_token
from api.database import SessionLocal, init_db
from api.models import ConnectorHeartbeat, ConnectorToken, LanDevice, RemoteGateway
from api.schemas import DeviceOut, TokenOut
from api.services.ai_advisor import migration_advice
from api.services.reports import render_report

_ready = False


def _ensure() -> None:
    global _ready
    if not _ready:
        init_db()
        _ready = True


def _iso(dt):
    return dt.isoformat() if dt else None


def get(path: str):
    _ensure()
    db = SessionLocal()
    try:
        if path == "/api/health":
            from pqc.backend import get_backend

            b = get_backend()
            return {"status": "ok", "service": "pqc-migration-gateway",
                    "pqc_backend": b.info.name, "quantum_safe": b.info.quantum_safe}

        if path == "/api/devices":
            rows = db.query(LanDevice).order_by(LanDevice.risk_score.desc()).all()
            return [DeviceOut.model_validate(r).model_dump(mode="json") for r in rows]

        if path == "/api/tokens":
            rows = db.query(ConnectorToken).order_by(ConnectorToken.created_at.desc()).all()
            out = []
            for r in rows:
                cnt = db.query(func.count(LanDevice.id)).filter(LanDevice.token_id == r.id).scalar()
                out.append(TokenOut(
                    id=r.id, name=r.name, token_prefix=r.token_prefix, org_name=r.org_name,
                    active=r.active, created_at=r.created_at, last_seen=r.last_seen,
                    device_count=cnt or 0,
                ).model_dump(mode="json"))
            return out

        if path == "/api/dashboard":
            from pqc.backend import get_backend

            total = db.query(func.count(LanDevice.id)).scalar() or 0
            wrapped = db.query(func.count(LanDevice.id)).filter(LanDevice.wrap_status == "wrapped").scalar() or 0
            t1 = db.query(func.count(LanDevice.id)).filter(LanDevice.priority_tier == "tier-1").scalar() or 0
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            online = db.query(func.count(ConnectorToken.id)).filter(ConnectorToken.last_seen >= cutoff).scalar() or 0
            last_hb = db.query(func.max(ConnectorHeartbeat.received_at)).scalar()
            rg = db.query(RemoteGateway).first()
            b = get_backend()
            return {
                "total_devices": total, "wrapped_devices": wrapped, "tier1_devices": t1,
                "connectors_online": online,
                "pqc_coverage_pct": round(100 * wrapped / max(1, total), 1),
                "remote_gateway_status": rg.status if rg else "not_configured",
                "last_ingest": _iso(last_hb),
                "pqc_backend": b.info.name, "quantum_safe": b.info.quantum_safe,
            }

        if path == "/api/advisor":
            return migration_advice(db.query(LanDevice).all())

        if path == "/api/pqc/backend":
            from pqc.backend import available_backends, get_backend

            b = get_backend()
            return {"active": b.info.name, "kem_alg": b.info.kem_alg, "sig_alg": b.info.sig_alg,
                    "quantum_safe": b.info.quantum_safe, "note": b.info.note,
                    "available": available_backends()}

        raise ValueError(f"Unknown GET path: {path}")
    finally:
        db.close()


def get_report(fmt: str):
    _ensure()
    db = SessionLocal()
    try:
        content, is_binary = render_report(fmt, db.query(LanDevice).all())
        return content, is_binary
    finally:
        db.close()


def post(path: str, body: dict):
    _ensure()
    db = SessionLocal()
    try:
        if path == "/api/tokens":
            row, raw = create_connector_token(db, body.get("name", "LAN Connector"),
                                              body.get("org_name", "Default Org"))
            return {"id": row.id, "name": row.name, "token": raw,
                    "token_prefix": row.token_prefix,
                    "message": "Store this token now - it is shown only once."}

        if path == "/api/wrapper":
            status_map = {"apply": "wrapped", "remove": "none"}
            new_status = status_map.get(body.get("action"))
            if not new_status:
                raise ValueError("action must be 'apply' or 'remove'")
            updated = 0
            for dev in db.query(LanDevice).filter(LanDevice.id.in_(body.get("device_ids", []))).all():
                dev.wrap_status = new_status
                updated += 1
            db.commit()
            return {"updated": updated, "wrap_status": new_status}

        if path == "/api/remote-gateway":
            rg = db.query(RemoteGateway).first()
            if not rg:
                rg = RemoteGateway(name="B2B Remote Gateway", peer_id=f"rgw_{secrets.token_hex(8)}",
                                   endpoint="pqc-gateway.cloud/b2b", status="active", b2b_enabled=True)
                db.add(rg)
                db.commit()
                db.refresh(rg)
            return {"peer_id": rg.peer_id, "status": rg.status, "b2b_enabled": rg.b2b_enabled}

        if path == "/api/pqc/wrap-demo":
            message = (body.get("message") or "Confidential LAN payload").encode("utf-8")
            if body.get("mode") == "socket":
                from pqc.gateway import loopback_demo

                return {"mode": "socket", **loopback_demo(message)}
            from pqc.tunnel import demonstrate_wrap

            return {"mode": "memory", **demonstrate_wrap(message)}

        if path.startswith("/api/tokens/") and body.get("_method") == "delete":
            tid = int(path.rsplit("/", 1)[-1])
            row = db.query(ConnectorToken).filter(ConnectorToken.id == tid).first()
            if row:
                row.active = False
                db.commit()
            return {"ok": True, "revoked": tid}

        raise ValueError(f"Unknown POST path: {path}")
    finally:
        db.close()
