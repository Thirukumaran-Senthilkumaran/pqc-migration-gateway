import axios from "axios";

export const api = axios.create({
  baseURL: "/",
  headers: { "Content-Type": "application/json" },
});

export type WrapMode = "off" | "monitor" | "wrap" | "native";
export type NodeStatus = "unknown" | "online" | "offline" | "quarantined";
export type PriorityTier = "tier-1" | "tier-2" | "tier-3";
export type SessionStatus =
  | "negotiating" | "established" | "rekeying" | "closed" | "failed";
export type StageStatus =
  | "planned" | "in_progress" | "completed" | "blocked";

export interface NodeOut {
  id: number;
  mac: string;
  ip: string;
  hostname?: string | null;
  vendor?: string | null;
  os_guess?: string | null;
  open_ports?: string | null;
  services?: string | null;
  notes?: string | null;
  pqc_ready: number;
  criticality: number;
  risk: number;
  priority_score: number;
  priority_tier: PriorityTier;
  wrap_mode: WrapMode;
  status: NodeStatus;
  first_seen: string;
  last_seen: string;
}

export interface DashboardStats {
  total_nodes: number;
  online_nodes: number;
  wrapped_nodes: number;
  native_pqc_nodes: number;
  active_sessions: number;
  total_bytes_protected: number;
  pqc_engine: {
    backend: string;
    kem_alg: string;
    sig_alg: string;
    aead_alg: string;
    pqc_grade: string;
    hybrid: boolean;
  };
  current_stage: string | null;
  overall_progress_pct: number;
}

export interface GatewaySessionOut {
  id: number;
  node_id: number;
  listen_port: number;
  upstream_host: string;
  upstream_port: number;
  kem_alg: string;
  sig_alg: string;
  aead_alg: string;
  hybrid: boolean;
  crypto_suite: string;
  scope: "lan-lan" | "lan-wan" | "any";
  suite_history?: string | null;
  bytes_in: number;
  bytes_out: number;
  frames_in: number;
  frames_out: number;
  status: SessionStatus;
  started_at: string;
  last_rekey_at?: string | null;
  closed_at?: string | null;
}

export interface MigrationStageOut {
  id: number;
  name: string;
  ordinal: number;
  target_tier?: PriorityTier | null;
  description?: string | null;
  status: StageStatus;
  progress_pct: number;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface MigrationTaskOut {
  id: number;
  stage_id: number;
  node_id?: number | null;
  action: string;
  status: StageStatus;
  notes?: string | null;
  updated_at: string;
}

export interface MigrationPlan {
  stages: MigrationStageOut[];
  tasks: MigrationTaskOut[];
}

export interface PQCSelfTestResult {
  kem_ok: boolean;
  sig_ok: boolean;
  tunnel_ok: boolean;
  backend: string;
  kem_alg: string;
  sig_alg: string;
  aead_alg: string;
  notes: string[];
}

// --------------------------------------------------------------------------- //
// helpers
// --------------------------------------------------------------------------- //
export const fetchDashboard = () =>
  api.get<DashboardStats>("/api/stats/dashboard").then((r) => r.data);

export const fetchTraffic = () =>
  api.get<{ ts: string; bytes_in: number; bytes_out: number; frames: number }[]>(
    "/api/stats/traffic"
  ).then((r) => r.data);

export const fetchNodes = () =>
  api.get<NodeOut[]>("/api/nodes").then((r) => r.data);

export const updateNode = (id: number, patch: Partial<NodeOut>) =>
  api.patch<NodeOut>(`/api/nodes/${id}`, patch).then((r) => r.data);

export const reclassify = () =>
  api.post<{ reclassified: number }>("/api/nodes/reclassify").then((r) => r.data);

export const triggerDiscovery = (subnet?: string) =>
  api.post<{ found: number }>("/api/nodes/discovery/trigger", { subnet }).then((r) => r.data);

export const fetchSessions = () =>
  api.get<GatewaySessionOut[]>("/api/gateway/sessions").then((r) => r.data);

export const createSession = (
  node_id: number,
  upstream_host: string,
  upstream_port: number,
  listen_port?: number,
  scope: TrafficScope = "lan-wan",
  crypto_suite?: string,
) =>
  api
    .post<GatewaySessionOut>("/api/gateway/sessions", {
      node_id, upstream_host, upstream_port, listen_port, scope, crypto_suite,
    })
    .then((r) => r.data);

export const deleteSession = (id: number) =>
  api.delete(`/api/gateway/sessions/${id}`);

export const fetchMigrationPlan = () =>
  api.get<MigrationPlan>("/api/migration/plan").then((r) => r.data);

export const rebuildPlan = () =>
  api.post("/api/migration/plan/rebuild").then((r) => r.data);

export const updateStage = (id: number, status: StageStatus) =>
  api.patch(`/api/migration/stages/${id}`, null, { params: { new_status: status } });

export const runSelfTest = () =>
  api.post<PQCSelfTestResult>("/api/pqc/selftest").then((r) => r.data);

export const fetchEngineInfo = () =>
  api.get("/api/pqc/info").then((r) => r.data);

export const sendTestTraffic = (iterations = 32, payloadSize = 16 * 1024) =>
  api
    .post<{
      ok: boolean;
      iterations?: number;
      payload_size?: number;
      bytes_sent?: number;
      bytes_recv?: number;
      elapsed_sec?: number;
      throughput_mbps?: number;
      error?: string;
    }>("/api/pqc/test-traffic", null, {
      params: { iterations, payload_size: payloadSize },
    })
    .then((r) => r.data);

// --------------------------------------------------------------------------- //
// Crypto policy
// --------------------------------------------------------------------------- //
export type TrafficScope = "lan-lan" | "lan-wan" | "any";
export type AnomalyType =
  | "aead_failure"
  | "replay_detected"
  | "handshake_failure"
  | "size_anomaly"
  | "policy_upgrade";
export type AnomalySeverity = "low" | "medium" | "high" | "critical";

export interface SuiteOut {
  suite: string;
  label: string;
  pqc: boolean;
  use_kem: boolean;
  use_x25519: boolean;
  use_signature: boolean;
  aead_key_len: number;
  handshake_bytes: number;
  description: string;
  quantum_safe: string;
}

export interface PolicyRuleOut {
  id: number;
  name: string;
  scope: TrafficScope;
  tier_filter: string | null;
  initial_suite: string;
  upgrade_suite: string | null;
  anomaly_threshold: number;
  anomaly_window_sec: number;
  enabled: boolean;
  priority: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnomalyEventOut {
  id: number;
  ts: string;
  session_id: number | null;
  type: AnomalyType;
  severity: AnomalySeverity;
  message: string;
  action_taken: string | null;
  from_suite: string | null;
  to_suite: string | null;
}

export const fetchSuites = () =>
  api.get<SuiteOut[]>("/api/policy/suites").then((r) => r.data);

export const fetchRules = () =>
  api.get<PolicyRuleOut[]>("/api/policy/rules").then((r) => r.data);

export const createRule = (payload: Partial<PolicyRuleOut> & { name: string; initial_suite: string }) =>
  api.post<PolicyRuleOut>("/api/policy/rules", payload).then((r) => r.data);

export const updateRule = (id: number, patch: Partial<PolicyRuleOut>) =>
  api.patch<PolicyRuleOut>(`/api/policy/rules/${id}`, patch).then((r) => r.data);

export const deleteRule = (id: number) =>
  api.delete(`/api/policy/rules/${id}`);

export const fetchAnomalies = (limit = 100) =>
  api
    .get<AnomalyEventOut[]>("/api/policy/anomalies", { params: { limit } })
    .then((r) => r.data);

export const injectAnomaly = (session_id: number, type: AnomalyType = "aead_failure", message = "demo") =>
  api
    .post<AnomalyEventOut>("/api/policy/anomalies/inject", { session_id, type, message })
    .then((r) => r.data);
