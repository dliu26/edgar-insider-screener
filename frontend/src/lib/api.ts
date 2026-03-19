const BASE = "/api/proxy";

export async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function buildFilingsUrl(params: {
  days?: number | null;
  minValue?: number | null;
  maxMarketCap?: number | null;
  minAdtv?: number | null;
  ticker?: string;
  titleGroup?: string;
  signal?: string;
  insiderType?: string;
  sector?: string;
  sortBy?: string;
  sortDir?: string;
}): string {
  const url = new URLSearchParams();
  if (params.days != null)         url.set("days", String(params.days));
  if (params.minValue != null)     url.set("min_value", String(params.minValue));
  if (params.maxMarketCap != null) url.set("max_market_cap", String(params.maxMarketCap));
  if (params.minAdtv != null)      url.set("min_adtv", String(params.minAdtv));
  if (params.ticker)               url.set("ticker", params.ticker);
  if (params.titleGroup && params.titleGroup !== "all") url.set("title_group", params.titleGroup);
  if (params.signal)               url.set("signal", params.signal);
  if (params.insiderType)          url.set("insider_type", params.insiderType);
  if (params.sector)               url.set("sector", params.sector);
  if (params.sortBy)               url.set("sort_by", params.sortBy);
  if (params.sortDir)              url.set("sort_dir", params.sortDir);
  const qs = url.toString();
  return `api/filings${qs ? `?${qs}` : ""}`;
}
