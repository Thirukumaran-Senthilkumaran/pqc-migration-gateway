import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, ShieldCheck } from "lucide-react";
import { fetchEngineInfo, runSelfTest } from "../api/client";

export default function PQCEnginePage() {
  const { data: info } = useQuery({
    queryKey: ["engine"],
    queryFn: fetchEngineInfo,
  });
  const m_test = useMutation({ mutationFn: runSelfTest });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">PQC Engine</h1>
        <p className="text-muted text-sm mt-1">
          Inspect the loaded post-quantum primitives and run a real round-trip self-test.
        </p>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="size-4 text-accent-glow" />
          <h2 className="font-semibold">Active backend</h2>
        </div>
        {info ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-8 text-sm">
            <Row label="Backend" value={info.backend} />
            <Row label="PQC grade" value={info.pqc_grade} />
            <Row label="KEM" value={info.kem_alg} mono />
            <Row label="Signature" value={info.sig_alg} mono />
            <Row label="AEAD" value={info.aead_alg} mono />
            <Row label="Hybrid" value={info.hybrid ? "X25519 + ML-KEM" : "off"} />
          </div>
        ) : (
          <div className="text-muted text-sm">loading…</div>
        )}
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Self-test</h2>
          <button onClick={() => m_test.mutate()} className="btn-primary" disabled={m_test.isPending}>
            {m_test.isPending ? "Running…" : "Run round-trip"}
          </button>
        </div>
        {m_test.data ? (
          <div className="space-y-3">
            <Result label="ML-KEM encapsulate / decapsulate" ok={m_test.data.kem_ok} />
            <Result label="ML-DSA sign / verify" ok={m_test.data.sig_ok} />
            <Result label="Tunnel handshake + AEAD echo" ok={m_test.data.tunnel_ok} />
            {m_test.data.notes.length > 0 && (
              <ul className="text-xs text-amber-300 list-disc list-inside mt-3">
                {m_test.data.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            )}
          </div>
        ) : (
          <p className="text-muted text-sm">
            The self-test exercises an end-to-end ML-KEM-768 + ML-DSA-65 round-trip plus
            a real PQC-tunnel echo against the bundled echo server.
          </p>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={mono ? "font-mono" : ""}>{value}</span>
    </div>
  );
}

function Result({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-bg-soft border border-bg-border">
      {ok ? (
        <CheckCircle2 className="size-5 text-emerald-400" />
      ) : (
        <XCircle className="size-5 text-red-400" />
      )}
      <span className="text-sm">{label}</span>
      <span className={ok ? "ml-auto badge-ok" : "ml-auto badge-bad"}>
        {ok ? "pass" : "fail"}
      </span>
    </div>
  );
}
