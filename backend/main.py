"""FastAPI entry point.

Boots:
    * SQLite DB
    * PQC engine
    * Discovery service (background)
    * PQC echo server (for self-test)
    * Migration plan defaults
    * REST + WebSocket API
    * Static dashboard (if built)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import gateway as gateway_api
from .api import migration as migration_api
from .api import nodes as nodes_api
from .api import policy as policy_api
from .api import pqc as pqc_api
from .api import stats as stats_api
from .api import ws as ws_api
from .config import get_settings
from .database import init_db
from .migration.planner import ensure_default_plan, rebuild_tasks
from .network.classifier import reclassify_all
from .network.discovery import get_discovery
from .network.gateway import get_echo_server, get_gateway, restart_persisted_sessions
from .network.monitor import get_monitor
from .policy.engine import get_policy
from .pqc.engine import get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Booting %s v%s …", settings.app_name, settings.version)

    await init_db()
    engine = get_engine()
    logger.info("PQC engine: %s", engine.describe())

    await ensure_default_plan()
    await get_policy().ensure_defaults()

    discovery = get_discovery()
    await discovery.start()

    monitor = get_monitor()
    await monitor.start_nic_poller()

    echo = get_echo_server()
    await echo.start()

    await restart_persisted_sessions()

    # background classification & migration sync loop
    async def periodic():
        while True:
            try:
                await reclassify_all()
                await rebuild_tasks()
                await get_gateway().flush_counters()
            except Exception as e:
                logger.warning("Periodic task failed: %s", e)
            await asyncio.sleep(30)

    bg_task = asyncio.create_task(periodic(), name="periodic-housekeeping")

    try:
        yield
    finally:
        logger.info("Shutting down …")
        bg_task.cancel()
        try:
            await bg_task
        except Exception:
            pass
        await monitor.stop_nic_poller()
        await discovery.stop()
        await echo.stop()
        await get_gateway().stop_all()
        logger.info("Bye.")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers
app.include_router(nodes_api.router)
app.include_router(pqc_api.router)
app.include_router(gateway_api.router)
app.include_router(migration_api.router)
app.include_router(policy_api.router)
app.include_router(stats_api.router)
app.include_router(ws_api.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.version}


# --------------------------------------------------------------------------- #
# Static frontend (if built)
# --------------------------------------------------------------------------- #
def _maybe_mount_frontend() -> None:
    static_dir: Path = settings.static_dir
    if not static_dir.exists():
        logger.warning(
            "Frontend build not found at %s — UI will not be served.",
            static_dir,
        )
        return

    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", response_model=None, include_in_schema=False)
    async def index():
        return FileResponse(static_dir / "index.html")

    # SPA fallback: anything not /api or /ws → index.html
    @app.get("/{path:path}", response_model=None, include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api") or path.startswith("ws"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        target = static_dir / path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(static_dir / "index.html")


_maybe_mount_frontend()


def run() -> None:
    """Entrypoint used by `python -m backend.main` and the launcher scripts."""
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
