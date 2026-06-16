import { useQuery } from "@tanstack/react-query";
import { fetchEngineInfo } from "../api/client";
import { Settings as SettingsIcon, Server, Shield } from "lucide-react";

export default function SettingsPage() {
  const { data: info } = useQuery({ queryKey: ["engine"], queryFn: fetchEngineInfo });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted text-sm mt-1">
          The gateway is configured via environment variables / .env. Restart after edits.
        </p>
      </div>

      <div className="card p-6 space-y-3">
        <div className="flex items-center gap-2 mb-2">
          <SettingsIcon className="size-4 text-accent-glow" />
          <h2 className="font-semibold">Environment variables</h2>
        </div>
        <table className="w-full text-sm">
          <tbody>
            {[
              ["PQCG_HOST", "Bind address (default 0.0.0.0)"],
              ["PQCG_PORT", "Web/API port (default 8080)"],
              ["PQCG_DISCOVERY_INTERVAL_SEC", "Seconds between LAN scans (default 60)"],
              ["PQCG_DISCOVERY_SUBNET", "Override auto-detected subnet, e.g. 192.168.1.0/24"],
              ["PQCG_GATEWAY_LISTEN_BASE_PORT", "Starting port for new gateway sessions (18000)"],
              ["PQCG_HYBRID_CLASSICAL", "true / false — hybrid X25519 + ML-KEM"],
              ["PQCG_BACKEND", "liboqs / pqcrypto / demo (auto)"],
            ].map(([k, v]) => (
              <tr key={k} className="border-t border-bg-border">
                <td className="py-2 pr-4 font-mono text-accent-glow">{k}</td>
                <td className="py-2 text-slate-300">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="size-4 text-accent-glow" />
          <h2 className="font-semibold">Cryptographic suite</h2>
        </div>
        {info && (
          <pre className="bg-bg-soft border border-bg-border rounded-lg p-4 text-xs font-mono overflow-x-auto">
{JSON.stringify(info, null, 2)}
          </pre>
        )}
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-2 mb-3">
          <Server className="size-4 text-accent-glow" />
          <h2 className="font-semibold">Plug-and-play tips</h2>
        </div>
        <ul className="text-sm space-y-2 list-disc list-inside text-slate-300">
          <li>Drop the box on the same VLAN as the devices you want to protect.</li>
          <li>Point each protected device's gateway / route to this machine's IP.</li>
          <li>For a quick demo, point sessions at <span className="font-mono">127.0.0.1:18999</span> — the bundled PQC echo server.</li>
          <li>Move tier-1 devices to native PQC first; the gateway covers the rest until they catch up.</li>
        </ul>
      </div>
    </div>
  );
}
