# kr-quante

Domestic Korean ETF quant trading system focused on one strategy:

**Korea Overnight Lead-Lag Multi-Theme ETF Strategy v4**

The system watches liquid domestic ETFs across core market beta, semiconductors,
secondary battery, energy, defense/space, shipbuilding, robotics, nuclear, bio,
and AI semiconductor equipment. It estimates the fair opening gap from overseas
lead indicators, waits for the first 5 minutes of Korean trading, and only buys
themes that appear under-reacted after market-quality and shock filters pass.

## Strategy Targets

- `069500` KODEX 200
- `091160` KODEX Semiconductors
- `305720` KODEX Secondary Battery Industry
- `117460` KODEX Energy Chemicals
- `463250` TIGER K-Defense & Space
- `466920` SOL Shipbuilding TOP3 Plus
- `445290` KODEX Robot Active
- `433500` ACE Nuclear TOP10
- `364970` TIGER Bio TOP10
- `471990` KODEX AI Semiconductor Equipment

## Safety Defaults

- Kiwoom mock API is the default.
- Live trading is disabled by default.
- Market orders are disallowed.
- Orders require preview and manual approval.
- Auto trading can buy up to four qualified ETFs per day.
- The auto engine avoids putting more than 40% of the daily budget into one ETF.
- Severe risk-off conditions block new buys.

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
- Shock guard: new buys are blocked when VIX, USD/KRW, SPY, QQQ, or EWY signal
  severe overnight risk-off conditions.

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

## Auto Trading

The dashboard includes an automatic trading panel.

Default behavior:

- Auto trading is off until enabled in the UI.
- The default daily budget is `10,000 KRW`.
- The engine checks the clock every `5` seconds.
- Buy automation runs only during `09:06-09:12` KST.
- End-of-day exit automation runs only during `14:50-15:10` KST.
- Only limit orders are sent.
- Up to four automatic buy candidates are allowed per day.
- Budget is allocated in whole-share lots across qualified candidates, with a
  per-ETF budget cap.
- If the daily budget is below one ETF share, no order is sent and the reason
  is written to the log.
- Live orders are still blocked unless `ALLOW_LIVE_TRADING=true`.

API endpoints:

```text
GET  /auto/status
GET  /auto/logs
POST /auto/settings
POST /auto/tick
```

Auto-trading state and audit logs are stored locally in
`work/auto_trader_state.json`, which is ignored by Git.

Current PnL shown in the dashboard is order-price based until Kiwoom fill and
position reconciliation are added. Treat it as an operational estimate, not a
confirmed brokerage statement.

## Disclaimer

This is trading infrastructure and research code, not financial advice.
