from __future__ import annotations

import csv
import io
import time
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class ReturnPoint:
    symbol: str
    value: float
    previous_close: float
    latest_close: float
    previous_date: str
    latest_date: str
    source: str


class YahooChartClient:
    base_url = "https://query2.finance.yahoo.com"

    async def daily_return(self, symbol: str) -> ReturnPoint:
        encoded = quote(symbol, safe="")
        url = f"{self.base_url}/v8/finance/chart/{encoded}?range=10d&interval=1d"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quotes = result["indicators"]["quote"][0]
        closes = quotes.get("close") or []
        points: List[tuple[str, float]] = []
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            date = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
            points.append((date, float(close)))
        if len(points) < 2:
            raise ValueError(f"not enough Yahoo daily bars for {symbol}")

        previous_date, previous_close = points[-2]
        latest_date, latest_close = points[-1]
        if previous_close <= 0:
            raise ValueError(f"invalid previous close for {symbol}")
        return ReturnPoint(
            symbol=symbol,
            value=latest_close / previous_close - 1.0,
            previous_close=previous_close,
            latest_close=latest_close,
            previous_date=previous_date,
            latest_date=latest_date,
            source="yahoo_chart",
        )


class FredCsvClient:
    base_url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    series_by_symbol = {
        "^GSPC": "SP500",
        "^NDX": "NASDAQ100",
        "^VIX": "VIXCLS",
        "USDKRW=X": "DEXKOUS",
    }

    async def daily_return(self, symbol: str) -> ReturnPoint:
        series_id = self.series_by_symbol[symbol]
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(self.base_url, params={"id": series_id})
            response.raise_for_status()

        rows = csv.DictReader(io.StringIO(response.text))
        points: List[tuple[str, float]] = []
        for row in rows:
            date = row.get("observation_date") or row.get("DATE") or row.get("date")
            raw_value = row.get(series_id) or row.get("VALUE") or row.get("value")
            if not date or not raw_value or raw_value == ".":
                continue
            try:
                points.append((date, float(raw_value)))
            except ValueError:
                continue
        if len(points) < 2:
            raise ValueError(f"not enough FRED observations for {series_id}")

        previous_date, previous_close = points[-2]
        latest_date, latest_close = points[-1]
        if previous_close <= 0:
            raise ValueError(f"invalid FRED previous value for {series_id}")
        return ReturnPoint(
            symbol=symbol,
            value=latest_close / previous_close - 1.0,
            previous_close=previous_close,
            latest_close=latest_close,
            previous_date=previous_date,
            latest_date=latest_date,
            source=f"fred:{series_id}",
        )


_CACHE: Dict[tuple[str, ...], tuple[float, Dict[str, ReturnPoint], List[str]]] = {}


async def fetch_overseas_returns(symbols: Iterable[str], ttl_seconds: int = 300) -> tuple[Dict[str, ReturnPoint], List[str]]:
    symbol_key = tuple(sorted(symbols))
    now = time.time()
    cached = _CACHE.get(symbol_key)
    if cached and now - cached[0] <= ttl_seconds:
        return dict(cached[1]), list(cached[2])

    yahoo = YahooChartClient()
    fred = FredCsvClient()
    returns: Dict[str, ReturnPoint] = {}
    warnings: List[str] = []

    semaphore = asyncio.Semaphore(8)

    async def fetch_symbol(symbol: str) -> tuple[str, Optional[ReturnPoint], List[str]]:
        async with semaphore:
            try:
                return symbol, await yahoo.daily_return(symbol), []
            except Exception as exc:
                if symbol not in fred.series_by_symbol:
                    return symbol, None, [f"{symbol}: Yahoo fetch failed ({exc})"]
            try:
                return symbol, await fred.daily_return(symbol), []
            except Exception as exc:
                return symbol, None, [f"{symbol}: Yahoo/FRED fetch failed ({exc})"]

    for symbol, point, symbol_warnings in await asyncio.gather(*(fetch_symbol(symbol) for symbol in symbols)):
        if point is not None:
            returns[symbol] = point
        warnings.extend(symbol_warnings)

    _CACHE[symbol_key] = (now, dict(returns), list(warnings))
    return returns, warnings


def serialize_returns(returns: Dict[str, ReturnPoint]) -> Dict[str, Dict]:
    return {symbol: asdict(point) for symbol, point in returns.items()}
