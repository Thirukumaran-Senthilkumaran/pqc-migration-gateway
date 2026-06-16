import { GraduationCap, Shield, Target, User, Lightbulb, Building2 } from "lucide-react";

export default function About() {
  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <User className="size-5 text-accent-glow" />
          About
        </h1>
        <p className="text-muted text-sm mt-1">
          The person behind this project and why it exists.
        </p>
      </div>

      <div className="card p-8">
        <div className="flex items-start gap-5">
          <div className="size-16 rounded-2xl bg-gradient-to-br from-accent/30 to-accent-glow/10 border border-accent/30 grid place-items-center shrink-0">
            <span className="text-2xl font-bold text-accent-glow">TS</span>
          </div>
          <div>
            <h2 className="text-xl font-semibold">Thirukumaran Senthilkumaran</h2>
            <p className="text-sm text-accent-glow mt-1">
              Network Security &amp; IAM Enthusiast
            </p>
            <div className="flex items-center gap-2 mt-3 text-xs text-muted">
              <GraduationCap className="size-4" />
              MSc Applied Cybersecurity — University of South Wales
            </div>
          </div>
        </div>

        <div className="mt-8 space-y-4 text-sm text-slate-300 leading-relaxed">
          <p>
            I am a cybersecurity practitioner with a deep interest in network security,
            identity and access management (IAM), and the practical side of building
            defences that organisations can actually operate — not just admire on paper.
            My MSc in Applied Cybersecurity from the{" "}
            <strong className="text-slate-100">University of South Wales</strong> gave me
            a rigorous foundation in threat modelling, secure architecture, and applied
            research; what drives me day to day is turning that knowledge into systems that
            solve real business problems.
          </p>
          <p>
            I believe cybersecurity engineering should be <em>proactive</em>, not reactive.
            Security is not a checkbox owned only by a specialist team — it must be woven
            into infrastructure, processes, and product design from the start. As we move
            deeper into the AI era, attack surfaces will shift faster than policies can
            follow. Networks, endpoints, and cloud estates need to be built with resilience
            in mind: ready to detect anomalies, adapt to new threats, and recover without
            bringing the business to a halt.
          </p>
          <p>
            That mindset — security as an enabler, infrastructure as a first-class
            participant in defence — is what led me to build tools like this gateway
            rather than only writing about the problem.
          </p>
        </div>
      </div>

      <div className="card p-8">
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="size-4 text-amber-400" />
          <h2 className="font-semibold">Motivation to build this</h2>
        </div>
        <div className="space-y-4 text-sm text-slate-300 leading-relaxed">
          <p>
            <strong className="text-slate-100">Enterprises must be ready for the post-quantum era.</strong>{" "}
            NIST has finalised post-quantum cryptography standards (ML-KEM, ML-DSA), and
            nation-states, regulators, and large vendors are already mapping migration
            roadmaps. Critical infrastructure — energy, healthcare, finance, transport —
            has begun inventorying cryptographic dependencies and planning staged
            rollouts because the cost of waiting is measured in decades of harvest-now,
            decrypt-later exposure.
          </p>
          <p>
            Small and medium businesses cannot afford to be left behind. Most SMBs run
            hundreds of legacy devices — printers, sensors, PLCs, cameras — that will
            never receive a firmware update capable of native PQC. Replacing every node
            is unrealistic; ignoring the problem is worse. A <strong className="text-slate-100">gateway-based
            migration path</strong> lets an organisation gain quantum-safe coverage
            immediately, then upgrade endpoints in priority order without a big-bang
            cutover.
          </p>
          <p>
            This project is my answer to that gap: a plug-and-play PQC migration gateway
            that discovers LAN nodes, classifies them by readiness and criticality, wraps
            traffic in NIST-aligned cryptography, and plans a stage-by-stage rollout —
            so that security teams and business owners can move in the same direction,
            at a pace the infrastructure can sustain.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-5">
          <Shield className="size-5 text-accent-glow mb-2" />
          <h3 className="font-medium text-sm">Focus</h3>
          <p className="text-xs text-muted mt-1">
            Network security, IAM, and cryptographic migration at scale.
          </p>
        </div>
        <div className="card p-5">
          <Target className="size-5 text-emerald-400 mb-2" />
          <h3 className="font-medium text-sm">Approach</h3>
          <p className="text-xs text-muted mt-1">
            Proactive, infrastructure-aware security — not bolt-on compliance.
          </p>
        </div>
        <div className="card p-5">
          <Building2 className="size-5 text-amber-400 mb-2" />
          <h3 className="font-medium text-sm">Audience</h3>
          <p className="text-xs text-muted mt-1">
            SMBs and security teams preparing for PQC without replacing every device.
          </p>
        </div>
      </div>
    </div>
  );
}
