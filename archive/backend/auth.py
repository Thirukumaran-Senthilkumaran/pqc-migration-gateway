"""Connector token authentication."""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import ConnectorToken

security = HTTPBearer(auto_error=False)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_token() -> tuple[str, str, str]:
    """Return (raw_token, hash, prefix)."""
    raw = f"pqcg_{secrets.token_urlsafe(32)}"
    return raw, hash_token(raw), raw[:12]


def create_connector_token(db: Session, name: str, org_name: str = "Default Org") -> tuple[ConnectorToken, str]:
    raw, th, prefix = generate_token()
    row = ConnectorToken(name=name, token_hash=th, token_prefix=prefix, org_name=org_name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def verify_connector_token(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> ConnectorToken:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Bearer token")
    th = hash_token(creds.credentials)
    row = db.query(ConnectorToken).filter(ConnectorToken.token_hash == th, ConnectorToken.active == True).first()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked token")
    return row
