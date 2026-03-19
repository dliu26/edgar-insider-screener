import { clsx } from "clsx";
import type { FilingRecord } from "@/types";
import { SignalBadge } from "./SignalBadge";
import { formatCurrency, formatPrice, formatAdtv, formatShares, formatDate, formatMarketCap, shortenTitle } from "@/lib/formatters";

interface Props {
  filing: FilingRecord;
  isSelected: boolean;
  onClick: () => void;
}

export function FilingsTableRow({ filing, isSelected, onClick }: Props) {
  const isCluster = filing.signals.includes("CLUSTER_BUY");
  const isFirstEver = filing.signals.includes("FIRST_EVER_BUY");

  return (
    <tr
      onClick={onClick}
      className={clsx(
        "border-l-2 cursor-pointer transition-colors",
        isSelected ? "bg-surface-600" : "hover:bg-surface-700",
        isCluster && !isFirstEver ? "border-l-green-500 bg-green-950/40" : "",
        isFirstEver ? "border-l-red-400" : "",
        !isCluster && !isFirstEver ? "border-l-transparent" : ""
      )}
    >
      <td className="px-4 py-3">
        <div className="font-medium text-white">{filing.ticker || "—"}</div>
        <div className="text-xs text-gray-400 truncate max-w-[160px]">{filing.issuerName}</div>
      </td>
      <td className="px-4 py-3">
        <div className="text-sm text-gray-200 truncate max-w-[140px]">{filing.insiderName}</div>
        <div className="text-xs text-gray-500">{shortenTitle(filing.title)}</div>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="text-sm font-medium text-green-400">{formatCurrency(filing.totalValue)}</div>
        <div className="text-xs text-gray-500">{formatShares(filing.shares)} shares</div>
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-400">
        {formatPrice(filing.pricePerShare)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-400">
        {formatMarketCap(filing.marketCap)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-400">
        {formatAdtv(filing.adtv)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-500">
        {formatDate(filing.transactionDate)}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {filing.signals.map((s) => (
            <SignalBadge key={s} signal={s} />
          ))}
        </div>
      </td>
    </tr>
  );
}
