import { PriorityTier } from "../api/client";

const styles: Record<PriorityTier, string> = {
  "tier-1": "badge-bad",
  "tier-2": "badge-warn",
  "tier-3": "badge-muted",
};

export default function TierPill({ tier }: { tier: PriorityTier }) {
  return <span className={styles[tier]}>{tier.toUpperCase()}</span>;
}
