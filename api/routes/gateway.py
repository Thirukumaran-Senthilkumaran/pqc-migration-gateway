"""PQC engine demos and the B2B remote gateway."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, RemoteGateway
from ..schemas import WrapDemoRequest

router = APIRouter(prefix="/api", tags=["gateway"])


@router.get("/pqc/backend")
def pqc_backend():
    from pqc.backend import available_backends, get_backend

    b = get_backend()
    return {
        "active": b.info.name,
        "kem_alg": b.info.kem_alg,
        "sig_alg": b.info.sig_alg,
        "quantum_safe": b.info.quantum_safe,
        "note": b.info.note,
        "available": available_backends(),
    }


@router.post("/pqc/wrap-demo")
def wrap_demo(body: WrapDemoRequest, db: Session = Depends(get_db)):
    """Run a real PQC tunnel (in-memory or via sockets) and return a transcript."""
    message = (body.message or "Confidential LAN payload").encode("utf-8")
    if body.mode == "socket":
        from pqc.gateway import loopback_demo

        result = loopback_demo(message)
        db.add(AuditEvent(source="ui", action="wrap_demo_socket", detail=f"ok={result['ok']}"))
        db.commit()
        return {"mode": "socket", **result}

    from pqc.tunnel import demonstrate_wrap

    result = demonstrate_wrap(message)
    db.add(AuditEvent(source="ui", action="wrap_demo_memory", detail=f"verified={result['verified']}"))
    db.commit()
    return {"mode": "memory", **result}


@router.post("/remote-gateway")
def ensure_remote_gateway(db: Session = Depends(get_db)):
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
        db.refresh(rg)
    return {"peer_id": rg.peer_id, "status": rg.status, "b2b_enabled": rg.b2b_enabled}
