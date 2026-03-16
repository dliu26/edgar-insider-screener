"use client";
import { useEffect, useState } from "react";
import { clsx } from "clsx";
import type { FilingRecord, FilingDetailResponse } from "@/types";
import { fetchJSON } from "@/lib/api";
import { SignalBadge } from "@/components/dashboard/SignalBadge";
import { TransactionChart } from "./TransactionChart";
import {
  formatCurrency,
  formatShares,
  formatDate,
  formatMarketCap,
  shortenTitle,
} from "@/lib/formatters";

interface Props {
  filing: FilingRecord | null;
  onClose: () => void;
}

export function DetailPanel({ filing, onClose }: Props) {
  const [detail, setDetail] = useState<FilingDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!filing) {
      setDetail(null);
      return;
    }
    setLoading(true);
    fetchJSON<FilingDetailResponse>(`api/filings/${encodeURIComponent(filing.id)}`)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filing?.id]);

  const isOpen = !!filing;

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={clsx(
          "fixed top-0 right-0 h-full w-full max-w-lg bg-surface-800 border-l border-white/10 z-40 overflow-y-auto transition-transform duration-300",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {filing && (
          <div className="p-6">
            {/* Header */}
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-2xl font-bold text-white">{filing.ticker || "—"}</span>
                  <span className="text-gray-400">·</span>
                  <span className="text-gray-400 text-sm">{filing.issuerName}</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {filing.signals.map((s) => (
                    <SignalBadge key={s} signal={s} />
                  ))}
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-gray-500 hover:text-gray-300 ml-4 flex-shrink-0"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3 mb-6">
              {[
                { label: "Total Value", value: formatCurrency(filing.totalValue) },
                { label: "Shares Bought", value: formatShares(filing.shares) },
                { label: "Price / Share", value: formatCurrency(filing.pricePerShare) },
                { label: "Market Cap", value: formatMarketCap(filing.marketCap) },
                { label: "Transaction Date", value: formatDate(filing.transactionDate) },
                { label: "Post-Txn Shares", value: formatShares(filing.postTransactionShares) },
              ].map((item) => (
                <div key={item.label} className="bg-surface-700 rounded-lg p-3">
                  <p className="text-xs text-gray-500 mb-1">{item.label}</p>
                  <p className="text-sm font-medium text-white">{item.value}</p>
                </div>
              ))}
            </div>

            {/* Insider Info */}
            <div className="bg-surface-700 rounded-lg p-4 mb-6">
              <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-3">Insider</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Name</span>
                  <span className="text-sm text-white">{filing.insiderName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Title</span>
                  <span className="text-sm text-white">{filing.title || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">10b5-1 Plan</span>
                  <span className={clsx("text-sm", filing.is10b51 ? "text-yellow-400" : "text-green-400")}>
                    {filing.is10b51 ? "Yes" : "No"}
                  </span>
                </div>
              </div>
            </div>

            {/* Transaction History Chart */}
            {loading ? (
              <div className="h-56 bg-surface-700 rounded-lg animate-pulse" />
            ) : detail && (detail.insiderHistory.length > 0) ? (
              <div className="mb-6">
                <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-3">
                  Insider Transaction History
                </h3>
                <div className="bg-surface-700 rounded-lg p-4">
                  <TransactionChart current={filing} history={detail.insiderHistory} />
                </div>
              </div>
            ) : null}

            {/* SEC Filing Link */}
            <a
              href={filing.filingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-surface-700 hover:bg-surface-600 border border-white/10 text-gray-300 text-sm font-medium py-2.5 rounded-lg transition-colors"
            >
              View SEC Filing →
            </a>
          </div>
        )}
      </div>
    </>
  );
}
