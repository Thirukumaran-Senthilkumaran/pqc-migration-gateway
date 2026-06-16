import { WrapMode } from "../api/client";

const labels: Record<WrapMode, string> = {
  off:     "Off",
  monitor: "Monitor",
  wrap:    "PQC Wrap",
  native:  "Native",
};

export default function WrapModePicker({
  value,
  onChange,
  disabled,
}: {
  value: WrapMode;
  onChange: (v: WrapMode) => void;
  disabled?: boolean;
}) {
  return (
    <select
      className="bg-bg-soft border border-bg-border rounded-md px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-accent"
      value={value}
      onChange={(e) => onChange(e.target.value as WrapMode)}
      disabled={disabled}
    >
      {Object.entries(labels).map(([k, v]) => (
        <option key={k} value={k}>{v}</option>
      ))}
    </select>
  );
}
