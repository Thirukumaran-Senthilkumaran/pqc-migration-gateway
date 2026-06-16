import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Plus, Trash2, ShieldCheck } from "lucide-react";
import {
  createSession, deleteSession, fetchNodes, fetchSessions, TrafficScope,
} from "../api/client";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KiB`;
  return `${(n / 1_048_576).toFixed(2)} MiB`;
}

export default function Gateway() {
  const qc = useQueryClient();
  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    refetchInterval: 4_000,
  });
  const { data: nodes = [] } = useQuery({
    queryKey: ["nodes"],
    queryFn: fetchNodes,
  });

  const [nodeId, setNodeId] = useState<number | "">("");
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState(18999);
  const [scope, setScope] = useState<TrafficScope>("lan-wan");

  const m_create = useMutation({
    mutationFn: () => {
      if (typeof nodeId !== "number") throw new Error("Pick a node");
      return createSession(nodeId, host, port, undefined, scope);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const m_delete = useMutation({
    mutationFn: (id: number) => deleteSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">PQC Gateway</h1>
        <p className="text-muted text-sm mt-1">
          Active TCP listeners forwarding LAN traffic into PQC-secured tunnels.
        </p>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Plus className="size-4 text-accent-glow" />
            <h2 className="font-semibold">New session</h2>
          </div>
          <button
            type="button"
            onClick={() => { setHost("127.0.0.1"); setPort(18999); }}
            className="btn-ghost text-xs"
            title="Fill the form with the bundled PQC echo server"
          >
            Use bundled echo server
          </button>
        </div>

        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 mb-4 text-xs text-amber-200">
          <strong>Upstream must speak PQC.</strong> Point this at the bundled echo
          server (<span className="font-mono">127.0.0.1:18999</span>) or another
          instance of this gateway. A regular LAN device (a phone, printer, etc.)
          will not complete the ML-KEM-768 handshake and the session will stay at
          zero bytes.
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <select
            className="bg-bg-soft border border-bg-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value ? parseInt(e.target.value) : "")}
          >
            <option value="">Pick a LAN node…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.hostname ?? n.ip} · {n.ip}
              </option>
            ))}
          </select>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="PQC upstream host (e.g. 127.0.0.1)"
            className="bg-bg-soft border border-bg-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
          <input
            type="number"
            value={port}
            min={1}
            max={65535}
            onChange={(e) => setPort(parseInt(e.target.value))}
            placeholder="PQC upstream port (e.g. 18999)"
            className="bg-bg-soft border border-bg-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as TrafficScope)}
            title="Traffic scope — drives the policy engine's suite selection."
            className="bg-bg-soft border border-bg-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          >
            <option value="lan-lan">Scope: LAN ↔ LAN</option>
            <option value="lan-wan">Scope: LAN ↔ WAN</option>
            <option value="any">Scope: any</option>
          </select>
          <button
            disabled={typeof nodeId !== "number" || m_create.isPending}
            onClick={() => m_create.mutate()}
            className="btn-primary justify-center"
          >
            <ShieldCheck className="size-4" />
            Open PQC tunnel
          </button>
        </div>
        {m_create.isError && (
          <div className="text-bad text-sm mt-3">
            {(m_create.error as Error).message}
          </div>
        )}
        <div className="text-xs text-muted mt-3">
          For an immediate visual demo without configuring a session, click
          {" "}<span className="text-slate-200">Send test traffic</span> on the Dashboard.
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3 text-left">Session</th>
              <th className="px-4 py-3 text-left">Listen</th>
              <th className="px-4 py-3 text-left">Upstream</th>
              <th className="px-4 py-3 text-left">Scope</th>
              <th className="px-4 py-3 text-left">Active suite</th>
              <th className="px-4 py-3 text-right">In</th>
              <th className="px-4 py-3 text-right">Out</th>
              <th className="px-4 py-3 text-center">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-10 text-muted">
                  No active gateway sessions.
                </td>
              </tr>
            )}
            {sessions.map((s) => (
              <tr key={s.id} className="border-t border-bg-border hover:bg-bg-hover/50">
                <td className="px-4 py-3 font-mono">#{s.id}</td>
                <td className="px-4 py-3 font-mono">0.0.0.0:{s.listen_port}</td>
                <td className="px-4 py-3 font-mono">{s.upstream_host}:{s.upstream_port}</td>
                <td className="px-4 py-3 text-xs">
                  <span className="badge-muted">{s.scope}</span>
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  <span className={s.crypto_suite === "classical" ? "badge-warn" : "badge-pqc"}>
                    {s.crypto_suite}
                  </span>
                  {s.suite_history && s.suite_history.includes(",") && (
                    <div className="text-[10px] text-muted mt-1">
                      history: {s.suite_history}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-right">{fmtBytes(s.bytes_in)}</td>
                <td className="px-4 py-3 text-right">{fmtBytes(s.bytes_out)}</td>
                <td className="px-4 py-3 text-center">
                  <span className={
                    s.status === "established" ? "badge-ok" :
                    s.status === "negotiating" ? "badge-warn" :
                    s.status === "rekeying" ? "badge-pqc" :
                    s.status === "failed" ? "badge-bad" : "badge-muted"
                  }>{s.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => m_delete.mutate(s.id)}
                    className="btn-ghost text-red-300 hover:text-red-200"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
