from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import httpx


@dataclass(frozen=True)
class KiwoomConfig:
    base_url: str
    app_key: str
    secret_key: str


class KiwoomRestClient:
    def __init__(self, config: KiwoomConfig):
        self.config = config
        self.access_token: Optional[str] = None

    async def issue_token(self) -> Dict[str, Any]:
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "secretkey": self.config.secret_key,
        }
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=20) as client:
            response = await client.post("/oauth2/token", json=payload)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("token") or data.get("access_token")
            return data

    async def request_tr(self, api_id: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self.access_token:
            await self.issue_token()
        headers = {
            "authorization": f"Bearer {self.access_token}",
            "api-id": api_id,
            "content-type": "application/json;charset=UTF-8",
        }
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=20) as client:
            response = await client.post(path, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    async def quote(self, code: str) -> Dict[str, Any]:
        return await self.request_tr("ka10004", "/api/dostk/mrkcond", {"stk_cd": code})

    async def minute_bars(self, code: str, tick_scope: str = "1") -> Dict[str, Any]:
        return await self.request_tr(
            "ka10080",
            "/api/dostk/chart",
            {"stk_cd": code, "tic_scope": tick_scope, "upd_stkpc_tp": "1"},
        )

    async def daily_bars(self, code: str, base_date: str = "") -> Dict[str, Any]:
        base_dt = base_date or datetime.now().strftime("%Y%m%d")
        return await self.request_tr(
            "ka10081",
            "/api/dostk/chart",
            {"stk_cd": code, "base_dt": base_dt, "upd_stkpc_tp": "1"},
        )

    async def buy_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return await self.request_tr(
            "kt10000",
            "/api/dostk/ordr",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": code,
                "ord_qty": str(quantity),
                "ord_uv": str(limit_price),
                "trde_tp": "0",
                "cond_uv": "",
                "acnt_no": account_no,
            },
        )

    async def sell_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return await self.request_tr(
            "kt10001",
            "/api/dostk/ordr",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": code,
                "ord_qty": str(quantity),
                "ord_uv": str(limit_price),
                "trde_tp": "0",
                "cond_uv": "",
                "acnt_no": account_no,
            },
        )


class MockKiwoomClient:
    async def issue_token(self) -> Dict[str, Any]:
        return {"access_token": "mock-token", "expires_in": 86400}

    async def quote(self, code: str) -> Dict[str, Any]:
        sample = {
            "069500": {"bid_req_base_tm": "090600", "sel_fpr_bid": "40950", "buy_fpr_bid": "40945"},
            "091160": {"bid_req_base_tm": "090600", "sel_fpr_bid": "45600", "buy_fpr_bid": "45550"},
            "305720": {"bid_req_base_tm": "090600", "sel_fpr_bid": "12850", "buy_fpr_bid": "12835"},
        }
        return sample.get(code, {"sel_fpr_bid": "10000", "buy_fpr_bid": "9995"})

    async def minute_bars(self, code: str, tick_scope: str = "1") -> Dict[str, Any]:
        base = {
            "069500": 40900,
            "091160": 45620,
            "305720": 12830,
        }.get(code, 10000)
        return {
            "stk_cd": code,
            "stk_min_pole_chart_qry": [
                {
                    "cntr_tm": "20260710090500",
                    "cur_prc": str(base),
                    "open_pric": str(base - 20),
                    "high_pric": str(base + 20),
                    "low_pric": str(base - 30),
                    "trde_qty": "25000",
                    "acc_trde_qty": "120000",
                },
                {
                    "cntr_tm": "20260710090000",
                    "cur_prc": str(base - 20),
                    "open_pric": str(base - 20),
                    "high_pric": str(base),
                    "low_pric": str(base - 35),
                    "trde_qty": "95000",
                    "acc_trde_qty": "95000",
                },
            ],
        }

    async def daily_bars(self, code: str, base_date: str = "") -> Dict[str, Any]:
        values = {
            "069500": (40750, 40880, 40920, 1_800_000),
            "091160": (45200, 45500, 45620, 2_200_000),
            "305720": (12780, 12820, 12830, 1_400_000),
        }
        previous_close, open_price, close_price, volume = values.get(code, (9900, 9950, 10000, 500000))
        return {
            "stk_cd": code,
            "stk_dt_pole_chart_qry": [
                {
                    "dt": "20260710",
                    "cur_prc": str(close_price),
                    "open_pric": str(open_price),
                    "high_pric": str(close_price + 50),
                    "low_pric": str(open_price - 50),
                    "trde_qty": str(volume),
                },
                {
                    "dt": "20260709",
                    "cur_prc": str(previous_close),
                    "open_pric": str(previous_close - 50),
                    "high_pric": str(previous_close + 80),
                    "low_pric": str(previous_close - 120),
                    "trde_qty": str(volume),
                },
            ],
        }

    async def buy_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return {
            "status": "mock_accepted",
            "side": "BUY",
            "code": code,
            "quantity": quantity,
            "limit_price": limit_price,
            "account_no": account_no[-4:] if account_no else "mock",
        }

    async def sell_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return {
            "status": "mock_accepted",
            "side": "SELL",
            "code": code,
            "quantity": quantity,
            "limit_price": limit_price,
            "account_no": account_no[-4:] if account_no else "mock",
        }


def build_kiwoom_client(mode: str, base_url: str, app_key: str, secret_key: str):
    if mode in {"local", "sample", "fake"} or not app_key or not secret_key:
        return MockKiwoomClient()
    return KiwoomRestClient(KiwoomConfig(base_url=base_url, app_key=app_key, secret_key=secret_key))
