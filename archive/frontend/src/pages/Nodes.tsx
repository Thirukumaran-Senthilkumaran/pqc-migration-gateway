import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { RefreshCw, Search, Wifi, WifiOff, Sparkles } from "lucide-react";
import {
  fetchNodes, NodeOut, reclassify, triggerDiscovery, updateNode,
} from "../api/client";
import TierPill from "../components/TierPill";
import WrapModePicker from "../components/WrapModePicker";

export default function Nodes() {
  const qc = useQueryClient();
  const { data: nodes = [] } = useQuery({
    queryKey: ["nodes"],
    queryFn: fetchNodes,
    refetchInterval: 8_000,
  });

  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);

  const filtered = nodes.filter((n) => {
    if (!filter.trim()) return true;
    const q = filter.toLowerCase();
    return (
      n.ip.includes(q) ||
      n.mac.toLowerCase().includes(q) ||
      (n.hostname ?? "").toLowerCase().includes(q) ||
      (n.vendor ?? "").toLowerCase().includes(q)
    );
  });

  const m_update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<NodeOut> }) =>
      updateNode(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nodes"] }),
  });

  const onScan = async () => {
    setBusy(true);
    try {
      await triggerDiscovery();
      await reclassify();
      qc.invalidateQueries({ queryKey: ["nodes"] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">LAN Nodes</h1>
          <p className="text-muted text-sm mt-1">
            Auto-discovered devices, classified by PQC readiness and criticality.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="size-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter ip / mac / vendor / hostname"
              className="bg-bg-soft border border-bg-border rounded-lg pl-9 pr-3 py-2 text-sm w-72 focus:outline-none focus:border-accent"
            />
          </div>
          <button onClick={onScan} disabled={busy} className="btn-primary">
            <RefreshCw className={`size-4 ${busy ? "animate-spin" : ""}`} />
            Scan now
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3 text-left">Node</th>
              <th className="px-4 py-3 text-left">Vendor</th>
              <th className="px-4 py-3 text-left">Services</th>
              <th className="px-4 py-3 text-right">PQC&nbsp;ready</th>
              <th className="px-4 py-3 text-right">Risk</th>
              <th className="px-4 py-3 text-right">Crit</th>
              <th className="px-4 py-3 text-center">Tier</th>
              <th className="px-4 py-3 text-center">Mode</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-12 text-muted">
                  No nodes match. Run a scan to discover the LAN.
                </td>
              </tr>
            )}
            {filtered.map((n) => (
              <tr key={n.id} className="border-t border-bg-border hover:bg-bg-hover/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {n.status === "online" ? (
                      <Wifi className="size-4 text-emerald-400" />
                    ) : (
                      <WifiOff className="size-4 text-amber-400" />
                    )}
                    <div>
                      <div className="font-medium">{n.hostname ?? n.ip}</div>
                      <div className="text-xs text-muted font-mono">{n.ip} · {n.mac}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-300">{n.vendor ?? "—"}</td>
                <td className="px-4 py-3 text-slate-300">{n.services ?? "—"}</td>
                <td className="px-4 py-3 text-right font-mono">{n.pqc_ready.toFixed(1)}</td>
                <td className="px-4 py-3 text-right font-mono">{n.risk.toFixed(1)}</td>
                <td className="px-4 py-3 text-right">
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={0.5}
                    value={n.criticality}
                    onChange={(e) =>
                      m_update.mutate({
                        id: n.id,
                        patch: { criticality: parseFloat(e.target.value) },
                      })
                    }
                    className="w-16 bg-bg-soft border border-bg-border rounded px-2 py-1 text-right text-xs"
                  />
                </td>
                <td className="px-4 py-3 text-center">
                  <TierPill tier={n.priority_tier} />
                </td>
                <td className="px-4 py-3 text-center">
                  <WrapModePicker
                    value={n.wrap_mode}
                    onChange={(v) => m_update.mutate({ id: n.id, patch: { wrap_mode: v } })}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  {n.priority_tier === "tier-1" && (
                    <span className="badge-pqc"><Sparkles className="size-3" /> priority</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
