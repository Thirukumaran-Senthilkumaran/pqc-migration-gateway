"""Direct backend access — used when HTTP to a separate API is unavailable (e.g. Streamlit Cloud)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from backend.auth import create_connector_token
from backend.database import SessionLocal, init_db
from backend.models import ConnectorHeartbeat, ConnectorToken, LanDevice, RemoteGateway
from backend.schemas import DeviceOut, TokenOut
from backend.services.ai_advisor import migration_advice
from backend.services.reports import (
    change_plan_draft,
    devices_to_csv,
    devices_to_json,
    devices_to_pdf,
    hld_summary,
    migration_summary,
    risk_report,
)

_initialized = False


def ensure_db() -> None:
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True


def _json(obj):
    if isinstance(obj, list):
        return [_json(x) for x in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def direct_get(path: str):
    ensure_db()
    db = SessionLocal()
    try:
        if path == "/api/health":
            return {"status": "ok", "service": "pqc-cloud-gateway", "mode": "embedded"}

        if path == "/api/devices":
            rows = db.query(LanDevice).order_by(LanDevice.risk_score.desc()).all()
            return _json([DeviceOut.model_validate(r) for r in rows])

        if path == "/api/tokens":
            rows = db.query(ConnectorToken).order_by(ConnectorToken.created_at.desc()).all()
            out = []
            for r in rows:
                cnt = db.query(func.count(LanDevice.id)).filter(LanDevice.token_id == r.id).scalar()
                out.append(
                    TokenOut(
                        id=r.id,
                        name=r.name,
                        token_prefix=r.token_prefix,
                        org_name=r.org_name,
                        active=r.active,
                        created_at=r.created_at,
                        last_seen=r.last_seen,
                        device_count=cnt or 0,
                    )
                )
            return _json(out)

        if path == "/api/dashboard":
            total = db.query(func.count(LanDevice.id)).scalar() or 0
            wrapped = (
                db.query(func.count(LanDevice.id)).filter(LanDevice.wrap_status == "wrapped").scalar() or 0
            )
            t1 = (
                db.query(func.count(LanDevice.id)).filter(LanDevice.priority_tier == "tier-1").scalar() or 0
            )
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            online = (
                db.query(func.count(ConnectorToken.id)).filter(ConnectorToken.last_seen >= cutoff).scalar() or 0
            )
            last_hb = db.query(func.max(ConnectorHeartbeat.received_at)).scalar()
            rg = db.query(RemoteGateway).first()
            return {
                "total_devices": total,
                "wrapped_devices": wrapped,
                "tier1_devices": t1,
                "connectors_online": online,
                "pqc_coverage_pct": round(100 * wrapped / max(1, total), 1),
                "remote_gateway_status": rg.status if rg else "not_configured",
                "last_ingest": last_hb.isoformat() if last_hb else None,
            }

        if path == "/api/advisor":
            devices = db.query(LanDevice).all()
            return migration_advice(devices)

        if path.startswith("/api/reports/"):
            fmt = path.split("/")[-1]
            devices = db.query(LanDevice).all()
            if fmt == "csv":
                return {"content": devices_to_csv(devices), "binary": False}
            if fmt == "json":
                return {"content": devices_to_json(devices), "binary": False}
            if fmt == "pdf":
                return {"content": devices_to_pdf(devices), "binary": True}
            if fmt == "migration":
                return {"content": migration_summary(devices), "binary": False}
            if fmt == "hld":
                return {"content": hld_summary(devices), "binary": False}
            if fmt == "change-plan":
                return {"content": change_plan_draft(devices), "binary": False}
            if fmt == "risk":
                return {"content": risk_report(devices), "binary": False}
            raise ValueError(f"Unknown report format: {fmt}")

        raise ValueError(f"Unknown GET path: {path}")
    finally:
        db.close()


def direct_post(path: str, body: dict):
    ensure_db()
    db = SessionLocal()
    try:
        if path == "/api/tokens":
            row, raw = create_connector_token(db, body["name"], body.get("org_name", "Default Org"))
            return {
                "id": row.id,
                "name": row.name,
                "token": raw,
                "token_prefix": row.token_prefix,
                "message": "Store this token securely — it is shown only once.",
            }

        if path == "/api/wrapper":
            status_map = {"apply": "wrapped", "remove": "none"}
            new_status = status_map.get(body.get("action"))
            if not new_status:
                raise ValueError("action must be apply or remove")
            updated = 0
            for dev in db.query(LanDevice).filter(LanDevice.id.in_(body.get("device_ids", []))).all():
                dev.wrap_status = new_status
                updated += 1
            db.commit()
            return {"updated": updated, "wrap_status": new_status}

        if path == "/api/remote-gateway":
            rg = db.query(RemoteGateway).first()
            if not rg:
                rg = RemoteGateway(
                    name="B2B Remote Gateway",
                    peer_id=f"rgw_{secrets.token_hex(8)}",
                    endpoint="pqc-gateway.cloud/b2b",
                    status="active",
                    b2b_enabled=True,
                )
                db.add(rg)
                db.commit()
            return {"peer_id": rg.peer_id, "status": rg.status, "b2b_enabled": rg.b2b_enabled}

        raise ValueError(f"Unknown POST path: {path}")
    finally:
        db.close()
