from __future__ import annotations

from dataclasses import dataclass
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
        return await self.request_tr("ka10080", "/api/dostk/chart", {"stk_cd": code, "tic_scope": tick_scope})

    async def daily_bars(self, code: str, base_date: str = "") -> Dict[str, Any]:
        return await self.request_tr("ka10081", "/api/dostk/chart", {"stk_cd": code, "base_dt": base_date})

    async def buy_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return await self.request_tr(
            "kt10000",
            "/api/dostk/ordr",
            {
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
            "069500": {"sel_fpr_bid": "40950", "buy_fpr_bid": "40945"},
            "091160": {"sel_fpr_bid": "45600", "buy_fpr_bid": "45550"},
            "305720": {"sel_fpr_bid": "12850", "buy_fpr_bid": "12835"},
        }
        return sample.get(code, {"sel_fpr_bid": "10000", "buy_fpr_bid": "9995"})

    async def buy_limit(self, code: str, quantity: int, limit_price: int, account_no: str) -> Dict[str, Any]:
        return {
            "status": "mock_accepted",
            "code": code,
            "quantity": quantity,
            "limit_price": limit_price,
            "account_no": account_no[-4:] if account_no else "mock",
        }


def build_kiwoom_client(mode: str, base_url: str, app_key: str, secret_key: str):
    if mode in {"local", "sample", "fake"} or not app_key or not secret_key:
        return MockKiwoomClient()
    return KiwoomRestClient(KiwoomConfig(base_url=base_url, app_key=app_key, secret_key=secret_key))
