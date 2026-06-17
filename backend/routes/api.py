"""Token and device management routes."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import create_connector_token
from ..database import get_db
from ..models import ConnectorHeartbeat, ConnectorToken, LanDevice, RemoteGateway
from ..schemas import DashboardStats, DeviceOut, TokenCreate, TokenOut, WrapRequest
from ..services.ai_advisor import migration_advice
from ..services.reports import (
    change_plan_draft,
    devices_to_csv,
    devices_to_json,
    devices_to_pdf,
    hld_summary,
    migration_summary,
    risk_report,
)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "pqc-cloud-gateway"}


@router.post("/tokens", response_model=dict)
def create_token(body: TokenCreate, db: Session = Depends(get_db)):
    row, raw = create_connector_token(db, body.name, body.org_name)
    return {
        "id": row.id,
        "name": row.name,
        "token": raw,
        "token_prefix": row.token_prefix,
        "message": "Store this token securely — it is shown only once.",
    }


@router.get("/tokens", response_model=list[TokenOut])
def list_tokens(db: Session = Depends(get_db)):
    rows = db.query(ConnectorToken).order_by(ConnectorToken.created_at.desc()).all()
    out = []
    for r in rows:
        cnt = db.query(func.count(LanDevice.id)).filter(LanDevice.token_id == r.id).scalar()
        out.append(TokenOut(
            id=r.id, name=r.name, token_prefix=r.token_prefix,
            org_name=r.org_name, active=r.active,
            created_at=r.created_at, last_seen=r.last_seen, device_count=cnt or 0,
        ))
    return out


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(LanDevice).order_by(LanDevice.risk_score.desc()).all()


@router.post("/wrapper")
def wrapper_action(body: WrapRequest, db: Session = Depends(get_db)):
    status_map = {"apply": "wrapped", "remove": "none"}
    new_status = status_map.get(body.action)
    if not new_status:
        raise HTTPException(400, "action must be apply or remove")
    updated = 0
    for dev in db.query(LanDevice).filter(LanDevice.id.in_(body.device_ids)).all():
        dev.wrap_status = new_status
        updated += 1
    db.commit()
    return {"updated": updated, "wrap_status": new_status}


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    total = db.query(func.count(LanDevice.id)).scalar() or 0
    wrapped = db.query(func.count(LanDevice.id)).filter(LanDevice.wrap_status == "wrapped").scalar() or 0
    t1 = db.query(func.count(LanDevice.id)).filter(LanDevice.priority_tier == "tier-1").scalar() or 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    online = (
        db.query(func.count(ConnectorToken.id))
        .filter(ConnectorToken.last_seen >= cutoff)
        .scalar() or 0
    )
    last_hb = db.query(func.max(ConnectorHeartbeat.received_at)).scalar()
    rg = db.query(RemoteGateway).first()
    return DashboardStats(
        total_devices=total,
        wrapped_devices=wrapped,
        tier1_devices=t1,
        connectors_online=online,
        pqc_coverage_pct=round(100 * wrapped / max(1, total), 1),
        remote_gateway_status=rg.status if rg else "not_configured",
        last_ingest=last_hb,
    )


@router.get("/advisor")
def advisor(db: Session = Depends(get_db)):
    devices = db.query(LanDevice).all()
    return migration_advice(devices)


@router.get("/reports/{fmt}")
def download_report(fmt: str, db: Session = Depends(get_db)):
    devices = db.query(LanDevice).all()
    if fmt == "csv":
        return PlainTextResponse(devices_to_csv(devices), media_type="text/csv",
                                   headers={"Content-Disposition": "attachment; filename=inventory.csv"})
    if fmt == "json":
        return PlainTextResponse(devices_to_json(devices), media_type="application/json",
                                   headers={"Content-Disposition": "attachment; filename=inventory.json"})
    if fmt == "pdf":
        return Response(devices_to_pdf(devices), media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=inventory.pdf"})
    if fmt == "migration":
        return PlainTextResponse(migration_summary(devices), media_type="text/plain")
    if fmt == "hld":
        return PlainTextResponse(hld_summary(devices), media_type="text/plain")
    if fmt == "change-plan":
        return PlainTextResponse(change_plan_draft(devices), media_type="text/plain")
    if fmt == "risk":
        return PlainTextResponse(risk_report(devices), media_type="text/plain")
    raise HTTPException(404, "Unknown report format")


@router.post("/remote-gateway")
def ensure_remote_gateway(db: Session = Depends(get_db)):
    import secrets
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
