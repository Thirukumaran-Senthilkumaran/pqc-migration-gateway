"""
PQC tunnel: authenticated key establishment + AES-256-GCM record protocol.

Handshake (server-authenticated, like a simplified TLS 1.3):

    server                                   client
    ------                                   ------
    sig_pk ---------------------------------->            (server identity)
    kem_pk, sign(sig_sk, transcript) -------->            client verifies signature
            <---------------------------- kem_ct          client encapsulates -> ss
    derive key = HKDF(ss)                    derive key = HKDF(ss)

Both sides then exchange AES-256-GCM records with a monotonic nonce. The same
primitives back the live socket gateway (``gateway.py``) and the in-process
demonstration shown in the UI.
"""

from __future__ import annotations

import hashlib
import os
import struct

from .backend import PQCBackend, get_backend


def hkdf_sha256(shared_secret: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF (extract+expand) with an empty salt."""
    prk = hashlib.pbkdf2_hmac("sha256", shared_secret, b"pqcg-hkdf-salt", 1, dklen=32)
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        import hmac

        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


class AeadChannel:
    """AES-256-GCM record channel with directional nonces."""

    def __init__(self, key: bytes, role: str):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self._aes = AESGCM(key)
        self._send_ctr = 0
        self._recv_ctr = 0
        # separate nonce prefixes per direction to avoid reuse
        self._send_prefix = b"\x00" if role == "server" else b"\x01"
        self._recv_prefix = b"\x01" if role == "server" else b"\x00"

    def _nonce(self, prefix: bytes, ctr: int) -> bytes:
        return prefix + struct.pack(">Q", ctr) + b"\x00\x00\x00"

    def seal(self, plaintext: bytes, aad: bytes = b"") -> bytes:
        nonce = self._nonce(self._send_prefix, self._send_ctr)
        self._send_ctr += 1
        return self._aes.encrypt(nonce, plaintext, aad)

    def open(self, ciphertext: bytes, aad: bytes = b"") -> bytes:
        nonce = self._nonce(self._recv_prefix, self._recv_ctr)
        self._recv_ctr += 1
        return self._aes.decrypt(nonce, ciphertext, aad)


class ServerIdentity:
    """Long-lived server signing identity (re-used across handshakes)."""

    def __init__(self, backend: PQCBackend | None = None):
        self.backend = backend or get_backend()
        self.sig_pk, self.sig_sk = self.backend.sig_keypair()


class HandshakeResult:
    def __init__(self, channel: AeadChannel, transcript: dict):
        self.channel = channel
        self.transcript = transcript


def server_handshake(identity: ServerIdentity) -> tuple[bytes, "function"]:
    """
    Build the server hello and return (server_hello_bytes, finish_fn).
    ``finish_fn(kem_ct)`` completes the handshake and returns HandshakeResult.
    """
    backend = identity.backend
    kem_pk, kem_sk = backend.kem_keypair()
    transcript = identity.sig_pk + kem_pk
    signature = backend.sign(identity.sig_sk, transcript)

    hello = _encode_hello(identity.sig_pk, kem_pk, signature)

    def finish(kem_ct: bytes) -> HandshakeResult:
        shared = backend.kem_decapsulate(kem_sk, kem_ct)
        key = hkdf_sha256(shared, b"pqcg-tunnel-v1")
        return HandshakeResult(
            AeadChannel(key, "server"),
            {
                "backend": backend.info.name,
                "kem_alg": backend.info.kem_alg,
                "sig_alg": backend.info.sig_alg,
                "quantum_safe": backend.info.quantum_safe,
                "key_fingerprint": hashlib.sha256(key).hexdigest()[:16],
            },
        )

    return hello, finish


def client_handshake(server_hello: bytes, backend: PQCBackend | None = None) -> tuple[bytes, HandshakeResult]:
    """Process server hello, return (kem_ct_to_send, HandshakeResult)."""
    backend = backend or get_backend()
    sig_pk, kem_pk, signature = _decode_hello(server_hello)

    transcript = sig_pk + kem_pk
    if not backend.verify(sig_pk, transcript, signature):
        raise ValueError("Server signature verification failed - possible MITM")

    kem_ct, shared = backend.kem_encapsulate(kem_pk)
    key = hkdf_sha256(shared, b"pqcg-tunnel-v1")
    result = HandshakeResult(
        AeadChannel(key, "client"),
        {
            "backend": backend.info.name,
            "kem_alg": backend.info.kem_alg,
            "sig_alg": backend.info.sig_alg,
            "quantum_safe": backend.info.quantum_safe,
            "key_fingerprint": hashlib.sha256(key).hexdigest()[:16],
            "server_authenticated": True,
        },
    )
    return kem_ct, result


# --- wire encoding -------------------------------------------------------- #
def _encode_hello(sig_pk: bytes, kem_pk: bytes, signature: bytes) -> bytes:
    return b"".join(
        struct.pack(">I", len(p)) + p for p in (sig_pk, kem_pk, signature)
    )


def _decode_hello(blob: bytes) -> tuple[bytes, bytes, bytes]:
    parts = []
    off = 0
    for _ in range(3):
        (n,) = struct.unpack(">I", blob[off : off + 4])
        off += 4
        parts.append(blob[off : off + n])
        off += n
    return parts[0], parts[1], parts[2]


# --- in-process demonstration (used by the dashboard) --------------------- #
def demonstrate_wrap(plaintext: bytes, backend_name: str | None = None) -> dict:
    """
    Run a full handshake + encrypt + decrypt in memory and return a transcript
    suitable for display. Proves the tunnel actually protects and recovers data.
    """
    backend = get_backend(backend_name)
    identity = ServerIdentity(backend)

    hello, finish = server_handshake(identity)
    kem_ct, client_res = client_handshake(hello, backend)
    server_res = finish(kem_ct)

    # client -> server protected record
    sealed = client_res.channel.seal(plaintext, aad=b"pqcg")
    recovered = server_res.channel.open(sealed, aad=b"pqcg")

    return {
        "backend": backend.info.name,
        "kem_alg": backend.info.kem_alg,
        "sig_alg": backend.info.sig_alg,
        "quantum_safe": backend.info.quantum_safe,
        "server_hello_bytes": len(hello),
        "kem_ciphertext_bytes": len(kem_ct),
        "key_fingerprint": server_res.transcript["key_fingerprint"],
        "keys_match": client_res.transcript["key_fingerprint"]
        == server_res.transcript["key_fingerprint"],
        "plaintext": plaintext.decode("utf-8", "replace"),
        "ciphertext_hex": sealed.hex(),
        "ciphertext_bytes": len(sealed),
        "recovered": recovered.decode("utf-8", "replace"),
        "verified": recovered == plaintext,
        "server_authenticated": True,
    }
