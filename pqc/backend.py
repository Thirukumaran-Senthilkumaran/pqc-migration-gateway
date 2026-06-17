"""
Pluggable post-quantum crypto backend.

Two interchangeable implementations share one interface so the rest of the app
never cares which is active:

* ``DemoBackend``  - runs anywhere with no PQC system libraries. Its KEM is a
  functionally-correct (both peers derive the same shared secret) hash-based
  construction sized like ML-KEM-768; its signatures are *real* Ed25519
  (via ``cryptography``) so the tunnel handshake genuinely authenticates.
  It is NOT quantum-safe - it exists to demonstrate the protocol shape and to
  keep the product runnable on Windows / Streamlit Cloud.
* ``OQSBackend``   - real ML-KEM-768 / ML-DSA-65 via liboqs (python ``oqs``) when
  installed. Same interface, genuine quantum-safe primitives.

The symmetric layer (AES-256-GCM) used by the tunnel is always real
(``cryptography``). Selection: env ``PQCG_PQC_BACKEND`` -> liboqs if importable
-> demo.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendInfo:
    name: str
    kem_alg: str
    sig_alg: str
    quantum_safe: bool
    note: str


class PQCBackend:
    """Interface every backend implements."""

    info: BackendInfo

    # KEM (key encapsulation mechanism)
    def kem_keypair(self) -> tuple[bytes, bytes]:  # (public, secret)
        raise NotImplementedError

    def kem_encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:  # (ciphertext, shared_secret)
        raise NotImplementedError

    def kem_decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:  # shared_secret
        raise NotImplementedError

    # Digital signatures
    def sig_keypair(self) -> tuple[bytes, bytes]:  # (public, secret)
        raise NotImplementedError

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        raise NotImplementedError

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#  Demo backend                                                               #
# --------------------------------------------------------------------------- #
class DemoBackend(PQCBackend):
    """Hash-based functional KEM + real Ed25519 signatures. Not quantum-safe."""

    KEM_PK = 1184
    KEM_SK = 2400
    KEM_CT = 1088
    SS_LEN = 32

    info = BackendInfo(
        name="demo",
        kem_alg="ML-KEM-768 (simulated, functional)",
        sig_alg="Ed25519 (classical, real)",
        quantum_safe=False,
        note="Demonstration backend - protocol-faithful and functional, not quantum-safe.",
    )

    @staticmethod
    def _expand(seed: bytes, length: int, tag: bytes) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            out += hashlib.sha512(tag + counter.to_bytes(4, "big") + seed).digest()
            counter += 1
        return bytes(out[:length])

    # --- KEM: functionally correct (matching shared secret), demo-grade security
    def kem_keypair(self) -> tuple[bytes, bytes]:
        seed = secrets.token_bytes(32)
        pk = self._expand(seed, self.KEM_PK, b"kem-pk")
        sk = seed + self._expand(seed, self.KEM_SK - 32, b"kem-sk")
        return pk, sk

    def kem_encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        ephemeral = secrets.token_bytes(32)
        shared = hashlib.sha256(b"pqcg-ss" + ephemeral + public_key).digest()[: self.SS_LEN]
        body = self._expand(ephemeral + public_key, self.KEM_CT - 32, b"kem-ct")
        return ephemeral + body, shared

    def kem_decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        seed = secret_key[:32]
        public_key = self._expand(seed, self.KEM_PK, b"kem-pk")
        ephemeral = ciphertext[:32]
        return hashlib.sha256(b"pqcg-ss" + ephemeral + public_key).digest()[: self.SS_LEN]

    # --- Signatures: real Ed25519 so handshake authentication actually verifies
    def sig_keypair(self) -> tuple[bytes, bytes]:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization

        priv = Ed25519PrivateKey.generate()
        sk = priv.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        pk = priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return pk, sk

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv = Ed25519PrivateKey.from_private_bytes(secret_key)
        return priv.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature

        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            return True
        except (InvalidSignature, Exception):
            return False


# --------------------------------------------------------------------------- #
#  liboqs backend - real ML-KEM / ML-DSA when available                       #
# --------------------------------------------------------------------------- #
class OQSBackend(PQCBackend):
    info = BackendInfo(
        name="liboqs",
        kem_alg="ML-KEM-768",
        sig_alg="ML-DSA-65",
        quantum_safe=True,
        note="Real NIST PQC primitives via liboqs.",
    )

    _KEM = "ML-KEM-768"
    _SIG = "ML-DSA-65"

    def __init__(self) -> None:
        import oqs

        self._oqs = oqs

    def kem_keypair(self) -> tuple[bytes, bytes]:
        with self._oqs.KeyEncapsulation(self._KEM) as kem:
            pk = kem.generate_keypair()
            return pk, kem.export_secret_key()

    def kem_encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        with self._oqs.KeyEncapsulation(self._KEM) as kem:
            return kem.encap_secret(public_key)

    def kem_decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        with self._oqs.KeyEncapsulation(self._KEM, secret_key=secret_key) as kem:
            return kem.decap_secret(ciphertext)

    def sig_keypair(self) -> tuple[bytes, bytes]:
        with self._oqs.Signature(self._SIG) as sig:
            pk = sig.generate_keypair()
            return pk, sig.export_secret_key()

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        with self._oqs.Signature(self._SIG, secret_key=secret_key) as sig:
            return sig.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        with self._oqs.Signature(self._SIG) as sig:
            return bool(sig.verify(message, signature, public_key))


_CACHED: PQCBackend | None = None


def available_backends() -> list[str]:
    backends = ["demo"]
    try:
        import oqs  # noqa: F401

        backends.insert(0, "liboqs")
    except Exception:
        pass
    return backends


def get_backend(name: str | None = None) -> PQCBackend:
    """Return a backend instance. Honors ``PQCG_PQC_BACKEND`` then auto-detects."""
    global _CACHED
    choice = (name or os.getenv("PQCG_PQC_BACKEND", "auto")).lower()

    if choice in ("liboqs", "oqs", "real"):
        return OQSBackend()
    if choice == "demo":
        return DemoBackend()

    if _CACHED is not None and name is None:
        return _CACHED
    try:
        backend: PQCBackend = OQSBackend()
    except Exception:
        backend = DemoBackend()
    if name is None:
        _CACHED = backend
    return backend
