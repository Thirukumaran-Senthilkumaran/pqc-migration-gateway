"""Anomaly detector — sliding-window failure counter + upgrade trigger."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable, Optional

from ..models import AnomalySeverity, AnomalyType
from .engine import get_policy

logger = logging.getLogger(__name__)


# Per-session sliding windows of (timestamp, type) tuples.
_windows: dict[int, deque[tuple[float, AnomalyType]]] = defaultdict(
    lambda: deque(maxlen=64)
)


class AnomalyDetector:
    """Per-session anomaly counter with auto-upgrade on threshold."""

    def __init__(
        self,
        threshold: int = 3,
        window_sec: int = 30,
        on_upgrade: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> None:
        self.threshold = threshold
        self.window_sec = window_sec
        self.on_upgrade = on_upgrade

    async def record(
        self,
        session_id: int,
        type_: AnomalyType,
        message: str,
        severity: AnomalySeverity = AnomalySeverity.MEDIUM,
    ) -> None:
        now = time.time()
        win = _windows[session_id]
        win.append((now, type_))
        # prune
        while win and now - win[0][0] > self.window_sec:
            win.popleft()

        await get_policy().record_event(
            type_=type_,
            message=message,
            session_id=session_id,
            severity=severity,
        )

        if len(win) >= self.threshold:
            logger.warning(
                "Anomaly threshold hit on session %d (%d events in %ds) — upgrading suite.",
                session_id, len(win), self.window_sec,
            )
            win.clear()
            new_suite = await get_policy().upgrade_session(session_id)
            if new_suite and self.on_upgrade is not None:
                try:
                    await self.on_upgrade(session_id)
                except Exception as e:
                    logger.error("Upgrade callback failed for session %d: %s", session_id, e)

    def configure(self, threshold: int, window_sec: int) -> None:
        self.threshold = threshold
        self.window_sec = window_sec


_detector_singleton: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    global _detector_singleton
    if _detector_singleton is None:
        _detector_singleton = AnomalyDetector()
    return _detector_singleton
