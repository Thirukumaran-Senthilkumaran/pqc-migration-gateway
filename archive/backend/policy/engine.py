"""Policy engine — chooses a crypto suite per session, handles upgrades."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from ..database import session_scope
from ..models import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    GatewaySession,
    PolicyRule,
    SessionStatus,
    TrafficScope,
)
from .suite import CryptoSuite, SUITES

logger = logging.getLogger(__name__)


DEFAULT_RULES = [
    {
        "name": "LAN ↔ LAN — fast classical, upgrade to PQC on anomaly",
        "scope": TrafficScope.LAN_LAN,
        "initial_suite": CryptoSuite.CLASSICAL.value,
        "upgrade_suite": CryptoSuite.PQC_COMPRESSED.value,
        "anomaly_threshold": 3,
        "anomaly_window_sec": 30,
        "priority": 10,
        "notes": "Trusted-segment performance path. Snaps to compressed PQC the moment anything looks wrong.",
    },
    {
        "name": "LAN ↔ WAN — full PQC always",
        "scope": TrafficScope.LAN_WAN,
        "initial_suite": CryptoSuite.PQC_FULL.value,
        "upgrade_suite": None,
        "anomaly_threshold": 3,
        "anomaly_window_sec": 30,
        "priority": 20,
        "notes": "Crossing the gateway boundary — never start below full PQC.",
    },
    {
        "name": "Default — compressed PQC",
        "scope": TrafficScope.ANY,
        "initial_suite": CryptoSuite.PQC_COMPRESSED.value,
        "upgrade_suite": CryptoSuite.PQC_FULL.value,
        "anomaly_threshold": 5,
        "anomaly_window_sec": 60,
        "priority": 100,
        "notes": "Catch-all fallback when no scope-specific rule matches.",
    },
]


# --------------------------------------------------------------------------- #
class PolicyEngine:
    async def ensure_defaults(self) -> None:
        async with session_scope() as db:
            existing = (await db.execute(select(PolicyRule))).scalars().all()
            if existing:
                return
            for r in DEFAULT_RULES:
                db.add(PolicyRule(**r))
        logger.info("Default policy rules created.")

    async def choose_suite(self, scope: TrafficScope) -> tuple[CryptoSuite, Optional[CryptoSuite], int, int]:
        """Return (initial_suite, upgrade_suite, threshold, window_sec)."""
        async with session_scope() as db:
            rules = (
                await db.execute(
                    select(PolicyRule)
                    .where(PolicyRule.enabled == True)  # noqa: E712
                    .order_by(PolicyRule.priority.asc())
                )
            ).scalars().all()
        for r in rules:
            if r.scope == scope or r.scope == TrafficScope.ANY:
                return (
                    CryptoSuite(r.initial_suite),
                    CryptoSuite(r.upgrade_suite) if r.upgrade_suite else None,
                    r.anomaly_threshold,
                    r.anomaly_window_sec,
                )
        # hard default
        return CryptoSuite.PQC_FULL, None, 3, 30

    async def record_event(
        self,
        type_: AnomalyType,
        message: str,
        session_id: Optional[int] = None,
        severity: AnomalySeverity = AnomalySeverity.MEDIUM,
        from_suite: Optional[str] = None,
        to_suite: Optional[str] = None,
        action_taken: Optional[str] = None,
    ) -> int:
        async with session_scope() as db:
            ev = AnomalyEvent(
                ts=datetime.now(timezone.utc),
                session_id=session_id,
                type=type_,
                severity=severity,
                message=message,
                from_suite=from_suite,
                to_suite=to_suite,
                action_taken=action_taken,
            )
            db.add(ev)
            await db.flush()
            evid = ev.id
        logger.info("Anomaly: %s (sev=%s) %s", type_.value, severity.value, message)
        return evid

    async def upgrade_session(self, session_id: int) -> Optional[CryptoSuite]:
        """Mark a session for suite upgrade based on its policy rule."""
        async with session_scope() as db:
            sess: GatewaySession | None = await db.get(GatewaySession, session_id)
            if not sess:
                return None
            current = CryptoSuite(sess.crypto_suite)
            _, upgrade_to, _, _ = await self.choose_suite(sess.scope)
            if upgrade_to is None or upgrade_to == current:
                return None
            history = (sess.suite_history or current.value).split(",") if sess.suite_history else [current.value]
            history.append(upgrade_to.value)
            sess.suite_history = ",".join(history)
            sess.crypto_suite = upgrade_to.value
            sess.status = SessionStatus.REKEYING
            sess.last_rekey_at = datetime.now(timezone.utc)
        await self.record_event(
            type_=AnomalyType.POLICY_UPGRADE,
            severity=AnomalySeverity.HIGH,
            message=f"Auto-upgrade {current.value} → {upgrade_to.value} on session {session_id}",
            session_id=session_id,
            from_suite=current.value,
            to_suite=upgrade_to.value,
            action_taken="suite_upgrade",
        )
        return upgrade_to


_engine_singleton: PolicyEngine | None = None


def get_policy() -> PolicyEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = PolicyEngine()
    return _engine_singleton
