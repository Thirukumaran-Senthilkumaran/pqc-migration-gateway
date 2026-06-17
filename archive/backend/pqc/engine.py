"""PQC engine facade.

Combines a chosen backend (liboqs / pqcrypto / demo) with:
    - hybrid X25519 + ML-KEM key agreement
    - HKDF-SHA-384 key derivation
    - AES-256-GCM frame AEAD
    - simple in-memory tunnel session abstraction (used by the gateway proxy)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from .backends import BackendProtocol, load_backend

logger = logging.getLogger(__name__)


HKDF_HASH = hashes.SHA384()
AEAD_KEY_LEN = 32  # AES-256


# --------------------------------------------------------------------------- #
# session container
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class TunnelSession:
    session_id: bytes
    peer_id: str
    send_key: bytes
    recv_key: bytes
    send_counter: int = 0
    recv_counter: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    created_at: float = 0.0
    rekeyed_at: float = 0.0
    transcript: bytes = b""
    metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #
class PQCEngine:
    """High-level operations used by the rest of the gateway."""

    def __init__(self, backend: Optional[BackendProtocol] = None, hybrid: bool = True) -> None:
        self.backend = backend or load_backend()
        self.hybrid = hybrid

    # ----------------------------- info ----------------------------------- #
    def describe(self) -> dict:
        info = self.backend.info
        return {
            "backend": info.name,
            "kem_alg": info.kem_alg,
            "sig_alg": info.sig_alg,
            "aead_alg": "AES-256-GCM",
            "pqc_grade": info.pqc_grade,
            "hybrid": self.hybrid,
        }

    # ----------------------------- KEM ------------------------------------ #
    def kem_keypair(self) -> tuple[bytes, bytes]:
        return self.backend.kem_keypair()

    def kem_encaps(self, peer_pk: bytes) -> tuple[bytes, bytes]:
        return self.backend.kem_encaps(peer_pk)

    def kem_decaps(self, sk: bytes, ct: bytes) -> bytes:
        return self.backend.kem_decaps(sk, ct)

    # ----------------------------- SIG ------------------------------------ #
    def sig_keypair(self) -> tuple[bytes, bytes]:
        return self.backend.sig_keypair()

    def sign(self, sk: bytes, msg: bytes) -> bytes:
        return self.backend.sig_sign(sk, msg)

    def verify(self, pk: bytes, msg: bytes, sig: bytes) -> bool:
        return self.backend.sig_verify(pk, msg, sig)

    # ----------------------------- HYBRID --------------------------------- #
    @staticmethod
    def x25519_keypair() -> tuple[bytes, bytes]:
        sk = X25519PrivateKey.generate()
        pk = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        # We export the raw 32-byte sk via a hack-free method: PEM round-trip
        from cryptography.hazmat.primitives.serialization import (
            PrivateFormat, NoEncryption,
        )
        sk_raw = sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        return pk, sk_raw

    @staticmethod
    def x25519_shared(sk_raw: bytes, peer_pk_raw: bytes) -> bytes:
        sk = X25519PrivateKey.from_private_bytes(sk_raw)
        peer = X25519PublicKey.from_public_bytes(peer_pk_raw)
        return sk.exchange(peer)

    # ----------------------------- KDF ------------------------------------ #
    @staticmethod
    def hkdf(ikm: bytes, info: bytes, salt: bytes = b"", length: int = AEAD_KEY_LEN) -> bytes:
        return HKDF(
            algorithm=HKDF_HASH,
            length=length,
            salt=salt,
            info=info,
        ).derive(ikm)

    # ----------------------------- AEAD ----------------------------------- #
    @staticmethod
    def aead_seal(key: bytes, counter: int, plaintext: bytes, aad: bytes = b"") -> bytes:
        nonce = struct.pack(">I", 0) + struct.pack(">Q", counter)  # 12 bytes
        aead = AESGCM(key)
        return aead.encrypt(nonce, plaintext, aad)

    @staticmethod
    def aead_open(key: bytes, counter: int, ciphertext: bytes, aad: bytes = b"") -> bytes:
        nonce = struct.pack(">I", 0) + struct.pack(">Q", counter)
        aead = AESGCM(key)
        return aead.decrypt(nonce, ciphertext, aad)

    # ----------------------------- HANDSHAKE ------------------------------ #
    def derive_session(
        self,
        role: str,
        kem_shared: bytes,
        x_shared: bytes | None,
        transcript: bytes,
        peer_id: str,
        session_id: bytes,
        aead_key_len: int = AEAD_KEY_LEN,
    ) -> TunnelSession:
        """Derive directional keys for a tunnel session.

        send/recv keys are derived from the same IKM with role-distinct info
        labels so client and server agree. `aead_key_len` lets callers choose
        AES-128 (16) or AES-256 (32) per the negotiated suite.
        """
        if x_shared and kem_shared:
            ikm = kem_shared + x_shared
        elif x_shared:
            ikm = x_shared
        else:
            ikm = kem_shared

        info_c2s = b"pqcg/c2s/aead/v1/" + str(aead_key_len).encode()
        info_s2c = b"pqcg/s2c/aead/v1/" + str(aead_key_len).encode()
        c2s = self.hkdf(ikm, info_c2s, transcript, length=aead_key_len)
        s2c = self.hkdf(ikm, info_s2c, transcript, length=aead_key_len)

        if role == "client":
            send_key, recv_key = c2s, s2c
        else:
            send_key, recv_key = s2c, c2s

        import time

        return TunnelSession(
            session_id=session_id,
            peer_id=peer_id,
            send_key=send_key,
            recv_key=recv_key,
            transcript=transcript,
            created_at=time.time(),
        )


# --------------------------------------------------------------------------- #
# singleton accessor
# --------------------------------------------------------------------------- #
@lru_cache
def get_engine() -> PQCEngine:
    from ..config import get_settings

    settings = get_settings()
    return PQCEngine(hybrid=settings.hybrid_classical)
