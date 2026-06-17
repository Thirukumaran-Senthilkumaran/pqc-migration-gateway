#!/usr/bin/env python3
"""
PQC Migration Gateway - LAN Connector  (v2.0)
=============================================

Runs INSIDE your local network. It scans device/crypto metadata (no payloads)
and uploads it to the cloud over HTTPS using a Bearer token you created in the
dashboard.

    Your LAN  ->  connector.py  ->  HTTPS POST /api/ingest  ->  Cloud Dashboard
                                    Authorization: Bearer <token>

Usage
-----
    pip install requests
    python connector.py --token pqcg_XXXXXXXX --url https://your-api.onrender.com

    # scan a specific subnet instead of auto-detect:
    python connector.py --token pqcg_XXXX --url http://127.0.0.1:8000 --subnet 192.168.1.0/24

Only standard-library scanning is used (sockets + TLS). The single third-party
dependency is `requests` for the HTTPS upload.
"""

from __future__ import annotations

import argparse
import ipaddress
import socket
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("This connector needs 'requests'. Install it with:  pip install requests")
    sys.exit(1)

VERSION = "2.0"
COMMON_PORTS = [21, 22, 23, 25, 80, 110, 143, 443, 445, 502, 1883, 3389, 8080, 8443, 8883]
SERVICE_NAMES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 80: "http", 110: "pop3",
    143: "imap", 443: "https", 445: "smb", 502: "modbus", 1883: "mqtt",
    3389: "rdp", 8080: "http-alt", 8443: "https-alt", 8883: "mqtts",
}
WEAK_TLS = {"SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1"}


def detect_subnet() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    a, b, c, _ = ip.split(".")
    return f"{a}.{b}.{c}.0/24"


def probe_port(ip: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def tls_probe(ip: str, port: int) -> tuple[str | None, str | None]:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=2) as sock:
            with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                version = ssock.version() or "unknown"
                cert = ssock.getpeercert()
                cert_type = "x509"
                if cert:
                    sig = cert.get("signatureAlgorithm", "")
                    cert_type = sig.split("With")[0] if sig else "x509"
                return version, cert_type
    except Exception:
        return None, None


def scan_host(ip: str) -> dict | None:
    open_ports = [p for p in COMMON_PORTS if probe_port(ip, p)]
    if not open_ports:
        return None

    tls_version, cert_type = None, None
    for tls_port in (443, 8443, 8883):
        if tls_port in open_ports:
            tls_version, cert_type = tls_probe(ip, tls_port)
            if tls_version:
                break

    primary = open_ports[0]
    hostname = None
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        pass

    return {
        "ip": ip,
        "hostname": hostname,
        "service": SERVICE_NAMES.get(primary, f"port-{primary}"),
        "port": primary,
        "tls_version": tls_version,
        "cert_type": cert_type,
        "weak_protocol": tls_version if tls_version in WEAK_TLS else None,
    }


def scan_network(subnet: str) -> list[dict]:
    net = ipaddress.IPv4Network(subnet, strict=False)
    hosts = [str(h) for h in net.hosts()][:512]
    devices: list[dict] = []
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(scan_host, ip): ip for ip in hosts}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                devices.append(result)
                print(f"  [+] {result['ip']:16} {result['service']}")
    return devices


def post(api_url: str, token: str, payload: dict) -> dict:
    url = api_url.rstrip("/") + "/api/ingest"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if resp.status_code == 401:
        print("[connector] Authentication failed - check your token.")
        sys.exit(2)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="PQC Migration Gateway LAN Connector")
    parser.add_argument("--token", required=True, help="Connector Bearer token from the dashboard")
    parser.add_argument("--url", required=True, help="Cloud API base URL (e.g. https://your-api.onrender.com)")
    parser.add_argument("--subnet", default=None, help="Override subnet, e.g. 192.168.1.0/24")
    args = parser.parse_args()

    subnet = args.subnet or detect_subnet()
    print(f"PQC LAN Connector v{VERSION}")
    print(f"[connector] Target subnet : {subnet}")
    print(f"[connector] Cloud API     : {args.url}")

    post(args.url, args.token, {"type": "heartbeat", "subnet": subnet, "connector_version": VERSION, "devices": []})
    print("[connector] Heartbeat sent. Scanning...")

    devices = scan_network(subnet)
    print(f"[connector] Found {len(devices)} active host(s).")

    result = post(args.url, args.token, {
        "type": "inventory",
        "subnet": subnet,
        "connector_version": VERSION,
        "devices": devices,
    })
    print(f"[connector] Upload complete: {result}")
    print("[connector] Done - open your dashboard to view the inventory.")


if __name__ == "__main__":
    main()
