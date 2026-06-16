"""asyncio TCP proxy with optional PQC-tunnel egress.

For each configured GatewaySession, the gateway opens a listener on
`listen_port`. Local LAN clients (or the gateway's own IP redirected via
firewall rules) connect to that port. The gateway then:

    *   establishes (or reuses) a PQC tunnel to the upstream peer
    *   pumps bytes  client ↔ tunnel (frames)
    *   updates traffic stats and DB session counters

If a per-session PQC peer is configured, the upstream is treated as
another gateway instance running `handshake_server`. Otherwise the
gateway can also operate in **wrap-then-classical** mode where it
maintains the PQC envelope only between the two gateways and emits plain
TCP to the final upstream — useful for migrating internet egress.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from ..database import session_scope
from ..models import (
    AnomalySeverity,
    AnomalyType,
    GatewaySession,
    Node,
    SessionStatus,
    WrapMode,
)
from ..policy.anomaly import get_detector
from ..pqc.engine import PQCEngine, get_engine
from ..pqc.tunnel import (
    handshake_client,
    handshake_server,
    recv_frame,
    send_frame,
)
from .monitor import get_monitor

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# in-memory active sessions
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class ActiveListener:
    session_id: int
    node_id: int
    listen_port: int
    upstream_host: str
    upstream_port: int
    server: asyncio.base_events.Server
    pqc_to_upstream: bool = True
    suite: str = "pqc-full"
    bytes_in: int = 0
    bytes_out: int = 0
    frames: int = 0
    anomalies: int = 0
    tasks: list[asyncio.Task] = field(default_factory=list)


class GatewayService:
    """Lifecycle manager for all proxy listeners."""

    def __init__(self) -> None:
        self._listeners: dict[int, ActiveListener] = {}
        self._lock = asyncio.Lock()
        self._engine: PQCEngine = get_engine()
        self._monitor = get_monitor()

    # --------------------------------------------------------------------- #
    # public API
    # --------------------------------------------------------------------- #
    async def start_session(
        self,
        session_id: int,
        node_id: int,
        listen_host: str,
        listen_port: int,
        upstream_host: str,
        upstream_port: int,
        pqc_to_upstream: bool = True,
        suite: str = "pqc-full",
    ) -> ActiveListener:
        async with self._lock:
            if session_id in self._listeners:
                return self._listeners[session_id]

            server = await asyncio.start_server(
                lambda r, w: self._handle_client(session_id, r, w),
                host=listen_host,
                port=listen_port,
                reuse_address=True,
            )
            entry = ActiveListener(
                session_id=session_id,
                node_id=node_id,
                listen_port=listen_port,
                upstream_host=upstream_host,
                upstream_port=upstream_port,
                server=server,
                pqc_to_upstream=pqc_to_upstream,
                suite=suite,
            )
            self._listeners[session_id] = entry

            await self._mark_session_status(session_id, SessionStatus.ESTABLISHED)
            logger.info(
                "Gateway session %s listening on %s:%d → %s:%d (suite=%s, pqc=%s)",
                session_id, listen_host, listen_port,
                upstream_host, upstream_port, suite, pqc_to_upstream,
            )
            return entry

    async def restart_with_suite(self, session_id: int, new_suite: str) -> bool:
        """Tear down a session and re-bind the same listener with a new suite.

        Triggered by the policy engine when an anomaly threshold fires.
        """
        entry = self._listeners.get(session_id)
        if not entry:
            return False
        logger.warning(
            "Restarting session %d on port %d with suite %s (was %s)",
            session_id, entry.listen_port, new_suite, entry.suite,
        )
        await self.stop_session(session_id)
        # rebind with same params, new suite
        await self.start_session(
            session_id=session_id,
            node_id=entry.node_id,
            listen_host="0.0.0.0",
            listen_port=entry.listen_port,
            upstream_host=entry.upstream_host,
            upstream_port=entry.upstream_port,
            pqc_to_upstream=entry.pqc_to_upstream,
            suite=new_suite,
        )
        return True

    async def stop_session(self, session_id: int) -> bool:
        async with self._lock:
            entry = self._listeners.pop(session_id, None)
        if not entry:
            return False
        entry.server.close()
        try:
            await entry.server.wait_closed()
        except Exception:
            pass
        for t in entry.tasks:
            t.cancel()
        await self._mark_session_status(session_id, SessionStatus.CLOSED, closed=True)
        logger.info("Gateway session %s stopped.", session_id)
        return True

    async def stop_all(self) -> None:
        ids = list(self._listeners.keys())
        for sid in ids:
            await self.stop_session(sid)

    def list_active(self) -> list[ActiveListener]:
        return list(self._listeners.values())

    # --------------------------------------------------------------------- #
    # internals
    # --------------------------------------------------------------------- #
    async def _handle_client(
        self,
        session_id: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peername = writer.get_extra_info("peername")
        listener = self._listeners.get(session_id)
        if not listener:
            writer.close()
            return

        logger.debug("Client connected on session %d from %s", session_id, peername)

        try:
            up_reader, up_writer = await asyncio.open_connection(
                listener.upstream_host, listener.upstream_port
            )
        except Exception as e:
            logger.warning(
                "Upstream %s:%d unreachable for session %d: %s",
                listener.upstream_host, listener.upstream_port, session_id, e,
            )
            writer.close()
            return

        if listener.pqc_to_upstream:
            try:
                tunnel = await handshake_client(
                    up_reader, up_writer, self._engine,
                    peer_id=f"{listener.upstream_host}:{listener.upstream_port}",
                    suite=listener.suite,
                )
            except Exception as e:
                logger.warning("PQC handshake failed for session %d: %s", session_id, e)
                await get_detector().record(
                    session_id=session_id,
                    type_=AnomalyType.HANDSHAKE_FAILURE,
                    severity=AnomalySeverity.HIGH,
                    message=f"Handshake to {listener.upstream_host}:{listener.upstream_port} failed: {e}",
                )
                up_writer.close()
                writer.close()
                return

            await self._mark_session_status(session_id, SessionStatus.ESTABLISHED)

            t1 = asyncio.create_task(
                self._pump_to_tunnel(reader, up_writer, tunnel, listener)
            )
            t2 = asyncio.create_task(
                self._pump_from_tunnel(up_reader, writer, tunnel, listener)
            )
            listener.tasks.extend((t1, t2))
            done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
        else:
            # Plain TCP forwarding (used in MONITOR / OFF mode)
            t1 = asyncio.create_task(self._pump_plain(reader, up_writer, listener, "out"))
            t2 = asyncio.create_task(self._pump_plain(up_reader, writer, listener, "in"))
            listener.tasks.extend((t1, t2))
            await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)

        for w in (writer, up_writer):
            try:
                w.close()
            except Exception:
                pass

    async def _pump_to_tunnel(
        self,
        client_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
        tunnel,
        listener: ActiveListener,
    ) -> None:
        try:
            while True:
                data = await client_reader.read(16 * 1024)
                if not data:
                    break
                await send_frame(upstream_writer, tunnel, data, self._engine)
                listener.bytes_out += len(data)
                listener.frames += 1
                self._monitor.add_out(len(data))
        except Exception as e:
            logger.debug("client→tunnel pump ended: %s", e)

    async def _pump_from_tunnel(
        self,
        upstream_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        tunnel,
        listener: ActiveListener,
    ) -> None:
        from cryptography.exceptions import InvalidTag

        try:
            while True:
                try:
                    data = await recv_frame(upstream_reader, tunnel, self._engine)
                except InvalidTag as e:
                    listener.anomalies += 1
                    await get_detector().record(
                        session_id=listener.session_id,
                        type_=AnomalyType.AEAD_FAILURE,
                        severity=AnomalySeverity.HIGH,
                        message=f"AEAD decryption failed (frame {tunnel.recv_counter}): {e}",
                    )
                    break
                except Exception as e:
                    logger.debug("tunnel recv ended: %s", e)
                    break

                if not data:
                    break
                client_writer.write(data)
                await client_writer.drain()
                listener.bytes_in += len(data)
                listener.frames += 1
                self._monitor.add_in(len(data))
        except Exception as e:
            logger.debug("tunnel→client pump ended: %s", e)

    async def _pump_plain(
        self,
        src: asyncio.StreamReader,
        dst: asyncio.StreamWriter,
        listener: ActiveListener,
        direction: str,
    ) -> None:
        try:
            while True:
                data = await src.read(16 * 1024)
                if not data:
                    break
                dst.write(data)
                await dst.drain()
                if direction == "in":
                    listener.bytes_in += len(data)
                    self._monitor.add_in(len(data))
                else:
                    listener.bytes_out += len(data)
                    self._monitor.add_out(len(data))
        except Exception:
            pass

    # --------------------------------------------------------------------- #
    # DB sync
    # --------------------------------------------------------------------- #
    async def _mark_session_status(
        self, session_id: int, status: SessionStatus, closed: bool = False
    ) -> None:
        try:
            async with session_scope() as db:
                row = await db.get(GatewaySession, session_id)
                if row:
                    row.status = status
                    if closed:
                        row.closed_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.debug("Could not update session %d status: %s", session_id, e)

    async def flush_counters(self) -> None:
        """Periodically called to push byte counters to DB."""
        async with session_scope() as db:
            for entry in self._listeners.values():
                row = await db.get(GatewaySession, entry.session_id)
                if row:
                    row.bytes_in = entry.bytes_in
                    row.bytes_out = entry.bytes_out
                    row.frames_in = entry.frames
                    row.frames_out = entry.frames


# --------------------------------------------------------------------------- #
# upstream PQC server (for gateway-to-gateway / lab demo mode)
# --------------------------------------------------------------------------- #
class PQCEchoServer:
    """Tiny PQC-tunnel echo server — handy for the self-test & demos.

    Listens on an arbitrary port and echoes every frame back. Lets the UI
    "Self-test" page run a real round-trip through the engine.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 18999) -> None:
        self.host = host
        self.port = port
        self._server: asyncio.base_events.Server | None = None
        self._engine = get_engine()

    async def start(self) -> None:
        if self._server:
            return
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        logger.info("PQC echo server listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            tunnel = await handshake_server(reader, writer, self._engine, peer_id="echo")
            while True:
                data = await recv_frame(reader, tunnel, self._engine)
                if not data:
                    break
                await send_frame(writer, tunnel, data, self._engine)
        except Exception as e:
            logger.debug("echo session ended: %s", e)
        finally:
            try:
                writer.close()
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# singletons + bootstrap helpers
# --------------------------------------------------------------------------- #
_gateway_singleton: GatewayService | None = None
_echo_singleton: PQCEchoServer | None = None


def get_gateway() -> GatewayService:
    global _gateway_singleton
    if _gateway_singleton is None:
        _gateway_singleton = GatewayService()
        # Wire the anomaly detector's upgrade callback to the gateway.
        async def _on_upgrade(session_id: int) -> None:
            from sqlalchemy import select as _select
            async with session_scope() as db:
                row = await db.get(GatewaySession, session_id)
                if row:
                    await _gateway_singleton.restart_with_suite(  # type: ignore[arg-type]
                        session_id, row.crypto_suite
                    )
        get_detector().on_upgrade = _on_upgrade
    return _gateway_singleton


def get_echo_server() -> PQCEchoServer:
    global _echo_singleton
    if _echo_singleton is None:
        _echo_singleton = PQCEchoServer()
    return _echo_singleton


async def restart_persisted_sessions() -> None:
    """Re-bind listeners for sessions that were active before restart."""
    gw = get_gateway()
    async with session_scope() as db:
        rows = (
            await db.execute(
                select(GatewaySession).where(
                    GatewaySession.status.in_(
                        [SessionStatus.ESTABLISHED, SessionStatus.NEGOTIATING]
                    )
                )
            )
        ).scalars().all()
        for r in rows:
            try:
                node = await db.get(Node, r.node_id)
                if not node or node.wrap_mode == WrapMode.OFF:
                    continue
                await gw.start_session(
                    session_id=r.id,
                    node_id=r.node_id,
                    listen_host="0.0.0.0",
                    listen_port=r.listen_port,
                    upstream_host=r.upstream_host,
                    upstream_port=r.upstream_port,
                    pqc_to_upstream=node.wrap_mode == WrapMode.WRAP,
                    suite=r.crypto_suite or "pqc-full",
                )
            except Exception as e:
                logger.warning("Could not restart session %d: %s", r.id, e)
                r.status = SessionStatus.FAILED
