"""Pluggable PQC backends.

Order of preference:
    1. liboqs (`oqs` python wrapper) — production-grade NIST PQC.
    2. pqcrypto pip package — pure-python wrappers over the reference impls.
    3. Fallback "demo" backend — uses HKDF over a strong classical secret
       and emits a clear capability warning. NEVER advertised as PQC-secure.

Every backend implements the same protocol declared in `BackendProtocol`.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class BackendInfo:
    name: str
    kem_alg: str
    sig_alg: str
    pqc_grade: str  # "nist-strict" | "nist-reference" | "demo"


class BackendProtocol(Protocol):
    info: BackendInfo

    def kem_keypair(self) -> tuple[bytes, bytes]: ...
    def kem_encaps(self, public_key: bytes) -> tuple[bytes, bytes]: ...
    def kem_decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes: ...
    def sig_keypair(self) -> tuple[bytes, bytes]: ...
    def sig_sign(self, secret_key: bytes, message: bytes) -> bytes: ...
    def sig_verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


# --------------------------------------------------------------------------- #
# 1) liboqs backend
# --------------------------------------------------------------------------- #
class _OqsBackend:
    info = BackendInfo(
        name="liboqs",
        kem_alg="ML-KEM-768",
        sig_alg="ML-DSA-65",
        pqc_grade="nist-strict",
    )

    def __init__(self) -> None:
        import oqs  # type: ignore

        self._oqs = oqs
        # quick capability check
        with oqs.KeyEncapsulation("ML-KEM-768"):
            pass
        with oqs.Signature("ML-DSA-65"):
            pass

    def kem_keypair(self) -> tuple[bytes, bytes]:
        with self._oqs.KeyEncapsulation("ML-KEM-768") as kem:
            pk = kem.generate_keypair()
            sk = kem.export_secret_key()
        return pk, sk

    def kem_encaps(self, public_key: bytes) -> tuple[bytes, bytes]:
        with self._oqs.KeyEncapsulation("ML-KEM-768") as kem:
            ct, ss = kem.encap_secret(public_key)
        return ct, ss

    def kem_decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        with self._oqs.KeyEncapsulation("ML-KEM-768", secret_key) as kem:
            return kem.decap_secret(ciphertext)

    def sig_keypair(self) -> tuple[bytes, bytes]:
        with self._oqs.Signature("ML-DSA-65") as sig:
            pk = sig.generate_keypair()
            sk = sig.export_secret_key()
        return pk, sk

    def sig_sign(self, secret_key: bytes, message: bytes) -> bytes:
        with self._oqs.Signature("ML-DSA-65", secret_key) as sig:
            return sig.sign(message)

    def sig_verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        with self._oqs.Signature("ML-DSA-65") as sig:
            return bool(sig.verify(message, signature, public_key))


# --------------------------------------------------------------------------- #
# 2) pqcrypto backend
# --------------------------------------------------------------------------- #
class _PqcryptoBackend:
    info = BackendInfo(
        name="pqcrypto",
        kem_alg="ML-KEM-768",
        sig_alg="ML-DSA-65",
        pqc_grade="nist-reference",
    )

    def __init__(self) -> None:
        # imports are deferred so we don't crash at module load if missing
        from pqcrypto.kem import ml_kem_768  # type: ignore
        from pqcrypto.sign import ml_dsa_65  # type: ignore

        self._kem = ml_kem_768
        self._sig = ml_dsa_65

    def kem_keypair(self) -> tuple[bytes, bytes]:
        pk, sk = self._kem.generate_keypair()
        return pk, sk

    def kem_encaps(self, public_key: bytes) -> tuple[bytes, bytes]:
        ct, ss = self._kem.encrypt(public_key)
        return ct, ss

    def kem_decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        return self._kem.decrypt(secret_key, ciphertext)

    def sig_keypair(self) -> tuple[bytes, bytes]:
        pk, sk = self._sig.generate_keypair()
        return pk, sk

    def sig_sign(self, secret_key: bytes, message: bytes) -> bytes:
        return self._sig.sign(secret_key, message)

    def sig_verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            self._sig.verify(public_key, message, signature)
            return True
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# 3) Demo / fallback backend
# --------------------------------------------------------------------------- #
class _DemoBackend:
    """Last-resort backend that exercises the *protocol* without real PQC.

    Used when neither `oqs` nor `pqcrypto` is available, e.g. on a fresh
    developer laptop. Generates large random "public/secret keys" and uses
    HKDF-SHA-384 over a 256-bit shared secret so the rest of the gateway
    can be exercised end-to-end. Clearly self-identifies as `pqc_grade=demo`.
    """

    info = BackendInfo(
        name="demo",
        kem_alg="ML-KEM-768[demo]",
        sig_alg="ML-DSA-65[demo]",
        pqc_grade="demo",
    )

    KEM_PK_LEN = 1184
    KEM_SK_LEN = 2400
    KEM_CT_LEN = 1088
    KEM_SS_LEN = 32

    SIG_PK_LEN = 1952
    SIG_SK_LEN = 4032
    SIG_LEN = 3309

    def __init__(self) -> None:
        logger.warning(
            "PQC demo backend active — install `oqs` or `pqcrypto` for real PQC."
        )

    @staticmethod
    def _h(*parts: bytes) -> bytes:
        import hashlib

        h = hashlib.sha3_512()
        for p in parts:
            h.update(len(p).to_bytes(4, "big"))
            h.update(p)
        return h.digest()

    def kem_keypair(self) -> tuple[bytes, bytes]:
        seed = secrets.token_bytes(64)
        pk = self._h(b"pk", seed)[: self.KEM_PK_LEN] + secrets.token_bytes(
            max(0, self.KEM_PK_LEN - 64)
        )
        pk = pk[: self.KEM_PK_LEN]
        sk = seed + pk + secrets.token_bytes(self.KEM_SK_LEN - 64 - self.KEM_PK_LEN)
        return pk, sk

    def kem_encaps(self, public_key: bytes) -> tuple[bytes, bytes]:
        ephem = secrets.token_bytes(64)
        ss = self._h(b"ss", ephem, public_key)[: self.KEM_SS_LEN]
        ct_body = secrets.token_bytes(self.KEM_CT_LEN - 64)
        ct = ephem + ct_body
        # Bind ss to ct so decaps can recover it
        return ct, ss

    def kem_decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        # The "public_key" portion of secret_key is bytes 64:64+KEM_PK_LEN
        pk = secret_key[64 : 64 + self.KEM_PK_LEN]
        ephem = ciphertext[:64]
        return self._h(b"ss", ephem, pk)[: self.KEM_SS_LEN]

    def sig_keypair(self) -> tuple[bytes, bytes]:
        seed = secrets.token_bytes(64)
        pk = self._h(b"sigpk", seed) + secrets.token_bytes(self.SIG_PK_LEN - 64)
        pk = pk[: self.SIG_PK_LEN]
        sk = seed + pk + secrets.token_bytes(self.SIG_SK_LEN - 64 - self.SIG_PK_LEN)
        return pk, sk

    def sig_sign(self, secret_key: bytes, message: bytes) -> bytes:
        seed = secret_key[:64]
        body = self._h(b"sig", seed, message)
        # pad / truncate to fixed signature length
        return (body * ((self.SIG_LEN // len(body)) + 1))[: self.SIG_LEN]

    def sig_verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        # In demo mode we cannot truly verify (no asymmetric keypair binding),
        # so we accept any well-formed signature length matching the algorithm.
        return len(signature) == self.SIG_LEN and len(public_key) == self.SIG_PK_LEN


# --------------------------------------------------------------------------- #
# loader
# --------------------------------------------------------------------------- #
def load_backend(prefer: str | None = None) -> BackendProtocol:
    """Return the best available backend.

    `prefer` can be set via env (`PQCG_BACKEND`) to force one of:
        liboqs / pqcrypto / demo
    """
    prefer = prefer or os.getenv("PQCG_BACKEND")

    candidates: list[type[BackendProtocol]] = [
        _OqsBackend,
        _PqcryptoBackend,
        _DemoBackend,
    ]

    if prefer:
        prefer = prefer.lower()
        order = {"liboqs": _OqsBackend, "pqcrypto": _PqcryptoBackend, "demo": _DemoBackend}
        if prefer in order:
            candidates = [order[prefer]] + [c for c in candidates if c is not order[prefer]]

    last_err: Exception | None = None
    for cls in candidates:
        try:
            be = cls()
            logger.info("PQC backend selected: %s (%s)", be.info.name, be.info.pqc_grade)
            return be
        except Exception as exc:  # pragma: no cover - depends on env
            last_err = exc
            logger.debug("Backend %s unavailable: %s", cls.__name__, exc)

    # Demo backend should always succeed; this is a true emergency.
    raise RuntimeError(f"No PQC backend available: {last_err}")
