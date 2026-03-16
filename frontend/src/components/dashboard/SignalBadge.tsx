import type { Signal } from "@/types";
import { clsx } from "clsx";

const BADGE_CONFIG: Record<Signal, { label: string; className: string }> = {
  FIRST_EVER_BUY: {
    label: "First Ever",
    className: "bg-red-500/20 text-red-400 border border-red-500/30",
  },
  CLUSTER_BUY: {
    label: "Cluster",
    className: "bg-orange-500/20 text-orange-400 border border-orange-500/30",
  },
  HIGH_CONVICTION: {
    label: "High Conv.",
    className: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  },
};

export function SignalBadge({ signal }: { signal: Signal }) {
  const config = BADGE_CONFIG[signal];
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}
