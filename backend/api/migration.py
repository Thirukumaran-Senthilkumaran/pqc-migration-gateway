"""Migration plan endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..migration.planner import (
    ensure_default_plan,
    overall_progress,
    rebuild_tasks,
)
from ..models import (
    MigrationStage,
    MigrationTask,
    StageStatus,
)
from ..schemas import (
    MigrationPlan,
    MigrationStageOut,
    MigrationTaskOut,
)

router = APIRouter(prefix="/api/migration", tags=["migration"])


@router.get("/plan", response_model=MigrationPlan)
async def get_plan(db: AsyncSession = Depends(get_session)) -> MigrationPlan:
    stages = (
        await db.execute(select(MigrationStage).order_by(MigrationStage.ordinal))
    ).scalars().all()
    tasks = (await db.execute(select(MigrationTask))).scalars().all()
    return MigrationPlan(
        stages=[MigrationStageOut.model_validate(s) for s in stages],
        tasks=[MigrationTaskOut.model_validate(t) for t in tasks],
    )


@router.post("/plan/rebuild", response_model=dict)
async def rebuild() -> dict:
    await ensure_default_plan()
    n = await rebuild_tasks()
    name, pct = await overall_progress()
    return {"tasks": n, "current_stage": name, "overall_progress_pct": pct}


@router.patch("/stages/{stage_id}", response_model=MigrationStageOut)
async def update_stage(
    stage_id: int,
    new_status: StageStatus,
    db: AsyncSession = Depends(get_session),
) -> MigrationStage:
    row = await db.get(MigrationStage, stage_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
    row.status = new_status
    if new_status == StageStatus.IN_PROGRESS and not row.started_at:
        row.started_at = datetime.now(timezone.utc)
    if new_status == StageStatus.COMPLETED:
        row.completed_at = datetime.now(timezone.utc)
        row.progress_pct = 100.0
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/tasks/{task_id}", response_model=MigrationTaskOut)
async def update_task(
    task_id: int,
    new_status: StageStatus,
    db: AsyncSession = Depends(get_session),
) -> MigrationTask:
    row = await db.get(MigrationTask, task_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    row.status = new_status
    await db.commit()
    await db.refresh(row)
    return row
