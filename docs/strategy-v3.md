# Korea Overnight Lead-Lag 3 ETF Strategy v3

## Definition

This is not a simple "US up, buy Korea" strategy.

It buys only when overseas lead indicators imply a positive fair opening gap,
the domestic ETF opened below that fair gap, the first 5 minutes of local trading
are not breaking down, and spread, premium, FX, and VIX filters pass.

## Timeline

- `08:50`: compute pre-open fair gap candidates.
- `09:00`: capture actual opening gap.
- `09:05-09:06`: evaluate tape, VWAP, spread, premium, and final score.
- `09:06-09:12`: create marketable limit order preview.
- `10:30`: survival check.
- `14:50-15:10`: close remaining position.

## Targets

| ETF | Code | Main lead indicators |
| --- | --- | --- |
| KODEX 200 | 069500 | KOSPI200 night futures, EWY, S&P500, Nasdaq100, USD/KRW, VIX |
| KODEX Semiconductors | 091160 | SOX, SOXX/SMH, NVDA, MU, AMD, TSM, Nasdaq100 |
| KODEX Secondary Battery | 305720 | TSLA, LIT/BATT, ALB, SQM, Nasdaq100, USD/KRW |

## Entry Logic

```text
fair_gap > 0
actual_gap < fair_gap
gap_residual_z > 0.8
overseas_theme_signal_z > 0.6
score > 1.0
09:00-09:05 return >= 0
price not more than -0.25% below open
price near or above 5-minute VWAP
spread and ETF premium normal
no simultaneous VIX and USD/KRW stress
```

Secondary battery is stricter:

```text
gap_residual_z > 1.0
score > 1.2
09:00-09:10 return >= 0
premium < 0.10%
max weight 20%
```

## Order Policy

- Market orders are banned.
- Use marketable limit orders only.
- Cancel if unfilled after `09:12`.
- Do not chase.

## Risk

```text
position_weight = risk_per_trade / stop_pct
```

Initial caps:

- KODEX 200: 20%
- KODEX Semiconductors: 20%
- KODEX Secondary Battery: 15%
