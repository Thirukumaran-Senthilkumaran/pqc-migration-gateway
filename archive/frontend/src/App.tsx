import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Nodes from "./pages/Nodes";
import Gateway from "./pages/Gateway";
import Migration from "./pages/Migration";
import PQCEngine from "./pages/PQCEngine";
import Policy from "./pages/Policy";
import SettingsPage from "./pages/Settings";
import About from "./pages/About";
import { useLive } from "./store/useLive";

export default function App() {
  const { engine, connected } = useLive();

  return (
    <div className="h-full flex">
      <Sidebar engine={engine} />
      <main className="flex-1 overflow-auto">
        <header className="px-8 py-4 border-b border-bg-border flex items-center justify-between bg-bg-soft/40 backdrop-blur sticky top-0 z-10">
          <div className="text-sm text-muted">
            <span className={connected ? "text-emerald-400" : "text-amber-400"}>
              ● {connected ? "live" : "reconnecting"}
            </span>
            <span className="mx-2 text-bg-border">|</span>
            Quantum-safe gateway for your local network
          </div>
          <a
            href="https://csrc.nist.gov/projects/post-quantum-cryptography"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted hover:text-slate-200"
          >
            NIST PQC ↗
          </a>
        </header>
        <div className="p-8 max-w-[1400px]">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/nodes" element={<Nodes />} />
            <Route path="/gateway" element={<Gateway />} />
            <Route path="/policy" element={<Policy />} />
            <Route path="/migration" element={<Migration />} />
            <Route path="/pqc" element={<PQCEngine />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
