# EDGAR Insider Alpha

Real-time insider buying signals from SEC EDGAR Form 4 filings, focused on small/mid-cap tech companies.

## Features

- Scrapes Form 4 filings from EDGAR for tech companies (SIC codes 7370-7379)
- Filters to open-market purchases (code P), excluding 10b5-1 plans
- Detects signals: First-Ever Buy, Cluster Buy (2+ insiders same company), High Conviction (>10x annual comp estimate)
- Dark-mode dashboard with filtering, sorting, and detail side panel with transaction history chart

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env and set EDGAR_USER_AGENT to "YourCompany yourname@yourdomain.com"
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000

## Deployment

- **Backend**: Deploy to Railway, set env vars from `.env.example`
- **Frontend**: Deploy to Vercel, set `BACKEND_URL` to your Railway URL (server-side only)

## Environment Variables

See `.env.example` for all required variables.

**Important**: Set `EDGAR_USER_AGENT` to `"YourCompany yourname@yourdomain.com"` — the SEC requires a valid user agent or will block requests.
