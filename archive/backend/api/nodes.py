"""Node CRUD + classification endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Node, NodeStatus, WrapMode
from ..network.classifier import classify_node, reclassify_all
from ..network.discovery import get_discovery
from ..schemas import (
    DiscoveryStatus,
    DiscoveryTrigger,
    NodeOut,
    NodeUpdate,
)

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeOut])
async def list_nodes(db: AsyncSession = Depends(get_session)) -> list[Node]:
    rows = (await db.execute(select(Node).order_by(Node.priority_score.desc()))).scalars().all()
    return list(rows)


@router.get("/{node_id}", response_model=NodeOut)
async def get_node(node_id: int, db: AsyncSession = Depends(get_session)) -> Node:
    row = await db.get(Node, node_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")
    return row


@router.patch("/{node_id}", response_model=NodeOut)
async def update_node(
    node_id: int,
    payload: NodeUpdate,
    db: AsyncSession = Depends(get_session),
) -> Node:
    row = await db.get(Node, node_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    classify_node(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_node(node_id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(Node, node_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reclassify", response_model=dict)
async def reclassify() -> dict:
    n = await reclassify_all()
    return {"reclassified": n}


# --------------------------------------------------------------------------- #
# discovery sub-routes (mounted under /api/nodes for UI convenience)
# --------------------------------------------------------------------------- #
@router.get("/discovery/status", response_model=DiscoveryStatus)
async def discovery_status() -> DiscoveryStatus:
    s = await get_discovery().status()
    return DiscoveryStatus(**s)


@router.post("/discovery/trigger", response_model=dict)
async def discovery_trigger(payload: DiscoveryTrigger) -> dict:
    found = await get_discovery().trigger_now(payload.subnet)
    return {"found": found}
