import type { SignalSummary } from "@/types";
import { formatCurrency } from "@/lib/formatters";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
}

function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="bg-surface-800 rounded-lg p-4 border border-white/5">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-semibold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1 truncate">{sub}</p>}
    </div>
  );
}

export function SummaryBar({ summary }: { summary: SignalSummary | undefined }) {
  if (!summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-surface-800 rounded-lg p-4 h-20 animate-pulse border border-white/5" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <StatCard label="Total Signals" value={summary.totalSignals} />
      <StatCard label="Cluster Buys" value={summary.clusterBuys} />
      <StatCard label="First-Ever Buys" value={summary.firstEverBuys} />
      <StatCard
        label="Largest Transaction"
        value={formatCurrency(summary.largestTransaction?.totalValue ?? null)}
        sub={summary.largestTransaction?.issuerName}
      />
    </div>
  );
}
