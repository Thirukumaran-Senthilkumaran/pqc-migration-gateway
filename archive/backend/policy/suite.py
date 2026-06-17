"""Crypto suite registry.

Each suite is a deliberate trade-off between speed/wire-size and quantum
robustness. The policy engine picks one per-session based on traffic scope
and the current threat indicator.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class CryptoSuite(str, enum.Enum):
    CLASSICAL = "classical"             # X25519 + AES-128-GCM (no PQC)
    PQC_COMPRESSED = "pqc-compressed"   # ML-KEM-768 + AES-128-GCM, no sig, no hybrid
    PQC_FULL = "pqc-full"               # ML-KEM-768 + ML-DSA-65 + X25519 + AES-256-GCM


@dataclass(slots=True, frozen=True)
class SuiteParams:
    suite: CryptoSuite
    label: str
    pqc: bool
    use_kem: bool
    use_x25519: bool
    use_signature: bool
    aead_key_len: int                # 16 for AES-128-GCM, 32 for AES-256-GCM
    handshake_bytes: int             # rough on-wire footprint
    description: str
    quantum_safe: str                # "no" / "partial" / "yes"


SUITES: dict[CryptoSuite, SuiteParams] = {
    CryptoSuite.CLASSICAL: SuiteParams(
        suite=CryptoSuite.CLASSICAL,
        label="Classical (X25519 + AES-128-GCM)",
        pqc=False,
        use_kem=False,
        use_x25519=True,
        use_signature=False,
        aead_key_len=16,
        handshake_bytes=64,
        description=(
            "Fast intra-LAN suite. No PQC. Handshake is two 32-byte "
            "X25519 public keys. Use for trusted-segment performance paths."
        ),
        quantum_safe="no",
    ),
    CryptoSuite.PQC_COMPRESSED: SuiteParams(
        suite=CryptoSuite.PQC_COMPRESSED,
        label="Compressed PQC (ML-KEM-768 + AES-128-GCM)",
        pqc=True,
        use_kem=True,
        use_x25519=False,
        use_signature=False,
        aead_key_len=16,
        handshake_bytes=2300,
        description=(
            "Quantum-safe key agreement only — no signature, no hybrid, "
            "AES-128-GCM bulk. ~2.3 KB handshake. Designed for constrained "
            "endpoints and the auto-upgrade-from-classical path."
        ),
        quantum_safe="yes",
    ),
    CryptoSuite.PQC_FULL: SuiteParams(
        suite=CryptoSuite.PQC_FULL,
        label="Full PQC (ML-KEM-768 + ML-DSA-65 + X25519 + AES-256-GCM)",
        pqc=True,
        use_kem=True,
        use_x25519=True,
        use_signature=True,
        aead_key_len=32,
        handshake_bytes=5500,
        description=(
            "Hybrid X25519 + ML-KEM-768 key agreement, ML-DSA-65 mutual "
            "authentication, AES-256-GCM bulk. Default for LAN-WAN crossings "
            "and post-anomaly upgrades."
        ),
        quantum_safe="yes",
    ),
}


def get_suite(s: CryptoSuite | str) -> SuiteParams:
    if isinstance(s, str):
        s = CryptoSuite(s)
    return SUITES[s]
