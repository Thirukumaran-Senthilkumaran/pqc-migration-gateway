"""Pydantic schemas (API I/O contracts)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AnomalySeverity,
    AnomalyType,
    NodeStatus,
    PriorityTier,
    SessionStatus,
    StageStatus,
    TrafficScope,
    WrapMode,
)


# --------------------------------------------------------------------------- #
# Node
# --------------------------------------------------------------------------- #
class NodeBase(BaseModel):
    mac: str
    ip: str
    hostname: str | None = None
    vendor: str | None = None
    os_guess: str | None = None
    open_ports: str | None = None
    services: str | None = None
    notes: str | None = None


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    hostname: str | None = None
    vendor: str | None = None
    os_guess: str | None = None
    criticality: float | None = Field(default=None, ge=0, le=10)
    risk: float | None = Field(default=None, ge=0, le=10)
    pqc_ready: float | None = Field(default=None, ge=0, le=10)
    wrap_mode: WrapMode | None = None
    notes: str | None = None


class NodeOut(NodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pqc_ready: float
    criticality: float
    risk: float
    priority_score: float
    priority_tier: PriorityTier
    wrap_mode: WrapMode
    status: NodeStatus
    first_seen: datetime
    last_seen: datetime


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
class GatewaySessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    listen_port: int
    upstream_host: str
    upstream_port: int
    kem_alg: str
    sig_alg: str
    aead_alg: str
    hybrid: bool
    crypto_suite: str = "pqc-full"
    scope: TrafficScope = TrafficScope.LAN_WAN
    suite_history: str | None = None
    bytes_in: int
    bytes_out: int
    frames_in: int
    frames_out: int
    status: SessionStatus
    started_at: datetime
    last_rekey_at: datetime | None
    closed_at: datetime | None


class CreateSessionRequest(BaseModel):
    node_id: int
    upstream_host: str
    upstream_port: int = Field(ge=1, le=65535)
    listen_port: int | None = Field(default=None, ge=1024, le=65535)
    scope: TrafficScope = TrafficScope.LAN_WAN
    crypto_suite: str | None = None  # if None, policy decides


# --------------------------------------------------------------------------- #
# Migration
# --------------------------------------------------------------------------- #
class MigrationStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ordinal: int
    target_tier: PriorityTier | None
    description: str | None
    status: StageStatus
    progress_pct: float
    started_at: datetime | None
    completed_at: datetime | None


class MigrationTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage_id: int
    node_id: int | None
    action: str
    status: StageStatus
    notes: str | None
    updated_at: datetime


class MigrationPlan(BaseModel):
    stages: list[MigrationStageOut]
    tasks: list[MigrationTaskOut]


# --------------------------------------------------------------------------- #
# Stats / Dashboard
# --------------------------------------------------------------------------- #
class DashboardStats(BaseModel):
    total_nodes: int
    online_nodes: int
    wrapped_nodes: int
    native_pqc_nodes: int
    active_sessions: int
    total_bytes_protected: int
    pqc_engine: dict[str, Any]
    current_stage: str | None
    overall_progress_pct: float


class TrafficSample(BaseModel):
    ts: datetime
    bytes_in: int
    bytes_out: int
    frames: int
    nic_in: int = 0
    nic_out: int = 0


# --------------------------------------------------------------------------- #
# PQC self-test
# --------------------------------------------------------------------------- #
class PQCSelfTestResult(BaseModel):
    kem_ok: bool
    sig_ok: bool
    tunnel_ok: bool
    backend: str
    kem_alg: str
    sig_alg: str
    aead_alg: str
    notes: list[str] = []


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
class DiscoveryStatus(BaseModel):
    running: bool
    last_run: datetime | None
    interface: str | None
    subnet: str | None
    nodes_found: int


class DiscoveryTrigger(BaseModel):
    subnet: str | None = None


# --------------------------------------------------------------------------- #
# Crypto policy
# --------------------------------------------------------------------------- #
class SuiteOut(BaseModel):
    suite: str
    label: str
    pqc: bool
    use_kem: bool
    use_x25519: bool
    use_signature: bool
    aead_key_len: int
    handshake_bytes: int
    description: str
    quantum_safe: str


class PolicyRuleBase(BaseModel):
    name: str
    scope: TrafficScope = TrafficScope.ANY
    tier_filter: str | None = None
    initial_suite: str
    upgrade_suite: str | None = None
    anomaly_threshold: int = Field(default=3, ge=1, le=100)
    anomaly_window_sec: int = Field(default=30, ge=1, le=3600)
    enabled: bool = True
    priority: int = 100
    notes: str | None = None


class PolicyRuleCreate(PolicyRuleBase):
    pass


class PolicyRuleUpdate(BaseModel):
    name: str | None = None
    scope: TrafficScope | None = None
    tier_filter: str | None = None
    initial_suite: str | None = None
    upgrade_suite: str | None = None
    anomaly_threshold: int | None = Field(default=None, ge=1, le=100)
    anomaly_window_sec: int | None = Field(default=None, ge=1, le=3600)
    enabled: bool | None = None
    priority: int | None = None
    notes: str | None = None


class PolicyRuleOut(PolicyRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AnomalyEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    session_id: int | None
    type: AnomalyType
    severity: AnomalySeverity
    message: str
    action_taken: str | None
    from_suite: str | None
    to_suite: str | None


class TriggerAnomalyRequest(BaseModel):
    session_id: int
    type: AnomalyType = AnomalyType.AEAD_FAILURE
    message: str = "manually injected for demo"
