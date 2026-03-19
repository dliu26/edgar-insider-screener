export type Signal = "FIRST_EVER_BUY" | "CLUSTER_BUY" | "HIGH_CONVICTION";
export type InsiderType = "corporate" | "institutional" | "";

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
  adtv: number | null;
  sector: string | null;
  insiderType: "corporate" | "institutional";
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
  days: number | null;
  minValue: number | null;
  maxMarketCap: number | null;
  minAdtv: number | null;
  ticker: string;
  titleGroup: string;
  signal: Signal | "";
  insiderType: InsiderType;
  sector: string;
}

export interface Sc13dRecord {
  id: string;
  issuerName: string;
  ticker: string;
  issuerCik: string;
  filerName: string;
  percentOwned: string | null;
  filingDate: string;
  filingUrl: string;
}

export interface Sc13dResponse {
  filings: Sc13dRecord[];
  total: number;
  lastRefreshed: string | null;
}
