"""PQC engine endpoints (info + self-test + demo traffic)."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from fastapi import APIRouter

from ..network.gateway import get_echo_server
from ..network.monitor import get_monitor
from ..pqc.engine import get_engine
from ..pqc.tunnel import (
    handshake_client,
    recv_frame,
    send_frame,
)
from ..schemas import PQCSelfTestResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pqc", tags=["pqc"])


@router.get("/info", response_model=dict)
async def info() -> dict:
    return get_engine().describe()


@router.post("/selftest", response_model=PQCSelfTestResult)
async def selftest() -> PQCSelfTestResult:
    engine = get_engine()
    notes: list[str] = []
    info = engine.describe()

    # 1) KEM round trip
    kem_ok = False
    try:
        pk, sk = engine.kem_keypair()
        ct, ss1 = engine.kem_encaps(pk)
        ss2 = engine.kem_decaps(sk, ct)
        kem_ok = ss1 == ss2 and len(ss1) >= 16
        if not kem_ok:
            notes.append("KEM shared secrets did not match.")
    except Exception as e:
        notes.append(f"KEM error: {e}")

    # 2) SIG round trip
    sig_ok = False
    try:
        pk, sk = engine.sig_keypair()
        msg = b"pqcg selftest message"
        sig = engine.sign(sk, msg)
        sig_ok = engine.verify(pk, msg, sig)
        if not sig_ok:
            notes.append("Signature verification failed.")
    except Exception as e:
        notes.append(f"SIG error: {e}")

    # 3) Tunnel round trip via local echo server
    tunnel_ok = False
    try:
        echo = get_echo_server()
        await echo.start()
        reader, writer = await asyncio.open_connection(echo.host, echo.port)
        tunnel = await handshake_client(reader, writer, engine)
        await send_frame(writer, tunnel, b"hello-pqc", engine)
        reply = await asyncio.wait_for(recv_frame(reader, tunnel, engine), timeout=5.0)
        tunnel_ok = reply == b"hello-pqc"
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        if not tunnel_ok:
            notes.append("Tunnel echo mismatch.")
    except Exception as e:
        notes.append(f"Tunnel error: {e}")

    return PQCSelfTestResult(
        kem_ok=kem_ok,
        sig_ok=sig_ok,
        tunnel_ok=tunnel_ok,
        backend=info["backend"],
        kem_alg=info["kem_alg"],
        sig_alg=info["sig_alg"],
        aead_alg=info["aead_alg"],
        notes=notes,
    )


@router.post("/test-traffic", response_model=dict)
async def send_test_traffic(
    iterations: int = 32,
    payload_size: int = 16 * 1024,
) -> dict:
    """Push a burst of frames through the bundled PQC echo server.

    Useful for filling the live-traffic chart on a freshly booted gateway
    before any real LAN sessions are configured.
    """
    iterations = max(1, min(iterations, 1000))
    payload_size = max(1, min(payload_size, 1024 * 1024))

    engine = get_engine()
    monitor = get_monitor()
    echo = get_echo_server()
    await echo.start()

    started = time.perf_counter()
    payload = os.urandom(payload_size)
    total_sent = 0
    total_recv = 0

    try:
        reader, writer = await asyncio.open_connection(echo.host, echo.port)
        tunnel = await handshake_client(reader, writer, engine)

        for _ in range(iterations):
            await send_frame(writer, tunnel, payload, engine)
            total_sent += len(payload)
            monitor.add_out(len(payload))

            reply = await asyncio.wait_for(recv_frame(reader, tunnel, engine), timeout=5.0)
            total_recv += len(reply)
            monitor.add_in(len(reply))

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
    except Exception as e:
        return {"ok": False, "error": str(e)}

    elapsed = time.perf_counter() - started
    return {
        "ok": True,
        "iterations": iterations,
        "payload_size": payload_size,
        "bytes_sent": total_sent,
        "bytes_recv": total_recv,
        "elapsed_sec": round(elapsed, 3),
        "throughput_mbps": round((total_sent + total_recv) * 8 / elapsed / 1_000_000, 2),
    }
