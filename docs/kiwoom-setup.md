# Kiwoom REST Setup

1. Create or confirm a Kiwoom Securities account.
2. Apply for Kiwoom REST API access.
3. Enable mock trading first.
4. Copy `.env.example` to `.env`.
5. Fill:

```text
KIWOOM_MODE=mock
KIWOOM_APP_KEY=...
KIWOOM_SECRET_KEY=...
KIWOOM_ACCOUNT_NO=...
```

6. Start the API and verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/strategy/today
```

7. If your app key was issued for live investment, use the live API domain even
   while keeping trading disabled:

```text
KIWOOM_MODE=live
KIWOOM_BASE_URL=https://api.kiwoom.com
ALLOW_LIVE_TRADING=false
```

This allows token and quote checks without enabling live order submission.

8. Live order submission requires both:

```text
KIWOOM_MODE=live
ALLOW_LIVE_TRADING=true
```

Do not enable live mode before mock orders and execution logs are verified.

Useful checks:

```bash
curl http://localhost:8000/kiwoom/token/check
curl http://localhost:8000/kiwoom/quote/091160
```
