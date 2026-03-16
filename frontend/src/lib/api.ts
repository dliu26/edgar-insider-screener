const BASE = "/api/proxy";

export async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function buildFilingsUrl(params: {
  minValue?: number | null;
  title?: string;
  signal?: string;
  sortBy?: string;
  sortDir?: string;
}): string {
  const url = new URLSearchParams();
  if (params.minValue != null) url.set("min_value", String(params.minValue));
  if (params.title) url.set("title", params.title);
  if (params.signal) url.set("signal", params.signal);
  if (params.sortBy) url.set("sort_by", params.sortBy);
  if (params.sortDir) url.set("sort_dir", params.sortDir);
  const qs = url.toString();
  return `api/filings${qs ? `?${qs}` : ""}`;
}
