"""Core management routes: health, tokens, devices, wrapper, dashboard, inventory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import create_connector_token
from ..config import get_settings
from ..database import get_db
from ..models import AuditEvent, ConnectorHeartbeat, ConnectorToken, LanDevice
from ..schemas import (
    DashboardStats,
    DeviceOut,
    TokenCreate,
    TokenOut,
    WrapRequest,
)

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
def health():
    from pqc.backend import get_backend

    b = get_backend()
    return {
        "status": "ok",
        "service": "pqc-migration-gateway",
        "version": get_settings().version,
        "pqc_backend": b.info.name,
        "quantum_safe": b.info.quantum_safe,
    }


# --- Tokens ---------------------------------------------------------------- #
@router.post("/tokens", response_model=dict)
def create_token(body: TokenCreate, db: Session = Depends(get_db)):
    row, raw = create_connector_token(db, body.name, body.org_name)
    db.add(AuditEvent(source="ui", action="token_created", detail=row.name))
    db.commit()
    return {
        "id": row.id,
        "name": row.name,
        "token": raw,
        "token_prefix": row.token_prefix,
        "message": "Store this token now - it is shown only once.",
    }


@router.get("/tokens", response_model=list[TokenOut])
def list_tokens(db: Session = Depends(get_db)):
    rows = db.query(ConnectorToken).order_by(ConnectorToken.created_at.desc()).all()
    out = []
    for r in rows:
        cnt = db.query(func.count(LanDevice.id)).filter(LanDevice.token_id == r.id).scalar()
        out.append(
            TokenOut(
                id=r.id, name=r.name, token_prefix=r.token_prefix, org_name=r.org_name,
                active=r.active, created_at=r.created_at, last_seen=r.last_seen,
                device_count=cnt or 0,
            )
        )
    return out


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: int, db: Session = Depends(get_db)):
    row = db.query(ConnectorToken).filter(ConnectorToken.id == token_id).first()
    if not row:
        raise HTTPException(404, "Token not found")
    row.active = False
    db.add(AuditEvent(source="ui", action="token_revoked", detail=row.name))
    db.commit()
    return {"ok": True, "revoked": token_id}


# --- Devices & wrapper ----------------------------------------------------- #
@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(LanDevice).order_by(LanDevice.risk_score.desc()).all()


@router.post("/wrapper")
def wrapper_action(body: WrapRequest, db: Session = Depends(get_db)):
    status_map = {"apply": "wrapped", "remove": "none"}
    new_status = status_map.get(body.action)
    if not new_status:
        raise HTTPException(400, "action must be 'apply' or 'remove'")
    updated = 0
    for dev in db.query(LanDevice).filter(LanDevice.id.in_(body.device_ids)).all():
        dev.wrap_status = new_status
        updated += 1
    db.add(AuditEvent(source="ui", action=f"wrap_{body.action}", detail=f"{updated} devices"))
    db.commit()
    return {"updated": updated, "wrap_status": new_status}


# --- Dashboard ------------------------------------------------------------- #
@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    from pqc.backend import get_backend

    total = db.query(func.count(LanDevice.id)).scalar() or 0
    wrapped = db.query(func.count(LanDevice.id)).filter(LanDevice.wrap_status == "wrapped").scalar() or 0
    t1 = db.query(func.count(LanDevice.id)).filter(LanDevice.priority_tier == "tier-1").scalar() or 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    online = (
        db.query(func.count(ConnectorToken.id)).filter(ConnectorToken.last_seen >= cutoff).scalar() or 0
    )
    last_hb = db.query(func.max(ConnectorHeartbeat.received_at)).scalar()
    from ..models import RemoteGateway

    rg = db.query(RemoteGateway).first()
    b = get_backend()
    return DashboardStats(
        total_devices=total,
        wrapped_devices=wrapped,
        tier1_devices=t1,
        connectors_online=online,
        pqc_coverage_pct=round(100 * wrapped / max(1, total), 1),
        remote_gateway_status=rg.status if rg else "not_configured",
        last_ingest=last_hb,
        pqc_backend=b.info.name,
        quantum_safe=b.info.quantum_safe,
    )
