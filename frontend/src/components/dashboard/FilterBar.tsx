"use client";
import type { Filters, Signal, InsiderType } from "@/types";

const SIGNALS: { value: Signal | ""; label: string }[] = [
  { value: "", label: "All Signals" },
  { value: "FIRST_EVER_BUY", label: "First Ever Buy" },
  { value: "CLUSTER_BUY", label: "Cluster Buy" },
  { value: "HIGH_CONVICTION", label: "High Conviction" },
];

const DAYS_OPTIONS = [
  { value: 30,  label: "Last 30 days" },
  { value: 60,  label: "Last 60 days" },
  { value: 90,  label: "Last 90 days" },
  { value: 180, label: "Last 180 days" },
  { value: 365, label: "Last 1 year" },
];

const TITLE_GROUPS = [
  { value: "all",             label: "All Titles" },
  { value: "ceo",             label: "CEO" },
  { value: "cfo",             label: "CFO" },
  { value: "coo",             label: "COO" },
  { value: "president",       label: "President" },
  { value: "chairman",        label: "Chairman" },
  { value: "vp",              label: "VP" },
  { value: "general_counsel", label: "General Counsel" },
  { value: "officer",         label: "Officer (Other)" },
  { value: "director",        label: "Director" },
  { value: "10pct_owner",     label: "10% Owner" },
  { value: "other",           label: "Other" },
];

const INSIDER_TYPES: { value: InsiderType; label: string }[] = [
  { value: "",               label: "All Insiders" },
  { value: "corporate",      label: "Corporate Insiders" },
  { value: "institutional",  label: "Institutional (10% Owners)" },
];

const SECTORS = [
  "Software/SaaS",
  "Cybersecurity",
  "Fintech/Payments",
  "Data/AI/Analytics",
  "Infrastructure/Hardware",
  "IT Services",
  "Vertical SaaS",
];

const cls = "bg-surface-700 border border-white/10 text-sm text-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:border-white/30";

const EMPTY_FILTERS: Filters = {
  days: 90, minValue: null, maxMarketCap: null, minAdtv: null,
  ticker: "", titleGroup: "all", signal: "", insiderType: "", sector: "",
};

function isDirty(f: Filters) {
  return f.ticker || f.signal || f.titleGroup !== "all" || f.insiderType ||
    f.sector || f.minValue != null || f.maxMarketCap != null || f.minAdtv != null;
}

interface Props { filters: Filters; onChange: (f: Filters) => void; }

export function FilterBar({ filters, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      <input
        type="text"
        placeholder="Ticker (e.g. DDOG)"
        value={filters.ticker}
        onChange={(e) => onChange({ ...filters, ticker: e.target.value.toUpperCase() })}
        className={`${cls} w-32 uppercase`}
      />

      <select value={filters.days ?? 90} onChange={(e) => onChange({ ...filters, days: Number(e.target.value) })} className={cls}>
        {DAYS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>

      <select value={filters.signal} onChange={(e) => onChange({ ...filters, signal: e.target.value as Signal | "" })} className={cls}>
        {SIGNALS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>

      <select value={filters.titleGroup} onChange={(e) => onChange({ ...filters, titleGroup: e.target.value })} className={cls}>
        {TITLE_GROUPS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>

      <select value={filters.insiderType} onChange={(e) => onChange({ ...filters, insiderType: e.target.value as InsiderType })} className={cls}>
        {INSIDER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>

      <select value={filters.sector} onChange={(e) => onChange({ ...filters, sector: e.target.value })} className={cls}>
        <option value="">All Sectors</option>
        {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>

      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-500">Min $</span>
        <input type="number" placeholder="Value" value={filters.minValue ?? ""}
          onChange={(e) => onChange({ ...filters, minValue: e.target.value ? Number(e.target.value) : null })}
          className={`${cls} w-24`} />
      </div>

      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-500">Max Cap $</span>
        <input type="number" placeholder="e.g. 10000000000" value={filters.maxMarketCap ?? ""}
          onChange={(e) => onChange({ ...filters, maxMarketCap: e.target.value ? Number(e.target.value) : null })}
          className={`${cls} w-32`} />
      </div>

      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-500">Min ADTV</span>
        <input type="number" placeholder="e.g. 500000" value={filters.minAdtv ?? ""}
          onChange={(e) => onChange({ ...filters, minAdtv: e.target.value ? Number(e.target.value) : null })}
          className={`${cls} w-28`} />
      </div>

      {isDirty(filters) && (
        <button onClick={() => onChange(EMPTY_FILTERS)}
          className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1.5 border border-white/10 rounded-md">
          Clear
        </button>
      )}
    </div>
  );
}
