"""PQC engine package.

Public surface:
    PQCEngine      - high-level facade
    get_engine()   - cached singleton
"""

from .engine import PQCEngine, get_engine

__all__ = ["PQCEngine", "get_engine"]
