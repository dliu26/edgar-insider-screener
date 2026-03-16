export type Signal = "FIRST_EVER_BUY" | "CLUSTER_BUY" | "HIGH_CONVICTION";

export interface FilingRecord {
  id: string;
  issuerName: string;
  ticker: string;
  issuerCik: string;
  insiderName: string;
  insiderCik: string;
  title: string;
  transactionDate: string;
  transactionType: string;
  shares: number;
  pricePerShare: number;
  totalValue: number;
  postTransactionShares: number;
  is10b51: boolean;
  marketCap: number | null;
  signals: Signal[];
  filingUrl: string;
}

export interface FilingsResponse {
  filings: FilingRecord[];
  total: number;
  lastRefreshed: string | null;
}

export interface FilingDetailResponse extends FilingRecord {
  insiderHistory: FilingRecord[];
}

export interface SignalSummary {
  totalSignals: number;
  clusterBuys: number;
  firstEverBuys: number;
  highConviction: number;
  largestTransaction: FilingRecord | null;
}

export interface RefreshResponse {
  status: "started" | "already_running";
}

export interface SortConfig {
  field: string;
  dir: "asc" | "desc";
}

export interface Filters {
  minValue: number | null;
  title: string;
  signal: Signal | "";
}
