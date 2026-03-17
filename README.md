# EDGAR Insider Screener

A full-stack tool that monitors SEC EDGAR Form 4 filings for open-market stock purchases by corporate insiders at small-cap tech companies, and flags the ones most likely to be meaningful.

---

## What it does

Every time the pipeline runs it:

1. Pulls the full list of public companies from the SEC's `company_tickers.json`
2. Checks each company's EDGAR submissions to identify those in tech SIC codes (7370–7372, 7374, 7379)
3. Scans their recent Form 4 filings (last 30 business days) for open-market **purchase** transactions (`code = P`) that are **not** covered by a Rule 10b5-1 plan
4. Filters to companies with a market cap ≤ $2 billion (configurable)
5. Applies three signal detectors to surface the most interesting buys

Results are served through a REST API and displayed in a Next.js dashboard with sortable columns, signal badges, and a per-insider transaction history chart.

---

## Signals

### FIRST_EVER_BUY
The insider has no prior Form 4 filings on record. A first-time purchase tends to carry higher conviction than a repeat transaction, because the insider has never previously demonstrated a reason to buy.

### CLUSTER_BUY
Two or more distinct insiders at the same company have made open-market purchases within the last 30 days. Coordinated buying across the leadership team is a stronger signal than any single transaction.

### HIGH_CONVICTION
The total dollar value of the transaction exceeds 10× the insider's estimated annual compensation (CEO/C-suite: $400–500k baseline; directors: $150k baseline). This flags insiders who are putting up a meaningful fraction of their net worth.

---

## Tech stack

| Layer | Technology |
|---|---|
| Data source | SEC EDGAR REST API (`data.sec.gov`, `www.sec.gov`) |
| Backend | Python 3.11 · FastAPI · httpx (async) · aiolimiter |
| XML parsing | lxml |
| Market cap | yfinance |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · Recharts · SWR |

---

## Running locally

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Clone

```bash
git clone https://github.com/dliu26/edgar-insider-screener.git
cd edgar-insider-screener
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example env file and fill in your details:

```bash
cp ../.env.example .env
```

The only required field is `EDGAR_USER_AGENT`. The SEC requires it in the format `"Name email@domain.com"`:

```
EDGAR_USER_AGENT=Daniel Liu daniel@example.com
```

Start the API server:

```bash
uvicorn app.main:app --reload
# Listening on http://localhost:8000
```

### 3. Frontend

In a separate terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```
BACKEND_URL=http://localhost:8000
```

Start the dev server:

```bash
npm run dev
# Open http://localhost:3000
```

### 4. Trigger the pipeline

Either open the dashboard and click **Refresh**, or call the API directly:

```bash
curl -X POST http://localhost:8000/api/refresh
```

The first run performs a full scan of all public companies to build the tech-company list (~10k requests at 8 req/s — expect ~20 minutes). The list is then cached in memory for 24 hours, so subsequent refreshes are fast (~2 minutes).

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/filings` | List filings. Supports `min_value`, `title`, `signal`, `sort_by`, `sort_dir` query params |
| `GET` | `/api/filings/{id}` | Single filing + full insider transaction history |
| `GET` | `/api/signals/summary` | Aggregated signal counts and largest transaction |
| `POST` | `/api/refresh` | Trigger a pipeline run (no-op if already running) |
| `GET` | `/health` | Health check |

---

## Configuration

All settings are read from `backend/.env` (see `.env.example` for all options):

| Variable | Default | Description |
|---|---|---|
| `EDGAR_USER_AGENT` | — | **Required.** `"Name email@domain.com"` per SEC policy |
| `MAX_MARKET_CAP_USD` | `2000000000` | Upper bound for company market cap filter |
| `CACHE_TTL_SECONDS` | `3600` | How long filing results are cached |
| `MARKET_CAP_TTL_SECONDS` | `86400` | How long market cap lookups are cached |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed CORS origins |
| `PORT` | `8000` | Uvicorn port |

---

## Deployment

- **Backend**: Deploy to Railway, set env vars from `.env.example`
- **Frontend**: Deploy to Vercel, set `BACKEND_URL` to your Railway backend URL (used server-side only via the Next.js proxy route)

---

## Notes

- All data comes from the SEC's public EDGAR APIs. No API key is required.
- The SEC rate limit is 10 requests/second per IP. This tool stays at 8 req/s per domain with automatic retry on 429s.
- Only **non-derivative**, open-market purchases are included. Derivative transactions (options, warrants) are excluded.
- Rule 10b5-1 plan transactions are always filtered out.
