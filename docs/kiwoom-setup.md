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

7. Live mode requires both:

```text
KIWOOM_MODE=live
ALLOW_LIVE_TRADING=true
```

Do not enable live mode before mock orders and execution logs are verified.
