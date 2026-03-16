import useSWR from "swr";
import { fetchJSON, buildFilingsUrl } from "@/lib/api";
import type { FilingsResponse, Filters, SortConfig } from "@/types";

export function useFilings(filters: Filters, sort: SortConfig) {
  const key = buildFilingsUrl({
    minValue: filters.minValue,
    title: filters.title,
    signal: filters.signal || undefined,
    sortBy: sort.field,
    sortDir: sort.dir,
  });

  const { data, error, isLoading, mutate } = useSWR<FilingsResponse>(
    key,
    (url: string) => fetchJSON(url),
    {
      refreshInterval: 0,
      revalidateOnFocus: false,
    }
  );

  return { data, error, isLoading, mutate };
}
