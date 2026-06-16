"""ORM models for the gateway."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _str_enum(enum_cls: type[enum.Enum], **kwargs) -> Enum:
    """Store/read str-enum *values* (e.g. 'lan-wan'), not member names (LAN_WAN).

    Without this, SQLAlchemy defaults to names while our SQLite migrations and
    API layer use the human-readable value strings — causing LookupError on read.
    """
    return Enum(
        enum_cls,
        values_callable=lambda obj: [member.value for member in obj],
        native_enum=False,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #
class NodeStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"


class PriorityTier(str, enum.Enum):
    TIER_1 = "tier-1"  # critical, migrate first
    TIER_2 = "tier-2"
    TIER_3 = "tier-3"  # low-priority / IoT, gateway-only OK


class WrapMode(str, enum.Enum):
    """How the gateway treats this node."""

    OFF = "off"             # no wrapping (passthrough)
    MONITOR = "monitor"     # observe only
    WRAP = "wrap"           # all egress wrapped in PQC tunnel
    NATIVE = "native"       # node speaks PQC itself, gateway out of path


class StageStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class SessionStatus(str, enum.Enum):
    NEGOTIATING = "negotiating"
    ESTABLISHED = "established"
    REKEYING = "rekeying"
    CLOSED = "closed"
    FAILED = "failed"


class TrafficScope(str, enum.Enum):
    LAN_LAN = "lan-lan"     # both endpoints on the LAN
    LAN_WAN = "lan-wan"     # crossing the gateway boundary
    ANY = "any"


class AnomalyType(str, enum.Enum):
    AEAD_FAILURE = "aead_failure"
    REPLAY_DETECTED = "replay_detected"
    HANDSHAKE_FAILURE = "handshake_failure"
    SIZE_ANOMALY = "size_anomaly"
    POLICY_UPGRADE = "policy_upgrade"


class AnomalySeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #
class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(String(17), unique=True, index=True)
    ip: Mapped[str] = mapped_column(String(45), index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_guess: Mapped[str | None] = mapped_column(String(128), nullable=True)
    open_ports: Mapped[str | None] = mapped_column(Text, nullable=True)  # csv
    services: Mapped[str | None] = mapped_column(Text, nullable=True)    # csv

    # classification
    pqc_ready: Mapped[float] = mapped_column(Float, default=0.0)         # 0–10
    criticality: Mapped[float] = mapped_column(Float, default=5.0)       # 0–10
    risk: Mapped[float] = mapped_column(Float, default=5.0)              # 0–10
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_tier: Mapped[PriorityTier] = mapped_column(
        _str_enum(PriorityTier), default=PriorityTier.TIER_3
    )

    # operational
    wrap_mode: Mapped[WrapMode] = mapped_column(
        _str_enum(WrapMode), default=WrapMode.MONITOR
    )
    status: Mapped[NodeStatus] = mapped_column(
        _str_enum(NodeStatus), default=NodeStatus.UNKNOWN
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list["GatewaySession"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class GatewaySession(Base):
    __tablename__ = "gateway_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    listen_port: Mapped[int] = mapped_column(Integer)
    upstream_host: Mapped[str] = mapped_column(String(255))
    upstream_port: Mapped[int] = mapped_column(Integer)

    kem_alg: Mapped[str] = mapped_column(String(64), default="ML-KEM-768")
    sig_alg: Mapped[str] = mapped_column(String(64), default="ML-DSA-65")
    aead_alg: Mapped[str] = mapped_column(String(64), default="AES-256-GCM")
    hybrid: Mapped[bool] = mapped_column(Boolean, default=True)

    crypto_suite: Mapped[str] = mapped_column(String(32), default="pqc-full")
    scope: Mapped[TrafficScope] = mapped_column(
        _str_enum(TrafficScope), default=TrafficScope.LAN_WAN
    )
    suite_history: Mapped[str | None] = mapped_column(Text, nullable=True)  # csv

    bytes_in: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_out: Mapped[int] = mapped_column(BigInteger, default=0)
    frames_in: Mapped[int] = mapped_column(BigInteger, default=0)
    frames_out: Mapped[int] = mapped_column(BigInteger, default=0)

    status: Mapped[SessionStatus] = mapped_column(
        _str_enum(SessionStatus), default=SessionStatus.NEGOTIATING
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_rekey_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    node: Mapped[Node] = relationship(back_populates="sessions")


class MigrationStage(Base):
    __tablename__ = "migration_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    ordinal: Mapped[int] = mapped_column(Integer)
    target_tier: Mapped[PriorityTier | None] = mapped_column(
        _str_enum(PriorityTier), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[StageStatus] = mapped_column(
        _str_enum(StageStatus), default=StageStatus.PLANNED
    )
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tasks: Mapped[list["MigrationTask"]] = relationship(
        back_populates="stage", cascade="all, delete-orphan"
    )


class MigrationTask(Base):
    __tablename__ = "migration_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("migration_stages.id", ondelete="CASCADE")
    )
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(128))
    status: Mapped[StageStatus] = mapped_column(
        _str_enum(StageStatus), default=StageStatus.PLANNED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    stage: Mapped[MigrationStage] = relationship(back_populates="tasks")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    source: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)


class PolicyRule(Base):
    """Adaptive crypto policy rule.

    A rule maps a traffic *scope* (and optional priority tier filter) to an
    initial crypto suite and an upgrade target if anomalies are detected.
    """

    __tablename__ = "policy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    scope: Mapped[TrafficScope] = mapped_column(
        _str_enum(TrafficScope), default=TrafficScope.ANY
    )
    tier_filter: Mapped[str | None] = mapped_column(String(32), nullable=True)
    initial_suite: Mapped[str] = mapped_column(String(32), default="pqc-full")
    upgrade_suite: Mapped[str | None] = mapped_column(String(32), nullable=True)

    anomaly_threshold: Mapped[int] = mapped_column(Integer, default=3)
    anomaly_window_sec: Mapped[int] = mapped_column(Integer, default=30)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("gateway_sessions.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[AnomalyType] = mapped_column(_str_enum(AnomalyType))
    severity: Mapped[AnomalySeverity] = mapped_column(
        _str_enum(AnomalySeverity), default=AnomalySeverity.MEDIUM
    )
    message: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_suite: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_suite: Mapped[str | None] = mapped_column(String(32), nullable=True)


class GatewayKey(Base):
    """Long-term gateway identity (ML-DSA keypair, etc.)."""

    __tablename__ = "gateway_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(128), unique=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[bytes] = mapped_column()  # blob
    secret_key: Mapped[bytes] = mapped_column()  # blob (encrypted at rest in prod)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
