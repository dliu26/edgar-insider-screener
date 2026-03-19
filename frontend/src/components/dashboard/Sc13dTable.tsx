import type { Sc13dRecord } from "@/types";
import { formatDate } from "@/lib/formatters";

interface Props {
  filings: Sc13dRecord[];
  isLoading: boolean;
}

export function Sc13dTable({ filings, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-14 bg-surface-800 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-white/5">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 bg-surface-800">
            {["Company", "Filer / Acquirer", "% Owned", "Filing Date", "SEC Filing"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 bg-surface-900">
          {filings.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                No Schedule 13D filings found for watchlist companies in the last 180 days.
              </td>
            </tr>
          ) : (
            filings.map((f) => (
              <tr key={f.id} className="hover:bg-surface-700 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{f.ticker || "—"}</div>
                  <div className="text-xs text-gray-400 truncate max-w-[180px]">{f.issuerName}</div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-200 truncate max-w-[220px]">
                  {f.filerName || "—"}
                </td>
                <td className="px-4 py-3 text-sm text-gray-400">
                  {f.percentOwned ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">
                  {formatDate(f.filingDate)}
                </td>
                <td className="px-4 py-3">
                  <a
                    href={f.filingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:text-blue-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View →
                  </a>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
