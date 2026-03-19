"use client";
import { useMemo } from "react";
import type { FilingRecord, SortConfig } from "@/types";
import { FilingsTableRow } from "./FilingsTableRow";
import { clsx } from "clsx";

interface Props {
  filings: FilingRecord[];
  selectedId: string | null;
  onSelect: (f: FilingRecord) => void;
  sort: SortConfig;
  onSort: (field: string) => void;
  isLoading: boolean;
}

const COLUMNS = [
  { key: "ticker",          label: "Company",  sortable: false },
  { key: "insider",         label: "Insider",  sortable: false },
  { key: "totalValue",      label: "Value",    sortable: true  },
  { key: "pricePerShare",   label: "Price/Sh", sortable: false },
  { key: "marketCap",       label: "Mkt Cap",  sortable: true  },
  { key: "adtv",            label: "ADTV",     sortable: true  },
  { key: "transactionDate", label: "Date",     sortable: true  },
  { key: "signals",         label: "Signals",  sortable: false },
];

export function FilingsTable({ filings, selectedId, onSelect, sort, onSort, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
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
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => col.sortable && onSort(col.key)}
                className={clsx(
                  "px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider",
                  col.sortable && "cursor-pointer hover:text-gray-300",
                  col.key === "totalValue" || col.key === "pricePerShare" || col.key === "marketCap" ? "text-right" : ""
                )}
              >
                {col.label}
                {col.sortable && sort.field === col.key && (
                  <span className="ml-1">{sort.dir === "desc" ? "↓" : "↑"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 bg-surface-900">
          {filings.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                No filings match your filters. Try adjusting the criteria above.
              </td>
            </tr>
          ) : (
            filings.map((f) => (
              <FilingsTableRow
                key={f.id}
                filing={f}
                isSelected={f.id === selectedId}
                onClick={() => onSelect(f)}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
