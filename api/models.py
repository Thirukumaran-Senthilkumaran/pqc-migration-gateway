"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectorToken(Base):
    __tablename__ = "connector_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(16))
    org_name: Mapped[str] = mapped_column(String(128), default="Default Org")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    devices: Mapped[list["LanDevice"]] = relationship(
        back_populates="token", cascade="all, delete-orphan"
    )
    heartbeats: Mapped[list["ConnectorHeartbeat"]] = relationship(
        back_populates="token", cascade="all, delete-orphan"
    )


class LanDevice(Base):
    __tablename__ = "lan_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("connector_tokens.id"))
    ip: Mapped[str] = mapped_column(String(45), index=True)
    mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tls_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cert_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weak_protocol: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pqc_candidate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=5.0)
    priority_tier: Mapped[str] = mapped_column(String(16), default="tier-3")
    wrap_status: Mapped[str] = mapped_column(String(16), default="none")
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    token: Mapped[ConnectorToken] = relationship(back_populates="devices")


class ConnectorHeartbeat(Base):
    __tablename__ = "connector_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("connector_tokens.id"))
    subnet: Mapped[str | None] = mapped_column(String(64), nullable=True)
    devices_found: Mapped[int] = mapped_column(Integer, default=0)
    connector_version: Mapped[str] = mapped_column(String(16), default="2.0")
    status: Mapped[str] = mapped_column(String(32), default="online")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    token: Mapped[ConnectorToken] = relationship(back_populates="heartbeats")


class RemoteGateway(Base):
    __tablename__ = "remote_gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    peer_id: Mapped[str] = mapped_column(String(64), unique=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="standby")
    b2b_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
