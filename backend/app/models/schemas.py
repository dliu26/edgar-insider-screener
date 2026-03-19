from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FilingRecord(BaseModel):
    id: str  # accession number
    issuerName: str
    ticker: str
    issuerCik: str
    insiderName: str
    insiderCik: str
    title: str
    transactionDate: str
    transactionType: str  # always "P"
    shares: float
    pricePerShare: float
    totalValue: float
    postTransactionShares: float
    is10b51: bool
    marketCap: Optional[float]
    adtv: Optional[float]           # 3-month avg daily trading volume
    sector: Optional[str]           # e.g. "Software/SaaS", "Cybersecurity"
    insiderType: str = "corporate"  # "corporate" | "institutional"
    signals: list[str]
    filingUrl: str


class FilingsResponse(BaseModel):
    filings: list[FilingRecord]
    total: int
    lastRefreshed: Optional[datetime]


class FilingDetailResponse(FilingRecord):
    insiderHistory: list[FilingRecord] = []


class SignalSummary(BaseModel):
    totalSignals: int
    clusterBuys: int        # unique companies with cluster buys
    firstEverBuys: int
    highConviction: int
    largestTransaction: Optional[FilingRecord]


class RefreshResponse(BaseModel):
    status: str  # "started" | "already_running"


class Sc13dRecord(BaseModel):
    id: str             # accession number
    issuerName: str
    ticker: str
    issuerCik: str
    filerName: str
    percentOwned: Optional[str]
    filingDate: str
    filingUrl: str


class Sc13dResponse(BaseModel):
    filings: list[Sc13dRecord]
    total: int
    lastRefreshed: Optional[datetime]
