"""POST /api/ingest - LAN connector upload endpoint (Bearer authenticated)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import verify_connector_token
from ..database import get_db
from ..models import AuditEvent, ConnectorHeartbeat, ConnectorToken, LanDevice
from ..schemas import IngestPayload
from ..services.classifier import classify_device

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest")
def ingest(
    payload: IngestPayload,
    token: ConnectorToken = Depends(verify_connector_token),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    token.last_seen = now

    if payload.type == "heartbeat":
        db.add(
            ConnectorHeartbeat(
                token_id=token.id,
                subnet=payload.subnet,
                devices_found=0,
                connector_version=payload.connector_version,
                status="online",
            )
        )
        db.commit()
        return {"ok": True, "type": "heartbeat", "received": now.isoformat()}

    upserted = 0
    for item in payload.devices:
        row = (
            db.query(LanDevice)
            .filter(LanDevice.token_id == token.id, LanDevice.ip == item.ip)
            .first()
        )
        if row is None:
            row = LanDevice(token_id=token.id, ip=item.ip)
            db.add(row)
        for field in (
            "mac", "hostname", "service", "port", "tls_version",
            "cert_type", "weak_protocol", "vendor",
        ):
            val = getattr(item, field, None)
            if val is not None:
                setattr(row, field, val)
        if item.risk_score is not None:
            row.risk_score = item.risk_score
        row.last_seen = now
        classify_device(row)
        upserted += 1

    db.add(
        ConnectorHeartbeat(
            token_id=token.id,
            subnet=payload.subnet,
            devices_found=upserted,
            connector_version=payload.connector_version,
            status="scan_complete",
        )
    )
    db.add(AuditEvent(source="connector", action=f"ingest_{payload.type}", detail=f"{upserted} devices"))
    db.commit()
    return {"ok": True, "type": payload.type, "upserted": upserted}
