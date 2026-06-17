import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Network, Workflow, ShieldCheck, Settings, Activity, Cpu, Shuffle, UserCircle,
} from "lucide-react";

const links = [
  { to: "/",          label: "Dashboard",     icon: LayoutDashboard },
  { to: "/nodes",     label: "Nodes",         icon: Network },
  { to: "/gateway",   label: "Gateway",       icon: Activity },
  { to: "/policy",    label: "Crypto Policy", icon: Shuffle },
  { to: "/migration", label: "Migration",     icon: Workflow },
  { to: "/pqc",       label: "PQC Engine",    icon: ShieldCheck },
  { to: "/about",     label: "About",         icon: UserCircle },
  { to: "/settings",  label: "Settings",      icon: Settings },
];

export default function Sidebar({ engine }: { engine: any | null }) {
  return (
    <aside className="w-64 shrink-0 border-r border-bg-border bg-bg-soft/60 backdrop-blur-sm flex flex-col">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-bg-border">
        <div className="size-9 rounded-lg bg-accent/20 grid place-items-center shadow-glow">
          <Cpu className="size-5 text-accent-glow" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-wide">PQC Gateway</div>
          <div className="text-[11px] text-muted">v0.1 · plug-and-play</div>
        </div>
      </div>

      <nav className="p-3 space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) => isActive ? "nav-link-active" : "nav-link"}
          >
            <Icon className="size-4 opacity-80" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto p-4 text-xs text-muted">
        {engine ? (
          <div className="space-y-1.5">
            <div className="flex justify-between"><span>Backend</span><span className="text-slate-300">{engine.backend}</span></div>
            <div className="flex justify-between"><span>KEM</span><span className="text-slate-300">{engine.kem_alg}</span></div>
            <div className="flex justify-between"><span>Sig</span><span className="text-slate-300">{engine.sig_alg}</span></div>
            <div className="flex justify-between"><span>Hybrid</span><span className="text-slate-300">{engine.hybrid ? "X25519+ML-KEM" : "off"}</span></div>
            <div className="pt-2">
              <span className={
                engine.pqc_grade === "demo"
                  ? "badge-warn"
                  : engine.pqc_grade === "nist-strict"
                  ? "badge-ok"
                  : "badge-pqc"
              }>
                {engine.pqc_grade}
              </span>
            </div>
          </div>
        ) : (
          <div>connecting…</div>
        )}
      </div>
    </aside>
  );
}
