"""Compatibility entry point.

Use `uvicorn api.main:app` for new deployments. This module exists so older
Render services configured with `uvicorn backend.main:app` still run the rebuilt
FastAPI app instead of the archived legacy backend.
"""

from api.main import app, run

__all__ = ["app", "run"]
