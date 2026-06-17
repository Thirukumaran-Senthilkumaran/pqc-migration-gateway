"""Quick smoke test for the PQC engine.

Usage:
    python scripts/smoke_test.py

Exercises:
    1. KEM keygen / encaps / decaps round-trip.
    2. ML-DSA sign / verify.
    3. End-to-end async PQC tunnel (handshake + AEAD echo).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# allow running from anywhere
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.pqc.engine import get_engine  # noqa: E402
from backend.pqc.tunnel import (  # noqa: E402
    handshake_client,
    handshake_server,
    recv_frame,
    send_frame,
)


async def tunnel_echo() -> bool:
    engine = get_engine()
    server_started = asyncio.Event()
    server_session = {}

    async def handle(reader, writer):
        try:
            sess = await handshake_server(reader, writer, engine, peer_id="test")
            server_session["sess"] = sess
            data = await recv_frame(reader, sess, engine)
            await send_frame(writer, sess, data, engine)
        except Exception as e:
            print("server err:", e)
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server_started.set()

    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        client_sess = await handshake_client(reader, writer, engine)
        await send_frame(writer, client_sess, b"hello pqc world", engine)
        reply = await recv_frame(reader, client_sess, engine)
        writer.close()
        ok = reply == b"hello pqc world"
        return ok


async def main() -> int:
    engine = get_engine()
    print(f"Engine info: {engine.describe()}")

    pk, sk = engine.kem_keypair()
    ct, ss1 = engine.kem_encaps(pk)
    ss2 = engine.kem_decaps(sk, ct)
    kem_ok = ss1 == ss2 and len(ss1) >= 16
    print(f"  KEM round trip ............ {'OK' if kem_ok else 'FAIL'}")

    pk, sk = engine.sig_keypair()
    msg = b"smoke test"
    sig = engine.sign(sk, msg)
    sig_ok = engine.verify(pk, msg, sig)
    print(f"  SIG round trip ............ {'OK' if sig_ok else 'FAIL'}")

    tunnel_ok = await tunnel_echo()
    print(f"  Tunnel echo ............... {'OK' if tunnel_ok else 'FAIL'}")

    return 0 if (kem_ok and sig_ok and tunnel_ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
