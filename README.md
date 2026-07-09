# kr-quante

Domestic Korean ETF quant trading system focused on one strategy:

**Korea Overnight Lead-Lag 3 ETF Strategy v3**

The system watches three domestic ETFs, estimates the fair opening gap from
overseas lead indicators, waits for the first 5 minutes of Korean trading, and
only creates a buy preview when the ETF appears under-reacted and market quality
filters pass.

## Strategy Targets

- `069500` KODEX 200
- `091160` KODEX Semiconductors
- `305720` KODEX Secondary Battery Industry

## Safety Defaults

- Kiwoom mock API is the default.
- Live trading is disabled by default.
- Market orders are disallowed.
- Orders require preview and manual approval.
- Only one ETF can be selected per day.

## Quick Start

```bash
cp .env.example .env
python3 -m unittest discover -s packages/kr_core/tests
python3 -m venv .venv
. .venv/bin/activate
pip install -r services/api/requirements.txt
PYTHONPATH=packages/kr_core/src:services/api uvicorn app.main:app --app-dir services/api --reload --port 8000
```

Web dashboard:

```bash
npm install
npm run web:dev
```

Open `http://localhost:3000`.

## Kiwoom

Kiwoom REST API docs:

- Token endpoint: `POST /oauth2/token`
- Market data endpoint group: `/api/dostk/mrkcond`
- Order endpoint group: `/api/dostk/ordr`

Use mock mode first. Put app keys only in `.env`.

## Disclaimer

This is trading infrastructure and research code, not financial advice.
