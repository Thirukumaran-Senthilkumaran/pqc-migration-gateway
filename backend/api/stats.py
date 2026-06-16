"""Aggregate stats / dashboard endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..migration.planner import overall_progress
from ..models import (
    GatewaySession,
    Node,
    NodeStatus,
    SessionStatus,
    WrapMode,
)
from ..network.monitor import get_monitor
from ..pqc.engine import get_engine
from ..schemas import DashboardStats, TrafficSample

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: AsyncSession = Depends(get_session)) -> DashboardStats:
    total = (await db.execute(select(func.count(Node.id)))).scalar_one()
    online = (
        await db.execute(
            select(func.count(Node.id)).where(Node.status == NodeStatus.ONLINE)
        )
    ).scalar_one()
    wrapped = (
        await db.execute(
            select(func.count(Node.id)).where(Node.wrap_mode == WrapMode.WRAP)
        )
    ).scalar_one()
    native = (
        await db.execute(
            select(func.count(Node.id)).where(Node.wrap_mode == WrapMode.NATIVE)
        )
    ).scalar_one()
    active = (
        await db.execute(
            select(func.count(GatewaySession.id)).where(
                GatewaySession.status == SessionStatus.ESTABLISHED
            )
        )
    ).scalar_one()

    bytes_in = (await db.execute(select(func.coalesce(func.sum(GatewaySession.bytes_in), 0)))).scalar_one()
    bytes_out = (await db.execute(select(func.coalesce(func.sum(GatewaySession.bytes_out), 0)))).scalar_one()

    name, pct = await overall_progress()

    return DashboardStats(
        total_nodes=int(total or 0),
        online_nodes=int(online or 0),
        wrapped_nodes=int(wrapped or 0),
        native_pqc_nodes=int(native or 0),
        active_sessions=int(active or 0),
        total_bytes_protected=int((bytes_in or 0) + (bytes_out or 0)),
        pqc_engine=get_engine().describe(),
        current_stage=name,
        overall_progress_pct=pct,
    )


@router.get("/traffic", response_model=list[TrafficSample])
async def traffic() -> list[TrafficSample]:
    snap = get_monitor().snapshot()
    return [
        TrafficSample(
            ts=datetime.fromtimestamp(s.ts, tz=timezone.utc),
            bytes_in=s.bytes_in,
            bytes_out=s.bytes_out,
            frames=s.frames,
            nic_in=s.nic_in,
            nic_out=s.nic_out,
        )
        for s in snap
    ]
