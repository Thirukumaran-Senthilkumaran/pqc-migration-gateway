#!/usr/bin/env python3
"""
PQC Cloud Gateway — LAN Connector v1.0

Run inside your local network to scan devices and upload inventory to the cloud.

Usage:
    python connector.py --token pqcg_YOUR_TOKEN --url https://your-api.example.com

Requires: Python 3.9+, requests (pip install requests)
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import platform
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

COMMON_PORTS = [22, 23, 80, 443, 502, 1883, 8080, 8443, 8883]
VERSION = "1.0"


def detect_subnet() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


def probe_port(ip: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def tls_probe(ip: str, port: int = 443) -> tuple[str | None, str | None]:
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=2) as sock:
            with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                ver = ssock.version() or "unknown"
                cert = ssock.getpeercert()
                ctype = "unknown"
                if cert:
                    sig = cert.get("signatureAlgorithm", "")
                    ctype = sig.split("With")[0] if sig else "x509"
                weak = ver in ("SSLv3", "TLSv1", "TLSv1.1")
                return ver, ("weak-tls" if weak else ctype)
    except Exception:
        return None, None


def scan_host(ip: str) -> dict | None:
    open_ports = [p for p in COMMON_PORTS if probe_port(ip, p)]
    if not open_ports:
        return None
    tls_ver, cert_type = None, None
    if 443 in open_ports:
        tls_ver, cert_type = tls_probe(ip, 443)
    elif 8443 in open_ports:
        tls_ver, cert_type = tls_probe(ip, 8443)
    service = {22: "ssh", 80: "http", 443: "https", 502: "modbus", 1883: "mqtt"}.get(
        open_ports[0], f"port-{open_ports[0]}"
    )
    hostname = None
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        pass
    return {
        "ip": ip,
        "hostname": hostname,
        "service": service,
        "port": open_ports[0],
        "tls_version": tls_ver,
        "cert_type": cert_type,
        "weak_protocol": tls_ver if tls_ver in ("SSLv3", "TLSv1", "TLSv1.1") else None,
        "vendor": platform.system(),
    }


def scan_network(subnet: str) -> list[dict]:
    net = ipaddress.IPv4Network(subnet, strict=False)
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 512:
        hosts = hosts[:512]
    devices = []
    with ThreadPoolExecutor(max_workers=64) as pool:
        futs = {pool.submit(scan_host, ip): ip for ip in hosts}
        for fut in as_completed(futs):
            result = fut.result()
            if result:
                devices.append(result)
    return devices


def post(api_url: str, token: str, payload: dict) -> dict:
    url = api_url.rstrip("/") + "/api/ingest"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="PQC Cloud Gateway LAN Connector")
    parser.add_argument("--token", required=True, help="Connector Bearer token from dashboard")
    parser.add_argument("--url", required=True, help="Cloud API base URL")
    parser.add_argument("--subnet", default=None, help="Override subnet e.g. 192.168.1.0/24")
    args = parser.parse_args()

    subnet = args.subnet or detect_subnet()
    print(f"[connector] Scanning {subnet} ...")
    devices = scan_network(subnet)
    print(f"[connector] Found {len(devices)} active hosts")

    # heartbeat first
    post(args.url, args.token, {
        "type": "heartbeat",
        "subnet": subnet,
        "connector_version": VERSION,
        "devices": [],
    })
    print("[connector] Heartbeat sent")

    result = post(args.url, args.token, {
        "type": "inventory",
        "subnet": subnet,
        "connector_version": VERSION,
        "devices": devices,
    })
    print(f"[connector] Inventory uploaded: {result}")
    print("[connector] Done. Check your cloud dashboard.")


if __name__ == "__main__":
    main()
