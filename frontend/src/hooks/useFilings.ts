import useSWR from "swr";
import { fetchJSON, buildFilingsUrl } from "@/lib/api";
import type { FilingsResponse, Filters, SortConfig } from "@/types";

export function useFilings(filters: Filters, sort: SortConfig) {
  const key = buildFilingsUrl({
    days: filters.days ?? undefined,
    minValue: filters.minValue,
    maxMarketCap: filters.maxMarketCap,
    minAdtv: filters.minAdtv,
    ticker: filters.ticker || undefined,
    titleGroup: filters.titleGroup || undefined,
    signal: filters.signal || undefined,
    insiderType: filters.insiderType || undefined,
    sector: filters.sector || undefined,
    sortBy: sort.field,
    sortDir: sort.dir,
  });

  const { data, error, isLoading, mutate } = useSWR<FilingsResponse>(
    key,
    (url: string) => fetchJSON(url),
    { refreshInterval: 0, revalidateOnFocus: false }
  );

  return { data, error, isLoading, mutate };
}
