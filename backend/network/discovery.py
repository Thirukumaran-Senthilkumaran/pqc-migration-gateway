"""LAN discovery service.

Strategy (cross-platform, no admin / WinPcap required for the basic mode):

1.  Determine the active interface and CIDR using `psutil` + `socket`.
2.  ICMP-style "ping" via TCP-SYN attempts on common ports for every host
    in the subnet (small ranges only — large /16's are sampled).
3.  Read the OS ARP cache afterwards (`arp -a` on Windows, `ip neigh` on
    Linux, `arp -a` on macOS) to harvest MAC addresses.
4.  Try a reverse DNS / NetBIOS / mDNS hostname resolution.
5.  Persist into the `nodes` table; emit `node.seen` events.

This avoids requiring scapy / npcap on Windows, which would break the
plug-and-play promise.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import platform
import re
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import psutil
from sqlalchemy import select

from ..config import get_settings
from ..database import session_scope
from ..models import Node, NodeStatus

logger = logging.getLogger(__name__)
settings = get_settings()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class InterfaceInfo:
    name: str
    ip: str
    netmask: str
    cidr: str
    is_virtual: bool = False

    @property
    def network(self) -> ipaddress.IPv4Network:
        return ipaddress.IPv4Network(self.cidr, strict=False)


# Substrings that mark an adapter as a virtual / VM / WSL / loopback shim.
_VIRTUAL_NAME_HINTS = (
    "vmware", "virtualbox", "vbox", "vethernet",
    "wsl", "hyper-v", "hyperv", "loopback",
    "tunnel", "tap-", "tap windows", "docker",
    "bluetooth", "teredo",
)


def _primary_ip_via_default_route() -> str | None:
    """Ask the OS which local IPv4 would be used to reach the internet.

    This works without sending a packet — `connect()` on UDP just resolves
    the route. The returned IP is, by definition, on the interface that owns
    the default route (which is the real LAN, not a VM-only adapter).
    """
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def _is_virtual_name(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _VIRTUAL_NAME_HINTS)


def _enumerate_candidates() -> list[InterfaceInfo]:
    out: list[InterfaceInfo] = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for name, infos in addrs.items():
        st = stats.get(name)
        if not st or not st.isup:
            continue
        for a in infos:
            if a.family != socket.AF_INET:
                continue
            ip = a.address
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            netmask = a.netmask or "255.255.255.0"
            try:
                net = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            except ValueError:
                continue
            out.append(
                InterfaceInfo(
                    name=name,
                    ip=ip,
                    netmask=netmask,
                    cidr=str(net),
                    is_virtual=_is_virtual_name(name),
                )
            )
    return out


def detect_active_interface() -> InterfaceInfo | None:
    """Pick the LAN interface that actually reaches the internet/gateway.

    Strategy:
        1. If `PQCG_DISCOVERY_INTERFACE` is set, honour it.
        2. Use the OS default-route trick → match its IP back to a NIC.
        3. Fall back to a scoring heuristic that strongly down-weights
           virtual adapters (VMware/VirtualBox/WSL/Hyper-V/etc).
    """
    candidates = _enumerate_candidates()
    if not candidates:
        return None

    # 1) explicit operator override
    forced = settings.discovery_interface
    if forced:
        for c in candidates:
            if c.name.lower() == forced.lower():
                logger.info("Using forced interface %s (%s)", c.name, c.ip)
                return c
        logger.warning(
            "Forced interface '%s' not found; falling back to auto-detect.", forced
        )

    # 2) default-route match
    primary_ip = _primary_ip_via_default_route()
    if primary_ip:
        for c in candidates:
            if c.ip == primary_ip:
                logger.info(
                    "Active interface (via default route): %s %s",
                    c.name, c.cidr,
                )
                return c

    # 3) scoring fallback — virtual adapters get heavily penalised
    def score(iface: InterfaceInfo) -> int:
        s = 0
        if not iface.is_virtual:
            s += 100
        ip = iface.ip
        if ip.startswith("192.168."):
            s += 3
        elif ip.startswith("10."):
            s += 2
        elif ip.startswith("172."):
            try:
                second = int(ip.split(".")[1])
                if 16 <= second <= 31:
                    s += 2
            except ValueError:
                pass
        else:
            s += 1
        return s

    candidates.sort(key=score, reverse=True)
    chosen = candidates[0]
    logger.info(
        "Active interface (heuristic): %s %s (virtual=%s)",
        chosen.name, chosen.cidr, chosen.is_virtual,
    )
    return chosen


# --------------------------------------------------------------------------- #
# ARP cache reader (cross-platform)
# --------------------------------------------------------------------------- #
_MAC_RE = re.compile(r"(?P<mac>[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5})")
_IP_RE = re.compile(r"(?P<ip>\d{1,3}(\.\d{1,3}){3})")


def read_arp_cache() -> dict[str, str]:
    """Return {ip: mac} from the local ARP cache."""
    out: dict[str, str] = {}
    sysname = platform.system().lower()
    try:
        if sysname == "windows":
            res = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            )
        elif sysname == "darwin":
            res = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            )
        else:
            res = subprocess.run(
                ["ip", "neigh"], capture_output=True, text=True, timeout=10
            )
        if res.returncode != 0:
            logger.debug("ARP cache command failed: %s", res.stderr)
            return out
        for line in res.stdout.splitlines():
            ip_m = _IP_RE.search(line)
            mac_m = _MAC_RE.search(line)
            if ip_m and mac_m:
                ip = ip_m.group("ip")
                mac = mac_m.group("mac").lower().replace("-", ":")
                if mac == "00:00:00:00:00:00" or mac == "ff:ff:ff:ff:ff:ff":
                    continue
                out[ip] = mac
    except Exception as e:  # pragma: no cover
        logger.warning("Failed to read ARP cache: %s", e)
    return out


# --------------------------------------------------------------------------- #
# probe (TCP-connect, port-connect, hostname)
# --------------------------------------------------------------------------- #
async def _tcp_probe(ip: str, port: int, timeout: float = 0.5) -> bool:
    try:
        fut = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(fut, timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _is_alive(ip: str, ports: Iterable[int]) -> tuple[bool, list[int]]:
    """Return (alive, [open_ports])."""
    open_ports: list[int] = []
    tasks = [asyncio.create_task(_tcp_probe(ip, p)) for p in ports]
    results = await asyncio.gather(*tasks)
    for port, hit in zip(ports, results):
        if hit:
            open_ports.append(port)
    return (bool(open_ports), open_ports)


def _resolve_hostname(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


def _vendor_from_mac(mac: str) -> str | None:
    """Lightweight OUI guess (no external DB) — flags major vendors only."""
    oui = mac.replace(":", "").replace("-", "").lower()[:6]
    table = {
        "001ec2": "Apple",
        "f0f61c": "Apple",
        "001a11": "Google",
        "84d6d0": "Microsoft",
        "0050f2": "Microsoft",
        "b827eb": "Raspberry Pi",
        "dca632": "Raspberry Pi",
        "fcfbfb": "Cisco",
        "00aabb": "Espressif",
        "ec1bbd": "Espressif",
        "001bc5": "Honeywell",
        "00a0a4": "Siemens",
        "001745": "Schneider Electric",
    }
    return table.get(oui)


# --------------------------------------------------------------------------- #
# DiscoveryService
# --------------------------------------------------------------------------- #
class DiscoveryService:
    """Background task that periodically scans the LAN."""

    def __init__(self) -> None:
        self.running = False
        self.last_run: datetime | None = None
        self.interface: InterfaceInfo | None = None
        self.found_count: int = 0
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._listeners: list[asyncio.Queue] = []

    # ----------------------------- public API ----------------------------- #
    async def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self.running = True
        # Detect the active interface immediately so the NIC poller, the API
        # and the UI have an answer well before the first full scan finishes.
        try:
            self.interface = detect_active_interface()
        except Exception as e:  # pragma: no cover
            logger.warning("Initial interface detection failed: %s", e)
        self._task = asyncio.create_task(self._loop(), name="discovery-loop")
        logger.info("Discovery service started.")

    async def stop(self) -> None:
        if not self.running:
            return
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.running = False
        logger.info("Discovery service stopped.")

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._listeners.append(q)
        return q

    async def status(self) -> dict:
        return {
            "running": self.running,
            "last_run": self.last_run,
            "interface": self.interface.name if self.interface else None,
            "subnet": self.interface.cidr if self.interface else None,
            "nodes_found": self.found_count,
        }

    async def trigger_now(self, subnet_override: str | None = None) -> int:
        return await self._run_one(subnet_override)

    # ----------------------------- internals ------------------------------ #
    async def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await self._run_one()
                except Exception as e:
                    logger.exception("Discovery iteration failed: %s", e)
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=settings.discovery_interval_sec
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            return

    async def _run_one(self, subnet_override: str | None = None) -> int:
        # Re-detect every cycle so adapter changes (e.g. Wi-Fi reconnect,
        # VPN up/down) are picked up automatically.
        self.interface = detect_active_interface()
        if not self.interface:
            logger.warning("No active LAN interface found; discovery skipped.")
            return 0

        subnet = subnet_override or settings.discovery_subnet or self.interface.cidr
        try:
            net = ipaddress.IPv4Network(subnet, strict=False)
        except ValueError:
            logger.error("Invalid subnet: %s", subnet)
            return 0

        if net.num_addresses > 4096:
            logger.warning(
                "Subnet %s is large (%d hosts); sampling first /22.",
                subnet, net.num_addresses,
            )
            net = ipaddress.IPv4Network(f"{net.network_address}/22", strict=False)

        logger.info("Discovery scan: subnet=%s ports=%s", net, settings.common_ports)
        targets = [str(h) for h in net.hosts()]

        # bounded concurrency
        sem = asyncio.Semaphore(128)

        async def worker(ip: str) -> tuple[str, list[int]] | None:
            async with sem:
                alive, ports = await _is_alive(ip, settings.common_ports)
                if alive:
                    return ip, ports
            return None

        results = await asyncio.gather(*(worker(ip) for ip in targets))
        alive_hosts = [r for r in results if r]

        arp = read_arp_cache()
        # Always include the local IP in arp map
        arp.setdefault(self.interface.ip, "00:00:00:00:00:00")

        seen = 0
        async with session_scope() as db:
            for ip, ports in alive_hosts:
                mac = arp.get(ip) or _synthetic_mac(ip)
                hostname = _resolve_hostname(ip)
                vendor = _vendor_from_mac(mac)

                row = (await db.execute(select(Node).where(Node.mac == mac))).scalar_one_or_none()
                ports_csv = ",".join(str(p) for p in ports)
                if row is None:
                    row = Node(
                        mac=mac,
                        ip=ip,
                        hostname=hostname,
                        vendor=vendor,
                        open_ports=ports_csv,
                        status=NodeStatus.ONLINE,
                    )
                    db.add(row)
                else:
                    row.ip = ip
                    row.hostname = hostname or row.hostname
                    row.vendor = vendor or row.vendor
                    row.open_ports = ports_csv
                    row.status = NodeStatus.ONLINE
                    row.last_seen = datetime.now(timezone.utc)
                seen += 1

            # Mark stale nodes offline (last_seen older than 3 cycles)
            cutoff = datetime.now(timezone.utc).timestamp() - settings.discovery_interval_sec * 3
            stale = (await db.execute(select(Node))).scalars().all()
            for n in stale:
                if n.last_seen.replace(tzinfo=timezone.utc).timestamp() < cutoff:
                    n.status = NodeStatus.OFFLINE

        self.last_run = datetime.now(timezone.utc)
        self.found_count = seen

        for q in list(self._listeners):
            try:
                q.put_nowait({"type": "discovery", "found": seen})
            except asyncio.QueueFull:
                pass

        logger.info("Discovery complete: %d alive nodes", seen)
        return seen


def _synthetic_mac(ip: str) -> str:
    """Stable synthetic MAC when ARP didn't populate (e.g., first contact)."""
    import hashlib

    h = hashlib.md5(ip.encode()).hexdigest()
    parts = ["02"] + [h[i : i + 2] for i in range(0, 10, 2)]
    return ":".join(parts)


# --------------------------------------------------------------------------- #
# singleton
# --------------------------------------------------------------------------- #
_service_singleton: DiscoveryService | None = None


def get_discovery() -> DiscoveryService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = DiscoveryService()
    return _service_singleton
