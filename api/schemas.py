"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestDevice(BaseModel):
    ip: str
    mac: str | None = None
    hostname: str | None = None
    service: str | None = None
    port: int | None = None
    tls_version: str | None = None
    cert_type: str | None = None
    weak_protocol: str | None = None
    vendor: str | None = None
    risk_score: float | None = None


class IngestPayload(BaseModel):
    type: str = Field(default="inventory", description="inventory | heartbeat | scan_result | risk_score")
    subnet: str | None = None
    connector_version: str = "2.0"
    devices: list[IngestDevice] = []
    metadata: dict[str, Any] = {}


class TokenCreate(BaseModel):
    name: str = "LAN Connector"
    org_name: str = "Default Org"


class TokenOut(BaseModel):
    id: int
    name: str
    token_prefix: str
    org_name: str
    active: bool
    created_at: datetime
    last_seen: datetime | None
    device_count: int = 0


class DeviceOut(BaseModel):
    id: int
    ip: str
    mac: str | None
    hostname: str | None
    service: str | None
    port: int | None
    tls_version: str | None
    cert_type: str | None
    weak_protocol: str | None
    pqc_candidate: str | None
    priority_tier: str
    wrap_status: str
    risk_score: float
    last_seen: datetime

    model_config = {"from_attributes": True}


class WrapRequest(BaseModel):
    device_ids: list[int]
    action: str = Field(description="apply | remove")


class DashboardStats(BaseModel):
    total_devices: int
    wrapped_devices: int
    tier1_devices: int
    connectors_online: int
    pqc_coverage_pct: float
    remote_gateway_status: str
    last_ingest: datetime | None
    pqc_backend: str
    quantum_safe: bool


class WrapDemoRequest(BaseModel):
    message: str = "Confidential LAN payload"
    mode: str = "memory"  # memory | socket
