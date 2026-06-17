"""Report export routes and the AI advisor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LanDevice
from ..services.ai_advisor import migration_advice
from ..services.reports import REPORT_KINDS, render_report

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/advisor")
def advisor(db: Session = Depends(get_db)):
    devices = db.query(LanDevice).all()
    return migration_advice(devices)


@router.get("/reports/{fmt}")
def download_report(fmt: str, db: Session = Depends(get_db)):
    if fmt not in REPORT_KINDS:
        raise HTTPException(404, "Unknown report format")
    filename, media_type, is_binary = REPORT_KINDS[fmt]
    devices = db.query(LanDevice).all()
    content, _ = render_report(fmt, devices)
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    if is_binary:
        return Response(content, media_type=media_type, headers=headers)
    return PlainTextResponse(content, media_type=media_type, headers=headers)
