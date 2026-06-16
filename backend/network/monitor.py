"""In-memory traffic monitor.

Tracks two independent series, both bucketed per second:

    bytes_in / bytes_out   — bytes through the PQC tunnels (gateway sessions).
    nic_in / nic_out       — raw NIC counters of the active LAN interface.

The ratio bytes / nic gives a live "PQC coverage" indicator on the dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 300  # keep last 5 minutes


@dataclass(slots=True)
class Sample:
    ts: float
    bytes_in: int = 0     # PQC tunnel bytes
    bytes_out: int = 0    # PQC tunnel bytes
    frames: int = 0
    nic_in: int = 0       # NIC observed bytes (last second)
    nic_out: int = 0


class TrafficMonitor:
    def __init__(self) -> None:
        self._samples: deque[Sample] = deque(maxlen=WINDOW_SECONDS)
        self._current = Sample(ts=int(time.time()))
        self._lock = asyncio.Lock()
        self._listeners: list[asyncio.Queue] = []
        self._nic_task: asyncio.Task | None = None
        self._last_nic_in: int | None = None
        self._last_nic_out: int | None = None
        self._nic_name: str | None = None

    # --------------------------------------------------------------------- #
    # PQC tunnel inputs (called from gateway pumps)
    # --------------------------------------------------------------------- #
    def add_in(self, n: int) -> None:
        self._roll()
        self._current.bytes_in += n
        self._current.frames += 1

    def add_out(self, n: int) -> None:
        self._roll()
        self._current.bytes_out += n
        self._current.frames += 1

    # --------------------------------------------------------------------- #
    # NIC observation poller
    # --------------------------------------------------------------------- #
    async def start_nic_poller(self) -> None:
        if self._nic_task is None:
            self._nic_task = asyncio.create_task(
                self._nic_loop(), name="nic-poller"
            )
            logger.info("Traffic monitor NIC poller started.")

    async def stop_nic_poller(self) -> None:
        if self._nic_task:
            self._nic_task.cancel()
            try:
                await self._nic_task
            except (asyncio.CancelledError, Exception):
                pass
            self._nic_task = None

    async def _nic_loop(self) -> None:
        # Lazy import: avoid a circular import at module load.
        from .discovery import detect_active_interface, get_discovery

        announced: str | None = None
        try:
            while True:
                try:
                    # Prefer discovery's choice (so it matches the dashboard);
                    # fall back to fresh detection so the poller works even
                    # before the first discovery scan finishes.
                    iface = get_discovery().interface or detect_active_interface()

                    if iface is not None:
                        counters = psutil.net_io_counters(pernic=True)
                        c = counters.get(iface.name)
                        if c is None:
                            # Windows occasionally hands back differently-cased
                            # adapter names — try a case-insensitive match.
                            for k, v in counters.items():
                                if k.lower() == iface.name.lower():
                                    c = v
                                    break

                        if c is not None:
                            if announced != iface.name:
                                logger.info(
                                    "NIC poller watching %s "
                                    "(baseline rx=%d tx=%d)",
                                    iface.name, c.bytes_recv, c.bytes_sent,
                                )
                                announced = iface.name

                            if self._nic_name != iface.name:
                                # interface changed — reset baseline
                                self._last_nic_in = c.bytes_recv
                                self._last_nic_out = c.bytes_sent
                                self._nic_name = iface.name
                            else:
                                d_in = max(
                                    0,
                                    c.bytes_recv - (self._last_nic_in or c.bytes_recv),
                                )
                                d_out = max(
                                    0,
                                    c.bytes_sent - (self._last_nic_out or c.bytes_sent),
                                )
                                self._last_nic_in = c.bytes_recv
                                self._last_nic_out = c.bytes_sent
                                self._roll()
                                self._current.nic_in += d_in
                                self._current.nic_out += d_out
                        else:
                            logger.debug(
                                "NIC %s not present in psutil counters: %s",
                                iface.name, list(counters.keys()),
                            )
                    else:
                        logger.debug("NIC poller: no active interface yet.")
                except Exception as e:
                    logger.debug("nic poll: %s", e)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return

    # --------------------------------------------------------------------- #
    # bucket roller
    # --------------------------------------------------------------------- #
    def _roll(self) -> None:
        now = int(time.time())
        if now != self._current.ts:
            # If we skipped seconds (e.g., long sleep), pad with empty buckets
            for sec in range(self._current.ts + 1, now):
                empty = Sample(ts=sec)
                self._samples.append(empty)
                self._fanout(empty)
            self._samples.append(self._current)
            self._fanout(self._current)
            self._current = Sample(ts=now)

    def _fanout(self, s: Sample) -> None:
        for q in list(self._listeners):
            try:
                q.put_nowait(s)
            except asyncio.QueueFull:
                pass

    def snapshot(self) -> list[Sample]:
        self._roll()
        return list(self._samples)

    def total_bytes(self) -> int:
        return sum(s.bytes_in + s.bytes_out for s in self._samples) + (
            self._current.bytes_in + self._current.bytes_out
        )

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)


_monitor_singleton: TrafficMonitor | None = None


def get_monitor() -> TrafficMonitor:
    global _monitor_singleton
    if _monitor_singleton is None:
        _monitor_singleton = TrafficMonitor()
    return _monitor_singleton
