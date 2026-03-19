"use client";
import { useState, useCallback, useMemo } from "react";
import useSWR from "swr";
import type { FilingRecord, Filters, SignalSummary, SortConfig, Sc13dResponse } from "@/types";
import { useFilings } from "@/hooks/useFilings";
import { fetchJSON } from "@/lib/api";
import { SummaryBar } from "@/components/dashboard/SummaryBar";
import { FilterBar } from "@/components/dashboard/FilterBar";
import { FilingsTable } from "@/components/dashboard/FilingsTable";
import { Sc13dTable } from "@/components/dashboard/Sc13dTable";
import { RefreshButton } from "@/components/dashboard/RefreshButton";
import { DetailPanel } from "@/components/panel/DetailPanel";
import { formatDate } from "@/lib/formatters";

const EMPTY_FILTERS: Filters = {
  days: 90, minValue: null, maxMarketCap: null, minAdtv: null,
  ticker: "", titleGroup: "all", signal: "", insiderType: "", sector: "",
};

type Tab = "form4" | "sc13d";

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("form4");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SortConfig>({ field: "totalValue", dir: "desc" });
  const [selected, setSelected] = useState<FilingRecord | null>(null);

  const { data, isLoading, mutate } = useFilings(filters, sort);
  const { data: sc13dData, mutate: mutateSc13d } = useSWR<Sc13dResponse>(
    "api/sc13d",
    (url: string) => fetchJSON(url),
    { refreshInterval: 0, revalidateOnFocus: false }
  );

  const summary = useMemo<SignalSummary | undefined>(() => {
    const filings = data?.filings;
    if (!filings) return undefined;
    const clusterIssuers = new Set(
      filings.filter((f) => f.signals.includes("CLUSTER_BUY")).map((f) => f.issuerCik)
    );
    return {
      totalSignals: filings.filter((f) => f.signals.length > 0).length,
      clusterBuys: clusterIssuers.size,
      firstEverBuys: filings.filter((f) => f.signals.includes("FIRST_EVER_BUY")).length,
      highConviction: filings.filter((f) => f.signals.includes("HIGH_CONVICTION")).length,
      largestTransaction: filings.reduce<FilingRecord | null>(
        (max, f) => (max === null || f.totalValue > max.totalValue ? f : max),
        null
      ),
    };
  }, [data?.filings]);

  const handleSort = useCallback((field: string) => {
    setSort((prev) =>
      prev.field === field
        ? { field, dir: prev.dir === "desc" ? "asc" : "desc" }
        : { field, dir: "desc" }
    );
  }, []);

  const handleRefreshed = useCallback(() => {
    mutate();
    mutateSc13d();
  }, [mutate, mutateSc13d]);

  const tabCls = (t: Tab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      tab === t
        ? "border-green-500 text-white"
        : "border-transparent text-gray-500 hover:text-gray-300"
    }`;

  return (
    <div className="min-h-screen bg-surface-900">
      <header className="border-b border-white/10 bg-surface-800 px-6 py-4">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">EDGAR Insider Alpha</h1>
            <p className="text-xs text-gray-500">
              SEC Form 4 · Small/Mid-cap Tech · Open Market Purchases
              {data?.lastRefreshed && (
                <span className="ml-2">· Updated {formatDate(data.lastRefreshed.split("T")[0])}</span>
              )}
            </p>
          </div>
          <RefreshButton onRefreshed={handleRefreshed} />
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">
        <SummaryBar summary={summary} />

        {/* Tabs */}
        <div className="flex gap-1 border-b border-white/10 mb-4">
          <button className={tabCls("form4")} onClick={() => setTab("form4")}>
            Form 4 — Insider Purchases
          </button>
          <button className={tabCls("sc13d")} onClick={() => setTab("sc13d")}>
            Schedule 13D — 5%+ Ownership
            {sc13dData && sc13dData.total > 0 && (
              <span className="ml-2 text-xs bg-green-600/30 text-green-400 px-1.5 py-0.5 rounded">
                {sc13dData.total}
              </span>
            )}
          </button>
        </div>

        {tab === "form4" && (
          <>
            <div className="flex items-center justify-between mb-2">
              <FilterBar filters={filters} onChange={setFilters} />
              {data && (
                <p className="text-xs text-gray-500 ml-4 whitespace-nowrap">
                  {data.total} filing{data.total !== 1 ? "s" : ""}
                </p>
              )}
            </div>
            <FilingsTable
              filings={data?.filings ?? []}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
              sort={sort}
              onSort={handleSort}
              isLoading={isLoading}
            />
          </>
        )}

        {tab === "sc13d" && (
          <Sc13dTable filings={sc13dData?.filings ?? []} isLoading={!sc13dData} />
        )}
      </main>

      <DetailPanel filing={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
