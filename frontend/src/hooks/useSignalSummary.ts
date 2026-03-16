import useSWR from "swr";
import { fetchJSON } from "@/lib/api";
import type { SignalSummary } from "@/types";

export function useSignalSummary() {
  const { data, error, isLoading, mutate } = useSWR<SignalSummary>(
    "api/signals/summary",
    (url: string) => fetchJSON(url),
    {
      refreshInterval: 0,
      revalidateOnFocus: false,
    }
  );

  return { data, error, isLoading, mutate };
}
