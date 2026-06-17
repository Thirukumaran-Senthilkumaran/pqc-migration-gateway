"""Device risk classification and PQC priority tiering."""

from __future__ import annotations

from ..models import LanDevice

WEAK_TLS = {"SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1"}

# port -> (service name, baseline risk)
SERVICE_RISK = {
    21: ("ftp", 8.0),
    22: ("ssh", 6.0),
    23: ("telnet", 9.5),
    25: ("smtp", 6.5),
    80: ("http", 5.0),
    110: ("pop3", 6.5),
    143: ("imap", 6.0),
    443: ("https", 4.0),
    445: ("smb", 8.5),
    502: ("modbus", 9.0),
    1883: ("mqtt", 7.0),
    3389: ("rdp", 8.0),
    8080: ("http-alt", 5.0),
    8443: ("https-alt", 4.5),
    8883: ("mqtts", 5.5),
}

# PQC candidate algorithm suggestion by service class
PQC_SUGGESTION = {
    "https": "ML-KEM-768 + ML-DSA-65 (TLS hybrid)",
    "https-alt": "ML-KEM-768 + ML-DSA-65 (TLS hybrid)",
    "ssh": "ML-KEM-768 (SSH hybrid KEX)",
    "mqtts": "ML-KEM-768 (TLS hybrid)",
    "mqtt": "Gateway wrap (no native TLS)",
    "modbus": "Gateway wrap (legacy OT)",
    "telnet": "Gateway wrap + decommission plan",
    "http": "Gateway wrap (no TLS)",
}


def classify_device(dev: LanDevice) -> LanDevice:
    risk = dev.risk_score or 5.0

    if dev.port and dev.port in SERVICE_RISK:
        svc, base = SERVICE_RISK[dev.port]
        dev.service = dev.service or svc
        risk = max(risk, base)

    if dev.tls_version in WEAK_TLS:
        dev.weak_protocol = dev.tls_version
        risk = max(risk, 8.0)

    if dev.cert_type:
        ct = dev.cert_type.lower()
        if "rsa-1024" in ct or "sha1" in ct or "weak" in ct:
            dev.weak_protocol = (dev.weak_protocol or "weak-cert")
            risk = max(risk, 7.5)

    dev.risk_score = round(min(risk, 10.0), 1)

    if dev.risk_score >= 8:
        dev.priority_tier = "tier-1"
    elif dev.risk_score >= 5:
        dev.priority_tier = "tier-2"
    else:
        dev.priority_tier = "tier-3"

    dev.pqc_candidate = PQC_SUGGESTION.get(dev.service or "", "Gateway wrap")
    return dev
