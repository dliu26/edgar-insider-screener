"use client";
import { useState, useCallback } from "react";
import type { FilingRecord, Filters, SortConfig } from "@/types";
import { useFilings } from "@/hooks/useFilings";
import { useSignalSummary } from "@/hooks/useSignalSummary";
import { SummaryBar } from "@/components/dashboard/SummaryBar";
import { FilterBar } from "@/components/dashboard/FilterBar";
import { FilingsTable } from "@/components/dashboard/FilingsTable";
import { RefreshButton } from "@/components/dashboard/RefreshButton";
import { DetailPanel } from "@/components/panel/DetailPanel";
import { formatDate } from "@/lib/formatters";

export default function Dashboard() {
  const [filters, setFilters] = useState<Filters>({
    minValue: null,
    title: "",
    signal: "",
  });
  const [sort, setSort] = useState<SortConfig>({ field: "totalValue", dir: "desc" });
  const [selected, setSelected] = useState<FilingRecord | null>(null);

  const { data, isLoading, mutate } = useFilings(filters, sort);
  const { data: summary, mutate: mutateSum } = useSignalSummary();

  const handleSort = useCallback(
    (field: string) => {
      setSort((prev) =>
        prev.field === field
          ? { field, dir: prev.dir === "desc" ? "asc" : "desc" }
          : { field, dir: "desc" }
      );
    },
    []
  );

  const handleRefreshed = useCallback(() => {
    mutate();
    mutateSum();
  }, [mutate, mutateSum]);

  return (
    <div className="min-h-screen bg-surface-900">
      {/* Top Nav */}
      <header className="border-b border-white/10 bg-surface-800 px-6 py-4">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">EDGAR Insider Alpha</h1>
            <p className="text-xs text-gray-500">
              SEC Form 4 · Small/Mid-cap Tech · Last 30 days
              {data?.lastRefreshed && (
                <span className="ml-2">· Updated {formatDate(data.lastRefreshed.split("T")[0])}</span>
              )}
            </p>
          </div>
          <RefreshButton onRefreshed={handleRefreshed} />
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {/* Summary */}
        <SummaryBar summary={summary} />

        {/* Filters */}
        <div className="flex items-center justify-between mb-2">
          <FilterBar filters={filters} onChange={setFilters} />
          {data && (
            <p className="text-xs text-gray-500 ml-4 whitespace-nowrap">
              {data.total} filing{data.total !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Table */}
        <FilingsTable
          filings={data?.filings ?? []}
          selectedId={selected?.id ?? null}
          onSelect={setSelected}
          sort={sort}
          onSort={handleSort}
          isLoading={isLoading}
        />
      </main>

      {/* Detail Side Panel */}
      <DetailPanel filing={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
