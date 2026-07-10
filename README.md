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

If Kiwoom returns an investment-type mismatch for `mockapi.kiwoom.com`, the key
was likely issued for live investment. In that case use `https://api.kiwoom.com`
for token and quote checks, but keep `ALLOW_LIVE_TRADING=false`.

## Live Data Mode

When Kiwoom credentials are present, `/strategy/today` uses real market data:

- Overseas lead returns: Yahoo chart daily returns, with FRED fallback for
  `SP500`, `NASDAQ100`, `VIXCLS`, and `DEXKOUS`.
- Domestic opening snapshot: Kiwoom daily chart, minute chart, and best bid/ask.
- Entry guard: even if a candidate scores well, it is blocked outside
  `09:06-09:12` KST.

The current free overseas source is practical for research and paper/live
preview, but it is not an institutional data feed. Before increasing size,
replace or cross-check it with a contracted source such as Alpha Vantage,
Tiingo, Polygon, Nasdaq Data Link, or a broker-provided market-data feed.

## Live Trading Runbook

Default live orders are blocked by `ALLOW_LIVE_TRADING=false`.

For a real trading day:

1. Start API and web before `09:00` KST.
2. Open `http://localhost:3000`.
3. Confirm the dashboard says `실제 데이터`.
4. During `09:06-09:12`, click `주문 미리보기`.
5. If a preview exists, check code, quantity, limit price, and risk.
6. Type an approver name and click `승인 후 지정가 매수`.
7. Close the position manually with `수동 청산`, or in Kiwoom, before the close.

To allow live order submission, set this only when you are ready to send real
orders:

```bash
ALLOW_LIVE_TRADING=true
```

Do not run unattended automation until fills, position reconciliation, cancel
handling, and forced EOD exit are implemented.

## Disclaimer

This is trading infrastructure and research code, not financial advice.
