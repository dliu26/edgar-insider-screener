"use client";
import { useState } from "react";
import { fetchJSON } from "@/lib/api";
import type { RefreshResponse } from "@/types";

interface RefreshButtonProps {
  onRefreshed: () => void;
}

export function RefreshButton({ onRefreshed }: RefreshButtonProps) {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function handleRefresh() {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetchJSON<RefreshResponse>("api/refresh", { method: "POST" });
      setStatus(res.status === "started" ? "Refresh started…" : "Already running");
      if (res.status === "started") {
        setTimeout(() => {
          onRefreshed();
          setStatus(null);
        }, 5000);
      }
    } catch {
      setStatus("Error triggering refresh");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      {status && <span className="text-xs text-gray-400">{status}</span>}
      <button
        onClick={handleRefresh}
        disabled={loading}
        className="flex items-center gap-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-md transition-colors"
      >
        {loading ? (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        Refresh
      </button>
    </div>
  );
}
