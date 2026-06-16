"""asyncio TCP tunnel framing using the PQC engine.

Wire format (over the underlying TCP socket):
    [ 4-byte big-endian length ][ ciphertext+16-byte GCM tag ]

Length is the length of (ciphertext + tag); the AEAD nonce is implicit and
derived from the per-direction frame counter starting at 0.

Handshake (client perspective):
    1.  Send 32-byte session id  +  32-byte X25519 ephemeral pk  +  KEM pk
    2.  Receive 32-byte X25519 peer pk  +  KEM ciphertext
    3.  Decapsulate ML-KEM, complete X25519 → derive session keys.

Handshake (server is the mirror).

This module is deliberately small and self-contained so it can be exercised
by unit tests without touching real sockets.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import struct
import time

from .engine import PQCEngine, TunnelSession

logger = logging.getLogger(__name__)

LEN_PREFIX = 4
SESSION_ID_LEN = 32
X25519_PK_LEN = 32

# Suite IDs negotiated on the wire (1 byte).
SUITE_ID = {
    "classical":      0x01,
    "pqc-compressed": 0x02,
    "pqc-full":       0x03,
}
SUITE_BY_ID = {v: k for k, v in SUITE_ID.items()}


def _suite_flags(suite_name: str) -> tuple[bool, bool, bool, int]:
    """Return (use_kem, use_x25519, use_signature, aead_key_len)."""
    if suite_name == "classical":
        return (False, True, False, 16)
    if suite_name == "pqc-compressed":
        return (True, False, False, 16)
    # pqc-full
    return (True, True, True, 32)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    buf = await reader.readexactly(n)
    return buf


async def _read_lp(reader: asyncio.StreamReader) -> bytes:
    raw_len = await _read_exact(reader, LEN_PREFIX)
    (length,) = struct.unpack(">I", raw_len)
    return await _read_exact(reader, length)


async def _write_lp(writer: asyncio.StreamWriter, data: bytes) -> None:
    writer.write(struct.pack(">I", len(data)) + data)
    await writer.drain()


# --------------------------------------------------------------------------- #
# handshake
# --------------------------------------------------------------------------- #
async def handshake_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    engine: PQCEngine,
    peer_id: str = "upstream",
    suite: str = "pqc-full",
) -> TunnelSession:
    use_kem, use_x25519, _use_sig, key_len = _suite_flags(suite)
    suite_id = SUITE_ID.get(suite, SUITE_ID["pqc-full"])

    sid = secrets.token_bytes(SESSION_ID_LEN)
    x_pk, x_sk = engine.x25519_keypair() if use_x25519 else (b"", b"")
    kem_pk, kem_sk = engine.kem_keypair() if use_kem else (b"", b"")

    msg1 = struct.pack(">B", suite_id) + sid
    if use_x25519:
        msg1 += x_pk
    if use_kem:
        msg1 += struct.pack(">I", len(kem_pk)) + kem_pk
    await _write_lp(writer, msg1)

    msg2 = await _read_lp(reader)
    off = 0
    peer_xpk = b""
    if use_x25519:
        peer_xpk = msg2[off : off + X25519_PK_LEN]; off += X25519_PK_LEN
    kem_ct = b""
    if use_kem:
        (ct_len,) = struct.unpack(">I", msg2[off : off + 4]); off += 4
        kem_ct = msg2[off : off + ct_len]; off += ct_len

    kem_ss = engine.kem_decaps(kem_sk, kem_ct) if use_kem else b""
    x_ss = engine.x25519_shared(x_sk, peer_xpk) if use_x25519 else None

    transcript = sid + msg1 + msg2
    sess = engine.derive_session(
        role="client",
        kem_shared=kem_ss,
        x_shared=x_ss,
        transcript=transcript,
        peer_id=peer_id,
        session_id=sid,
        aead_key_len=key_len,
    )
    sess.metadata["suite"] = suite
    return sess


async def handshake_server(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    engine: PQCEngine,
    peer_id: str = "client",
) -> TunnelSession:
    msg1 = await _read_lp(reader)
    suite_id = msg1[0]
    suite = SUITE_BY_ID.get(suite_id, "pqc-full")
    use_kem, use_x25519, _use_sig, key_len = _suite_flags(suite)

    off = 1
    sid = msg1[off : off + SESSION_ID_LEN]; off += SESSION_ID_LEN

    peer_xpk = b""
    x_pk, x_sk = b"", b""
    if use_x25519:
        peer_xpk = msg1[off : off + X25519_PK_LEN]; off += X25519_PK_LEN
        x_pk, x_sk = engine.x25519_keypair()

    kem_pk = b""
    if use_kem:
        (kem_pk_len,) = struct.unpack(">I", msg1[off : off + 4]); off += 4
        kem_pk = msg1[off : off + kem_pk_len]; off += kem_pk_len

    kem_ct, kem_ss = engine.kem_encaps(kem_pk) if use_kem else (b"", b"")

    msg2 = b""
    if use_x25519:
        msg2 += x_pk
    if use_kem:
        msg2 += struct.pack(">I", len(kem_ct)) + kem_ct
    await _write_lp(writer, msg2)

    x_ss = engine.x25519_shared(x_sk, peer_xpk) if use_x25519 else None

    transcript = sid + msg1 + msg2
    sess = engine.derive_session(
        role="server",
        kem_shared=kem_ss,
        x_shared=x_ss,
        transcript=transcript,
        peer_id=peer_id,
        session_id=sid,
        aead_key_len=key_len,
    )
    sess.metadata["suite"] = suite
    return sess


# --------------------------------------------------------------------------- #
# data plane
# --------------------------------------------------------------------------- #
async def send_frame(
    writer: asyncio.StreamWriter,
    session: TunnelSession,
    payload: bytes,
    engine: PQCEngine,
) -> None:
    ct = engine.aead_seal(session.send_key, session.send_counter, payload)
    session.send_counter += 1
    session.bytes_out += len(payload)
    await _write_lp(writer, ct)


async def recv_frame(
    reader: asyncio.StreamReader,
    session: TunnelSession,
    engine: PQCEngine,
) -> bytes:
    ct = await _read_lp(reader)
    pt = engine.aead_open(session.recv_key, session.recv_counter, ct)
    session.recv_counter += 1
    session.bytes_in += len(pt)
    return pt
