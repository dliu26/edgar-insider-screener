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
    clusterBuys: int
    firstEverBuys: int
    highConviction: int
    largestTransaction: Optional[FilingRecord]


class RefreshResponse(BaseModel):
    status: str  # "started" | "already_running"
