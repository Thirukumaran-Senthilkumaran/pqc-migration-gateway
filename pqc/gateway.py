"""
Live PQC gateway proxy (socket level).

Topology for protecting a legacy device:

    legacy client --plaintext--> [ingress gateway] ==PQC tunnel==> [egress gateway] --plaintext--> server

This module provides both ends plus a self-contained loopback demo so the
mechanism is verifiable on a single machine (and described in the LLD).
"""

from __future__ import annotations

import socket
import struct
import threading

from .tunnel import ServerIdentity, client_handshake, server_handshake


def send_frame(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_frame(sock: socket.socket) -> bytes | None:
    header = _recv_exact(sock, 4)
    if header is None:
        return None
    (n,) = struct.unpack(">I", header)
    return _recv_exact(sock, n)


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


class EgressGateway:
    """
    Listens for PQC-tunnelled connections, decrypts, and forwards plaintext to an
    upstream TCP service. Runs in a background thread.
    """

    def __init__(self, listen_host: str, listen_port: int, upstream_host: str, upstream_port: int):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.upstream = (upstream_host, upstream_port)
        self.identity = ServerIdentity()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> int:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.listen_host, self.listen_port))
        self._sock.listen(8)
        self.listen_port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self.listen_port

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            hello, finish = server_handshake(self.identity)
            send_frame(conn, hello)
            kem_ct = recv_frame(conn)
            if kem_ct is None:
                return
            result = finish(kem_ct)
            channel = result.channel

            upstream = socket.create_connection(self.upstream, timeout=10)
            try:
                while True:
                    record = recv_frame(conn)
                    if record is None:
                        break
                    plaintext = channel.open(record)
                    upstream.sendall(plaintext)
                    upstream.settimeout(2)
                    try:
                        reply = upstream.recv(65536)
                    except socket.timeout:
                        reply = b""
                    if reply:
                        send_frame(conn, channel.seal(reply))
            finally:
                upstream.close()
        except Exception:
            pass
        finally:
            conn.close()


class IngressClient:
    """Client side: opens a PQC tunnel to an EgressGateway and exchanges records."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port), timeout=10)
        hello = recv_frame(self.sock)
        if hello is None:
            raise ConnectionError("No server hello")
        kem_ct, result = client_handshake(hello)
        send_frame(self.sock, kem_ct)
        self.channel = result.channel
        self.transcript = result.transcript

    def send(self, data: bytes) -> bytes:
        send_frame(self.sock, self.channel.seal(data))
        reply = recv_frame(self.sock)
        return self.channel.open(reply) if reply else b""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def loopback_demo(message: bytes = b"GET /status HTTP/1.0") -> dict:
    """
    Spin up an echo upstream + egress gateway, push one record through a real
    socket-based PQC tunnel, and confirm round-trip integrity.
    """
    # echo upstream
    echo = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    echo.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    echo.bind(("127.0.0.1", 0))
    echo.listen(1)
    echo_port = echo.getsockname()[1]

    def _echo() -> None:
        try:
            c, _ = echo.accept()
            data = c.recv(65536)
            c.sendall(b"ECHO:" + data)
            c.close()
        except OSError:
            pass

    threading.Thread(target=_echo, daemon=True).start()

    gw = EgressGateway("127.0.0.1", 0, "127.0.0.1", echo_port)
    gw_port = gw.start()
    try:
        client = IngressClient("127.0.0.1", gw_port)
        reply = client.send(message)
        client.close()
        return {
            "ok": reply == b"ECHO:" + message,
            "gateway_port": gw_port,
            "request": message.decode("utf-8", "replace"),
            "response": reply.decode("utf-8", "replace"),
            "transcript": client.transcript,
        }
    finally:
        gw.stop()
        echo.close()
