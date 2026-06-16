import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Shuffle, Plus, Trash2, ZapOff, AlertTriangle, ArrowRight, Cpu, Sparkles,
} from "lucide-react";
import {
  AnomalyEventOut, fetchAnomalies, fetchRules, fetchSuites,
  fetchSessions, injectAnomaly, deleteRule, createRule, updateRule,
  PolicyRuleOut, SuiteOut, TrafficScope,
} from "../api/client";

const SCOPES: TrafficScope[] = ["lan-lan", "lan-wan", "any"];
const SCOPE_LABEL: Record<TrafficScope, string> = {
  "lan-lan": "LAN ↔ LAN",
  "lan-wan": "LAN ↔ WAN",
  "any":     "Any",
};

const SEV_CLASS: Record<string, string> = {
  low:      "badge-muted",
  medium:   "badge-warn",
  high:     "badge-bad",
  critical: "badge-bad",
};

export default function Policy() {
  const qc = useQueryClient();
  const { data: rules = [] } = useQuery({
    queryKey: ["rules"],
    queryFn: fetchRules,
    refetchInterval: 8_000,
  });
  const { data: suites = [] } = useQuery({
    queryKey: ["suites"],
    queryFn: fetchSuites,
  });
  const { data: anomalies = [] } = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => fetchAnomalies(50),
    refetchInterval: 3_000,
  });
  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    refetchInterval: 5_000,
  });

  const m_delete = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
  const m_toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => updateRule(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
  const m_create = useMutation({
    mutationFn: createRule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Shuffle className="size-5 text-accent-glow" />
          Crypto Policy
        </h1>
        <p className="text-muted text-sm mt-1">
          Adaptive cipher selection per traffic scope. Anomalies auto-upgrade
          the suite mid-flow — no operator intervention needed.
        </p>
      </div>

      {/* Suite reference */}
      <SuiteCards suites={suites} />

      {/* Rules table + new rule form */}
      <RulesCard
        rules={rules}
        suites={suites}
        onDelete={(id) => m_delete.mutate(id)}
        onToggle={(id, enabled) => m_toggle.mutate({ id, enabled })}
        onCreate={(payload) => m_create.mutate(payload)}
      />

      {/* Anomaly feed + injector */}
      <AnomalyFeed anomalies={anomalies} sessions={sessions} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────── //
// Suite cards
// ─────────────────────────────────────────────────────────────────────────── //
function SuiteCards({ suites }: { suites: SuiteOut[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {suites.map((s) => {
        const accent =
          s.suite === "pqc-full" ? "border-accent/40 shadow-glow"
            : s.suite === "pqc-compressed" ? "border-accent/20"
            : "border-bg-border";
        return (
          <div key={s.suite} className={`card p-5 transition-colors ${accent}`}>
            <div className="flex items-center gap-2 mb-2">
              <Cpu className="size-4 text-accent-glow" />
              <h3 className="font-semibold text-sm">{s.label}</h3>
            </div>
            <p className="text-xs text-muted mb-3">{s.description}</p>
            <div className="grid grid-cols-2 gap-y-1 text-xs">
              <span className="text-muted">KEM</span>
              <span>{s.use_kem ? "ML-KEM-768" : "—"}</span>
              <span className="text-muted">X25519</span>
              <span>{s.use_x25519 ? "yes" : "—"}</span>
              <span className="text-muted">Sig</span>
              <span>{s.use_signature ? "ML-DSA-65" : "—"}</span>
              <span className="text-muted">AEAD</span>
              <span>AES-{s.aead_key_len * 8}-GCM</span>
              <span className="text-muted">Handshake</span>
              <span className="font-mono">~{(s.handshake_bytes / 1024).toFixed(1)} KiB</span>
            </div>
            <div className="mt-3">
              <span className={
                s.quantum_safe === "yes" ? "badge-ok" :
                s.quantum_safe === "partial" ? "badge-warn" : "badge-bad"
              }>
                quantum-safe: {s.quantum_safe}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────── //
// Rules
// ─────────────────────────────────────────────────────────────────────────── //
function RulesCard({
  rules, suites, onDelete, onToggle, onCreate,
}: {
  rules: PolicyRuleOut[];
  suites: SuiteOut[];
  onDelete: (id: number) => void;
  onToggle: (id: number, enabled: boolean) => void;
  onCreate: (payload: any) => void;
}) {
  const [form, setForm] = useState({
    name: "",
    scope: "lan-lan" as TrafficScope,
    initial_suite: "classical",
    upgrade_suite: "pqc-compressed",
    anomaly_threshold: 3,
    anomaly_window_sec: 30,
    priority: 50,
    notes: "",
  });

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Active rules</h2>
        <span className="text-xs text-muted">
          Lower priority numbers match first.
        </span>
      </div>
      <div className="overflow-hidden rounded-lg border border-bg-border">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Scope</th>
              <th className="px-3 py-2 text-left">Initial → Upgrade</th>
              <th className="px-3 py-2 text-right">Threshold</th>
              <th className="px-3 py-2 text-right">Priority</th>
              <th className="px-3 py-2 text-center">Enabled</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t border-bg-border hover:bg-bg-hover/50">
                <td className="px-3 py-2">
                  <div className="font-medium">{r.name}</div>
                  {r.notes && <div className="text-xs text-muted">{r.notes}</div>}
                </td>
                <td className="px-3 py-2">
                  <span className="badge-muted">{SCOPE_LABEL[r.scope]}</span>
                </td>
                <td className="px-3 py-2">
                  <span className="font-mono text-xs">{r.initial_suite}</span>
                  {r.upgrade_suite && (
                    <>
                      <ArrowRight className="inline size-3 mx-1 text-accent-glow" />
                      <span className="font-mono text-xs text-accent-glow">{r.upgrade_suite}</span>
                    </>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-xs">
                  {r.anomaly_threshold} / {r.anomaly_window_sec}s
                </td>
                <td className="px-3 py-2 text-right">{r.priority}</td>
                <td className="px-3 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) => onToggle(r.id, e.target.checked)}
                    className="accent-accent"
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => onDelete(r.id)}
                    className="btn-ghost text-red-300 hover:text-red-200 px-2 py-1 text-xs"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New rule */}
      <div className="mt-5 grid grid-cols-1 md:grid-cols-7 gap-2">
        <input
          placeholder="Rule name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="md:col-span-2 bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
        />
        <select
          value={form.scope}
          onChange={(e) => setForm({ ...form, scope: e.target.value as TrafficScope })}
          className="bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
        >
          {SCOPES.map((s) => <option key={s} value={s}>{SCOPE_LABEL[s]}</option>)}
        </select>
        <select
          value={form.initial_suite}
          onChange={(e) => setForm({ ...form, initial_suite: e.target.value })}
          className="bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
        >
          {suites.map((s) => <option key={s.suite} value={s.suite}>{s.suite}</option>)}
        </select>
        <select
          value={form.upgrade_suite}
          onChange={(e) => setForm({ ...form, upgrade_suite: e.target.value })}
          className="bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
        >
          <option value="">(no upgrade)</option>
          {suites.map((s) => <option key={s.suite} value={s.suite}>↑ {s.suite}</option>)}
        </select>
        <input
          type="number"
          min={1}
          max={100}
          value={form.anomaly_threshold}
          onChange={(e) => setForm({ ...form, anomaly_threshold: parseInt(e.target.value) })}
          title="Anomaly threshold (events to trigger upgrade)"
          className="bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
        />
        <button
          disabled={!form.name}
          onClick={() => onCreate({
            ...form,
            upgrade_suite: form.upgrade_suite || undefined,
          })}
          className="btn-primary text-xs justify-center"
        >
          <Plus className="size-3.5" /> Add rule
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────── //
// Anomaly feed
// ─────────────────────────────────────────────────────────────────────────── //
function AnomalyFeed({
  anomalies, sessions,
}: {
  anomalies: AnomalyEventOut[];
  sessions: { id: number; crypto_suite: string; node_id: number }[];
}) {
  const [target, setTarget] = useState<number | "">("");
  const m_inject = useMutation({ mutationFn: ({ id }: { id: number }) => injectAnomaly(id, "aead_failure", "demo: simulated tampering") });

  const upgradeCount = useMemo(
    () => anomalies.filter((a) => a.type === "policy_upgrade").length,
    [anomalies]
  );

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h2 className="font-semibold flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-400" />
            Anomaly feed
          </h2>
          <p className="text-xs text-muted mt-1">
            Live decryption-failure / handshake-error / policy-upgrade events.
            {upgradeCount > 0 && (
              <span className="ml-2 badge-pqc">
                <Sparkles className="size-3" /> {upgradeCount} auto-upgrades
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value ? parseInt(e.target.value) : "")}
            className="bg-bg-soft border border-bg-border rounded px-2 py-1.5 text-xs"
          >
            <option value="">Pick a session…</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} ({s.crypto_suite})
              </option>
            ))}
          </select>
          <button
            disabled={typeof target !== "number" || m_inject.isPending}
            onClick={() => typeof target === "number" && m_inject.mutate({ id: target })}
            className="btn-ghost text-xs"
            title="Simulates 3 AEAD failures in a row to trigger the upgrade rule."
          >
            <ZapOff className="size-3.5" />
            Inject anomaly
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-bg-border max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-xs uppercase tracking-wider text-muted sticky top-0">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-center">Sev</th>
              <th className="px-3 py-2 text-left">Session</th>
              <th className="px-3 py-2 text-left">Suite change</th>
              <th className="px-3 py-2 text-left">Message</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-muted">
                  No anomalies recorded. The system is calm.
                </td>
              </tr>
            )}
            {anomalies.map((a) => (
              <tr key={a.id} className="border-t border-bg-border">
                <td className="px-3 py-2 text-xs text-muted whitespace-nowrap">
                  {new Date(a.ts).toLocaleTimeString()}
                </td>
                <td className="px-3 py-2 text-xs">
                  <span className={a.type === "policy_upgrade" ? "badge-pqc" : "badge-muted"}>
                    {a.type}
                  </span>
                </td>
                <td className="px-3 py-2 text-center">
                  <span className={SEV_CLASS[a.severity] ?? "badge-muted"}>{a.severity}</span>
                </td>
                <td className="px-3 py-2 text-xs">{a.session_id ?? "—"}</td>
                <td className="px-3 py-2 text-xs">
                  {a.from_suite && a.to_suite ? (
                    <span>
                      <span className="font-mono">{a.from_suite}</span>
                      <ArrowRight className="inline size-3 mx-1 text-accent-glow" />
                      <span className="font-mono text-accent-glow">{a.to_suite}</span>
                    </span>
                  ) : "—"}
                </td>
                <td className="px-3 py-2 text-xs text-slate-300">{a.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
