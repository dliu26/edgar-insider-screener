"use client";
import type { Filters, Signal } from "@/types";

const SIGNALS: { value: Signal | ""; label: string }[] = [
  { value: "", label: "All Signals" },
  { value: "FIRST_EVER_BUY", label: "First Ever Buy" },
  { value: "CLUSTER_BUY", label: "Cluster Buy" },
  { value: "HIGH_CONVICTION", label: "High Conviction" },
];

const MIN_VALUES = [
  { value: null, label: "Any Amount" },
  { value: 100_000, label: "> $100K" },
  { value: 500_000, label: "> $500K" },
  { value: 1_000_000, label: "> $1M" },
  { value: 5_000_000, label: "> $5M" },
];

interface FilterBarProps {
  filters: Filters;
  onChange: (f: Filters) => void;
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      <select
        value={filters.signal}
        onChange={(e) => onChange({ ...filters, signal: e.target.value as Signal | "" })}
        className="bg-surface-700 border border-white/10 text-sm text-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:border-white/30"
      >
        {SIGNALS.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <select
        value={filters.minValue ?? ""}
        onChange={(e) => onChange({ ...filters, minValue: e.target.value ? Number(e.target.value) : null })}
        className="bg-surface-700 border border-white/10 text-sm text-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:border-white/30"
      >
        {MIN_VALUES.map((m) => (
          <option key={m.label} value={m.value ?? ""}>{m.label}</option>
        ))}
      </select>

      <input
        type="text"
        placeholder="Filter by title..."
        value={filters.title}
        onChange={(e) => onChange({ ...filters, title: e.target.value })}
        className="bg-surface-700 border border-white/10 text-sm text-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:border-white/30 w-40"
      />
    </div>
  );
}
