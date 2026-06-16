"""WebSocket endpoint — pushes real-time traffic samples to the dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..network.monitor import get_monitor
from ..pqc.engine import get_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    monitor = get_monitor()
    queue = monitor.subscribe()

    # send hello
    try:
        await ws.send_text(
            json.dumps(
                {"type": "hello", "engine": get_engine().describe(),
                 "ts": datetime.now(timezone.utc).isoformat()}
            )
        )

        def _serialize(s) -> dict:
            return {
                "ts": s.ts,
                "bytes_in": s.bytes_in,
                "bytes_out": s.bytes_out,
                "frames": s.frames,
                "nic_in": s.nic_in,
                "nic_out": s.nic_out,
            }

        # initial snapshot
        snap = monitor.snapshot()
        await ws.send_text(
            json.dumps(
                {
                    "type": "traffic.snapshot",
                    "samples": [_serialize(s) for s in snap],
                }
            )
        )

        # stream
        while True:
            try:
                sample = await asyncio.wait_for(queue.get(), timeout=15)
                await ws.send_text(
                    json.dumps({"type": "traffic.sample", **_serialize(sample)})
                )
            except asyncio.TimeoutError:
                # heartbeat
                await ws.send_text(
                    json.dumps({"type": "ping",
                                "ts": datetime.now(timezone.utc).isoformat()})
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WS closed: %s", e)
    finally:
        monitor.unsubscribe(queue)
