"""Device classification and inventory logic."""

from __future__ import annotations

from .models import LanDevice

WEAK_TLS = {"SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1"}
SERVICE_RISK = {
    22: ("ssh", 6.0),
    23: ("telnet", 9.5),
    80: ("http", 5.0),
    443: ("https", 4.0),
    502: ("modbus", 9.0),
    1883: ("mqtt", 7.0),
    8883: ("mqtts", 5.5),
}


def classify_device(dev: LanDevice) -> LanDevice:
    risk = dev.risk_score or 5.0
    if dev.tls_version in WEAK_TLS:
        dev.weak_protocol = dev.tls_version
        risk = max(risk, 8.0)
    if dev.port and dev.port in SERVICE_RISK:
        svc, r = SERVICE_RISK[dev.port]
        dev.service = dev.service or svc
        risk = max(risk, r)
    if dev.cert_type and "rsa-1024" in dev.cert_type.lower():
        dev.weak_protocol = (dev.weak_protocol or "") + " weak-rsa"
        risk = max(risk, 7.5)

    dev.risk_score = round(risk, 1)
    if risk >= 8:
        dev.priority_tier = "tier-1"
        dev.pqc_candidate = "wrap-now"
    elif risk >= 5:
        dev.priority_tier = "tier-2"
        dev.pqc_candidate = "gateway-wrap"
    else:
        dev.priority_tier = "tier-3"
        dev.pqc_candidate = "monitor"
    return dev
