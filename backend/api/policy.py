"""Crypto policy API: rules CRUD + anomaly feed + suite reference."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import (
    AnomalyEvent,
    AnomalySeverity,
    PolicyRule,
)
from ..policy.anomaly import get_detector
from ..policy.suite import SUITES, get_suite
from ..schemas import (
    AnomalyEventOut,
    PolicyRuleCreate,
    PolicyRuleOut,
    PolicyRuleUpdate,
    SuiteOut,
    TriggerAnomalyRequest,
)

router = APIRouter(prefix="/api/policy", tags=["policy"])


# --------------------------------------------------------------------------- #
# Suite reference
# --------------------------------------------------------------------------- #
@router.get("/suites", response_model=list[SuiteOut])
async def list_suites() -> list[SuiteOut]:
    return [
        SuiteOut(
            suite=p.suite.value,
            label=p.label,
            pqc=p.pqc,
            use_kem=p.use_kem,
            use_x25519=p.use_x25519,
            use_signature=p.use_signature,
            aead_key_len=p.aead_key_len,
            handshake_bytes=p.handshake_bytes,
            description=p.description,
            quantum_safe=p.quantum_safe,
        )
        for p in SUITES.values()
    ]


# --------------------------------------------------------------------------- #
# Rules CRUD
# --------------------------------------------------------------------------- #
@router.get("/rules", response_model=list[PolicyRuleOut])
async def list_rules(db: AsyncSession = Depends(get_session)) -> list[PolicyRule]:
    rows = (
        await db.execute(
            select(PolicyRule).order_by(PolicyRule.priority.asc(), PolicyRule.id.asc())
        )
    ).scalars().all()
    return list(rows)


@router.post("/rules", response_model=PolicyRuleOut, status_code=201)
async def create_rule(
    payload: PolicyRuleCreate, db: AsyncSession = Depends(get_session)
) -> PolicyRule:
    # validate suites exist
    try:
        get_suite(payload.initial_suite)
        if payload.upgrade_suite:
            get_suite(payload.upgrade_suite)
    except (KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown suite: {e}")

    row = PolicyRule(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/rules/{rule_id}", response_model=PolicyRuleOut)
async def update_rule(
    rule_id: int,
    payload: PolicyRuleUpdate,
    db: AsyncSession = Depends(get_session),
) -> PolicyRule:
    row = await db.get(PolicyRule, rule_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_session)):
    from fastapi import Response
    row = await db.get(PolicyRule, rule_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Anomaly feed
# --------------------------------------------------------------------------- #
@router.get("/anomalies", response_model=list[AnomalyEventOut])
async def list_anomalies(
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
) -> list[AnomalyEvent]:
    limit = max(1, min(limit, 1000))
    rows = (
        await db.execute(
            select(AnomalyEvent).order_by(desc(AnomalyEvent.ts)).limit(limit)
        )
    ).scalars().all()
    return list(rows)


@router.post("/anomalies/inject", response_model=AnomalyEventOut)
async def inject_anomaly(payload: TriggerAnomalyRequest) -> AnomalyEvent:
    """Inject a synthetic anomaly — useful for demonstrating auto-upgrade."""
    await get_detector().record(
        session_id=payload.session_id,
        type_=payload.type,
        severity=AnomalySeverity.HIGH,
        message=f"[demo-injected] {payload.message}",
    )
    # return the latest event for this session
    from ..database import session_scope as _scope
    async with _scope() as db:
        row = (
            await db.execute(
                select(AnomalyEvent)
                .where(AnomalyEvent.session_id == payload.session_id)
                .order_by(desc(AnomalyEvent.ts))
                .limit(1)
            )
        ).scalar_one()
    return row
