import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity, ShieldCheck, Cpu, Network, Zap, Server, Workflow, Send,
} from "lucide-react";
import StatCard from "../components/StatCard";
import TrafficChart from "../components/TrafficChart";
import { fetchDashboard, sendTestTraffic } from "../api/client";
import { useLive } from "../store/useLive";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KiB`;
  if (n < 1_073_741_824) return `${(n / 1_048_576).toFixed(2)} MiB`;
  return `${(n / 1_073_741_824).toFixed(2)} GiB`;
}

export default function Dashboard() {
  const { data } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: 5_000,
  });
  const { samples } = useLive();

  const m_test = useMutation({ mutationFn: () => sendTestTraffic(64, 16 * 1024) });

  const recent = samples.slice(-30);
  const recentPqc = recent.reduce((a, s) => a + s.bytes_in + s.bytes_out, 0);
  const recentNic = recent.reduce((a, s) => a + s.nic_in + s.nic_out, 0);
  const coverage = recentNic > 0
    ? Math.min(100, Math.round((recentPqc / recentNic) * 100))
    : 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Operations Dashboard</h1>
        <p className="text-muted text-sm mt-1">
          Real-time quantum-safe coverage of your local area network.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="LAN nodes"
          value={data?.total_nodes ?? "—"}
          hint={`${data?.online_nodes ?? 0} online`}
          icon={<Network className="size-5" />}
        />
        <StatCard
          label="PQC-wrapped"
          value={data?.wrapped_nodes ?? "—"}
          hint={`${data?.native_pqc_nodes ?? 0} native PQC`}
          accent="pqc"
          icon={<ShieldCheck className="size-5" />}
        />
        <StatCard
          label="Active sessions"
          value={data?.active_sessions ?? "—"}
          hint="established tunnels"
          accent="ok"
          icon={<Activity className="size-5" />}
        />
        <StatCard
          label="Bytes protected"
          value={fmtBytes(data?.total_bytes_protected ?? 0)}
          hint="cumulative through gateway"
          icon={<Zap className="size-5" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
            <div>
              <h2 className="font-semibold">Live traffic</h2>
              <p className="text-xs text-muted">
                NIC total (grey) vs. PQC-tunnelled bytes (purple) — 1-second buckets.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge-muted">PQC coverage&nbsp;{coverage}%</span>
              <span className="badge-pqc">{data?.pqc_engine.aead_alg}</span>
              <button
                onClick={() => m_test.mutate()}
                disabled={m_test.isPending}
                className="btn-primary text-xs"
                title="Push 64 × 16 KiB frames through the bundled PQC echo server"
              >
                <Send className="size-3.5" />
                {m_test.isPending ? "Sending…" : "Send test traffic"}
              </button>
            </div>
          </div>
          <TrafficChart samples={samples} />
          {m_test.data?.ok && (
            <div className="text-xs text-muted mt-3">
              Sent {m_test.data.iterations} × {(m_test.data.payload_size! / 1024).toFixed(0)} KiB
              {" "}in {m_test.data.elapsed_sec}s — {m_test.data.throughput_mbps} Mbps through the PQC tunnel.
            </div>
          )}
          {m_test.data?.ok === false && (
            <div className="text-xs text-bad mt-3">Test traffic failed: {m_test.data.error}</div>
          )}
        </div>

        <div className="card p-6 space-y-5">
          <div className="flex items-center gap-2">
            <Cpu className="size-4 text-accent-glow" />
            <h2 className="font-semibold">PQC engine</h2>
          </div>
          {data?.pqc_engine ? (
            <ul className="text-sm space-y-2">
              <li className="flex justify-between">
                <span className="text-muted">Backend</span>
                <span>{data.pqc_engine.backend}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-muted">KEM</span>
                <span className="font-mono">{data.pqc_engine.kem_alg}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-muted">Signature</span>
                <span className="font-mono">{data.pqc_engine.sig_alg}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-muted">AEAD</span>
                <span className="font-mono">{data.pqc_engine.aead_alg}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-muted">Hybrid</span>
                <span>{data.pqc_engine.hybrid ? "X25519 + ML-KEM" : "off"}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-muted">Grade</span>
                <span className={
                  data.pqc_engine.pqc_grade === "demo"
                    ? "badge-warn"
                    : data.pqc_engine.pqc_grade === "nist-strict"
                    ? "badge-ok"
                    : "badge-pqc"
                }>{data.pqc_engine.pqc_grade}</span>
              </li>
            </ul>
          ) : (
            <div className="text-muted text-sm">loading…</div>
          )}
          <a
            href="/pqc"
            className="btn-ghost w-full justify-center"
          >Run self-test</a>
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Workflow className="size-4 text-accent-glow" />
            <h2 className="font-semibold">Migration progress</h2>
          </div>
          <span className="badge-pqc">{data?.current_stage ?? "—"}</span>
        </div>
        <div className="h-3 bg-bg-soft rounded-full overflow-hidden border border-bg-border">
          <div
            className="h-full bg-gradient-to-r from-accent to-accent-glow shadow-glow transition-all"
            style={{ width: `${data?.overall_progress_pct ?? 0}%` }}
          />
        </div>
        <div className="text-xs text-muted mt-2">
          {data?.overall_progress_pct?.toFixed(1) ?? 0}% of the planned stages completed across the network.
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-2 mb-3">
          <Server className="size-4 text-accent-glow" />
          <h2 className="font-semibold">How it works</h2>
        </div>
        <ol className="text-sm text-slate-300 space-y-2 list-decimal list-inside">
          <li><span className="text-muted">Discover</span> — every device on your LAN is auto-detected.</li>
          <li><span className="text-muted">Classify</span> — PQC-readiness, criticality and risk are computed.</li>
          <li><span className="text-muted">Wrap</span> — outbound traffic is tunneled in ML-KEM-768 + AES-256-GCM.</li>
          <li><span className="text-muted">Migrate</span> — high-priority devices get native PQC stage by stage.</li>
          <li><span className="text-muted">Standby</span> — gateway covers only the residual legacy nodes.</li>
        </ol>
      </div>
    </div>
  );
}
