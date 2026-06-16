import { useEffect, useRef, useState } from "react";

export interface LiveSample {
  ts: number;
  bytes_in: number;
  bytes_out: number;
  frames: number;
  nic_in: number;
  nic_out: number;
}

export function useLive() {
  const [samples, setSamples] = useState<LiveSample[]>([]);
  const [connected, setConnected] = useState(false);
  const [engine, setEngine] = useState<any | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${proto}//${window.location.host}/ws/live`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "hello") setEngine(msg.engine);
          if (msg.type === "traffic.snapshot") {
            setSamples(msg.samples ?? []);
          } else if (msg.type === "traffic.sample") {
            setSamples((prev) =>
              [...prev, {
                ts: msg.ts,
                bytes_in: msg.bytes_in,
                bytes_out: msg.bytes_out,
                frames: msg.frames,
                nic_in: msg.nic_in ?? 0,
                nic_out: msg.nic_out ?? 0,
              }].slice(-300)
            );
          }
        } catch {
          /* ignore */
        }
      };
    };
    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return { samples, connected, engine };
}
