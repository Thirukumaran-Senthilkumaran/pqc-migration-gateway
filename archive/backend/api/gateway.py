"""Gateway/session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..models import (
    GatewaySession,
    Node,
    SessionStatus,
    TrafficScope,
    WrapMode,
)
from ..network.gateway import get_gateway
from ..policy.engine import get_policy
from ..policy.suite import get_suite
from ..schemas import CreateSessionRequest, GatewaySessionOut

router = APIRouter(prefix="/api/gateway", tags=["gateway"])
settings = get_settings()


@router.get("/sessions", response_model=list[GatewaySessionOut])
async def list_sessions(db: AsyncSession = Depends(get_session)) -> list[GatewaySession]:
    rows = (
        await db.execute(select(GatewaySession).order_by(GatewaySession.started_at.desc()))
    ).scalars().all()
    return list(rows)


@router.post("/sessions", response_model=GatewaySessionOut, status_code=201)
async def create_session(
    req: CreateSessionRequest, db: AsyncSession = Depends(get_session)
) -> GatewaySession:
    node = await db.get(Node, req.node_id)
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

    if req.listen_port is not None:
        port = req.listen_port
    else:
        port = await _next_listen_port(db)

    # Decide the crypto suite:
    #   1) operator override via request, else
    #   2) policy engine choice based on traffic scope.
    if req.crypto_suite:
        try:
            suite_params = get_suite(req.crypto_suite)
            suite_name = suite_params.suite.value
        except (KeyError, ValueError):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unknown crypto suite '{req.crypto_suite}'",
            )
    else:
        suite_enum, _, _, _ = await get_policy().choose_suite(req.scope)
        suite_name = suite_enum.value

    row = GatewaySession(
        node_id=node.id,
        listen_port=port,
        upstream_host=req.upstream_host,
        upstream_port=req.upstream_port,
        kem_alg=settings.kem_algorithm,
        sig_alg=settings.sig_algorithm,
        aead_alg=settings.aead_algorithm,
        hybrid=settings.hybrid_classical,
        crypto_suite=suite_name,
        scope=req.scope,
        status=SessionStatus.NEGOTIATING,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    pqc = node.wrap_mode == WrapMode.WRAP

    try:
        await get_gateway().start_session(
            session_id=row.id,
            node_id=node.id,
            listen_host="0.0.0.0",
            listen_port=row.listen_port,
            upstream_host=row.upstream_host,
            upstream_port=row.upstream_port,
            pqc_to_upstream=pqc,
            suite=suite_name,
        )
    except OSError as e:
        row.status = SessionStatus.FAILED
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Could not bind port: {e}")

    await db.refresh(row)
    return row


@router.delete("/sessions/{session_id}", status_code=204, response_class=Response)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(GatewaySession, session_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await get_gateway().stop_session(session_id)
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


async def _next_listen_port(db: AsyncSession) -> int:
    used = (
        await db.execute(select(GatewaySession.listen_port).where(
            GatewaySession.status != SessionStatus.CLOSED
        ))
    ).scalars().all()
    used_set = set(used)
    p = settings.gateway_listen_base_port
    while p in used_set:
        p += 1
    return p
