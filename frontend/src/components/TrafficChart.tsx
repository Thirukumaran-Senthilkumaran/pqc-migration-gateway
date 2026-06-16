import { useMemo } from "react";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
  Legend,
} from "recharts";
import { LiveSample } from "../store/useLive";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KiB`;
  if (n < 1_073_741_824) return `${(n / 1_048_576).toFixed(2)} MiB`;
  return `${(n / 1_073_741_824).toFixed(2)} GiB`;
}

export default function TrafficChart({ samples }: { samples: LiveSample[] }) {
  const data = useMemo(
    () =>
      samples.map((s) => ({
        t: new Date(s.ts * 1000).toLocaleTimeString([], { hour12: false }).slice(3),
        pqc: (s.bytes_in ?? 0) + (s.bytes_out ?? 0),
        nic: (s.nic_in ?? 0) + (s.nic_out ?? 0),
      })),
    [samples]
  );

  if (data.length === 0) {
    return (
      <div className="text-muted text-sm h-72 grid place-items-center">
        Waiting for traffic samples …
      </div>
    );
  }

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="g-nic" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7d8597" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#7d8597" stopOpacity={0.04} />
            </linearGradient>
            <linearGradient id="g-pqc" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7c5cff" stopOpacity={0.7} />
              <stop offset="100%" stopColor="#7c5cff" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#252b38" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" stroke="#7d8597" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis
            stroke="#7d8597"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={fmtBytes}
            width={70}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#161a23",
              border: "1px solid #252b38",
              borderRadius: 10,
              fontSize: 12,
            }}
            formatter={(v: number, name: string) =>
              [fmtBytes(v), name === "nic" ? "NIC total" : "PQC tunnel"]
            }
          />
          <Legend
            verticalAlign="top"
            height={28}
            iconType="circle"
            wrapperStyle={{ fontSize: 12, color: "#7d8597" }}
            formatter={(v) => (v === "nic" ? "NIC total" : "PQC tunnel")}
          />
          <Area
            type="monotone"
            dataKey="nic"
            stroke="#7d8597"
            fill="url(#g-nic)"
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="pqc"
            stroke="#a18bff"
            fill="url(#g-pqc)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
