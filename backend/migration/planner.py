"""Stage-by-stage migration planner.

Generates a 6-stage default plan that operators can edit:

    Stage 0 — Discovery        : inventory all LAN nodes
    Stage 1 — Wrap-All         : route all egress through the PQC gateway
    Stage 2 — Native PQC T-1   : upgrade tier-1 (critical) nodes natively
    Stage 3 — Native PQC T-2   : upgrade tier-2 nodes
    Stage 4 — Native PQC T-3   : upgrade or retire tier-3 nodes
    Stage 5 — Gateway Standby  : gateway covers only residual legacy

Tasks are derived per-node from the classifier output.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..database import session_scope
from ..models import (
    MigrationStage,
    MigrationTask,
    Node,
    PriorityTier,
    StageStatus,
    WrapMode,
)

logger = logging.getLogger(__name__)


DEFAULT_STAGES: list[dict] = [
    {
        "ordinal": 0, "name": "Discovery",
        "description": "Inventory and classify every LAN node.",
        "target_tier": None,
    },
    {
        "ordinal": 1, "name": "Wrap-All",
        "description": "Route all egress through the PQC tunnel; no endpoint changes.",
        "target_tier": None,
    },
    {
        "ordinal": 2, "name": "Native PQC — Tier 1",
        "description": "Upgrade critical / high-risk nodes to native PQC.",
        "target_tier": PriorityTier.TIER_1,
    },
    {
        "ordinal": 3, "name": "Native PQC — Tier 2",
        "description": "Upgrade standard endpoints to native PQC.",
        "target_tier": PriorityTier.TIER_2,
    },
    {
        "ordinal": 4, "name": "Native PQC — Tier 3",
        "description": "Upgrade or retire IoT / low-priority nodes.",
        "target_tier": PriorityTier.TIER_3,
    },
    {
        "ordinal": 5, "name": "Gateway Standby",
        "description": "Gateway only covers residual legacy devices.",
        "target_tier": None,
    },
]


# --------------------------------------------------------------------------- #
# bootstrap
# --------------------------------------------------------------------------- #
async def ensure_default_plan() -> None:
    async with session_scope() as db:
        rows = (await db.execute(select(MigrationStage))).scalars().all()
        if rows:
            return
        for stage in DEFAULT_STAGES:
            db.add(MigrationStage(**stage))
        # mark Stage 0 in progress
        # need to flush so we can find it
        await db.flush()
        s0 = (
            await db.execute(select(MigrationStage).where(MigrationStage.ordinal == 0))
        ).scalar_one_or_none()
        if s0:
            s0.status = StageStatus.IN_PROGRESS
            s0.started_at = datetime.now(timezone.utc)
    logger.info("Default migration plan created.")


# --------------------------------------------------------------------------- #
# rebuild tasks
# --------------------------------------------------------------------------- #
async def rebuild_tasks() -> int:
    """Recreate per-node tasks for each stage based on current classification."""
    n = 0
    async with session_scope() as db:
        stages = (await db.execute(select(MigrationStage))).scalars().all()
        nodes = (await db.execute(select(Node))).scalars().all()

        # remove existing tasks
        for s in stages:
            for t in s.tasks:
                await db.delete(t)
        await db.flush()

        for stage in stages:
            if stage.ordinal == 0:
                # discovery — one task per node ("inventoried")
                for node in nodes:
                    db.add(
                        MigrationTask(
                            stage_id=stage.id,
                            node_id=node.id,
                            action="inventory",
                            status=StageStatus.COMPLETED if node.id else StageStatus.PLANNED,
                        )
                    )
                    n += 1
            elif stage.ordinal == 1:
                # wrap-all — one task per node ("enable wrap")
                for node in nodes:
                    db.add(
                        MigrationTask(
                            stage_id=stage.id,
                            node_id=node.id,
                            action="enable-wrap",
                            status=(
                                StageStatus.COMPLETED
                                if node.wrap_mode == WrapMode.WRAP
                                else StageStatus.PLANNED
                            ),
                        )
                    )
                    n += 1
            elif stage.ordinal in (2, 3, 4) and stage.target_tier:
                tier_nodes = [n_ for n_ in nodes if n_.priority_tier == stage.target_tier]
                for node in tier_nodes:
                    db.add(
                        MigrationTask(
                            stage_id=stage.id,
                            node_id=node.id,
                            action="upgrade-native-pqc",
                            status=(
                                StageStatus.COMPLETED
                                if node.wrap_mode == WrapMode.NATIVE
                                else StageStatus.PLANNED
                            ),
                        )
                    )
                    n += 1
            elif stage.ordinal == 5:
                residual = [
                    n_ for n_ in nodes
                    if n_.wrap_mode in (WrapMode.WRAP, WrapMode.MONITOR)
                ]
                for node in residual:
                    db.add(
                        MigrationTask(
                            stage_id=stage.id,
                            node_id=node.id,
                            action="retire-or-keep-wrapped",
                            status=StageStatus.PLANNED,
                        )
                    )
                    n += 1

        # progress %
        await db.flush()
        for stage in stages:
            tasks = list(stage.tasks)
            if not tasks:
                stage.progress_pct = 0.0
                continue
            done = sum(1 for t in tasks if t.status == StageStatus.COMPLETED)
            stage.progress_pct = round(100.0 * done / len(tasks), 2)
            if stage.progress_pct >= 100.0:
                stage.status = StageStatus.COMPLETED
                stage.completed_at = stage.completed_at or datetime.now(timezone.utc)
            elif stage.progress_pct > 0:
                stage.status = StageStatus.IN_PROGRESS
                stage.started_at = stage.started_at or datetime.now(timezone.utc)

    logger.info("Rebuilt %d migration tasks.", n)
    return n


# --------------------------------------------------------------------------- #
# overall progress + current stage
# --------------------------------------------------------------------------- #
async def overall_progress() -> tuple[str | None, float]:
    async with session_scope() as db:
        stages = (await db.execute(select(MigrationStage).order_by(MigrationStage.ordinal))).scalars().all()
        if not stages:
            return None, 0.0
        current = next(
            (s for s in stages if s.status != StageStatus.COMPLETED),
            stages[-1],
        )
        avg = sum(s.progress_pct for s in stages) / max(1, len(stages))
        return current.name, round(avg, 2)
