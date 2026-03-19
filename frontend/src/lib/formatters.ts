export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${value.toFixed(2)}`;
}

export function formatAdtv(vol: number | null | undefined): string {
  if (vol == null) return "N/A";
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(0)}K`;
  return vol.toLocaleString();
}

export function formatShares(shares: number): string {
  if (shares >= 1_000_000) return `${(shares / 1_000_000).toFixed(2)}M`;
  if (shares >= 1_000) return `${(shares / 1_000).toFixed(0)}K`;
  return shares.toLocaleString();
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const [year, month, day] = dateStr.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(month) - 1]} ${parseInt(day)}, ${year}`;
}

export function formatMarketCap(cap: number | null): string {
  if (cap == null) return "N/A";
  return formatCurrency(cap);
}

export function shortenTitle(title: string): string {
  const map: Record<string, string> = {
    "chief executive officer": "CEO",
    "chief financial officer": "CFO",
    "chief operating officer": "COO",
    "chief technology officer": "CTO",
    "president": "President",
    "director": "Director",
    "vice president": "VP",
  };
  const lower = title.toLowerCase();
  for (const [key, val] of Object.entries(map)) {
    if (lower.includes(key)) return val;
  }
  return title.length > 20 ? title.slice(0, 20) + "…" : title;
}
