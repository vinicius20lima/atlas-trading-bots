"""Binance public market data, plus an optional signed read-only account call.

Market data defaults to https://data-api.binance.vision because api.binance.com
returns HTTP 451 from some regions. The signed account endpoint stays on
api.binance.com and is never used to place orders.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from atlas.data.base import MarketDataAdapter
from atlas.errors import AdapterError, AdapterUnavailable, DataError
from atlas.http import GetJson, build_url, http_get_json
from atlas.models import AccountSnapshot, Balance, Candle, Ticker

INTERVALS = {"1m", "5m", "15m", "1h", "4h", "1d"}
_SYMBOL = re.compile(r"^[A-Z0-9]{5,20}$")

# Official example query from the Binance spot docs, checked with HMAC-SHA256.
SIGN_EXAMPLE_QUERY = (
    "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1"
    "&recvWindow=5000&timestamp=1499827319559"
)
SIGN_EXAMPLE_SECRET = "NhqPtmdSJVfOiYXikKsVMc6H38o3eZU2cDaGwKsByMW"
SIGN_EXAMPLE_SIGNATURE = "95e9472777d1454ba9e98240a0248c914a1d81fad78d6e7f04041d49c30e2566"


def sign_query(secret: str, query: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def parse_kline(row: list[Any]) -> Candle:
    if not isinstance(row, list) or len(row) < 7:
        raise DataError("kline row is too short")
    open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
    close_time = datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC)
    return Candle(
        open_time=open_time,
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
        close_time=close_time,
    )


def parse_ticker(payload: dict[str, Any]) -> Ticker:
    when = payload.get("closeTime")
    if when is None:
        moment = datetime.now(UTC)
    else:
        moment = datetime.fromtimestamp(int(when) / 1000, tz=UTC)
    return Ticker(
        symbol=str(payload["symbol"]),
        bid=float(payload["bidPrice"]),
        ask=float(payload["askPrice"]),
        last=float(payload.get("lastPrice", payload["bidPrice"])),
        time=moment,
    )


def parse_account(payload: dict[str, Any]) -> AccountSnapshot:
    rates = payload.get("commissionRates") or {}
    taker = _optional_float(rates.get("taker"))
    maker = _optional_float(rates.get("maker"))
    if taker is None and payload.get("takerCommission") is not None:
        taker = float(payload["takerCommission"]) / 10000.0
    if maker is None and payload.get("makerCommission") is not None:
        maker = float(payload["makerCommission"]) / 10000.0
    balances = tuple(
        Balance(asset=item["asset"], free=float(item["free"]), locked=float(item["locked"]))
        for item in payload.get("balances", [])
        if float(item.get("free", 0)) or float(item.get("locked", 0))
    )
    return AccountSnapshot(
        can_trade=bool(payload.get("canTrade")),
        balances=balances,
        taker_commission=taker,
        maker_commission=maker,
    )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


class BinanceAdapter(MarketDataAdapter):
    name = "binance"

    def __init__(
        self,
        get_json: GetJson | None = None,
        data_base_url: str = "https://data-api.binance.vision",
        api_base_url: str = "https://api.binance.com",
        api_key: str | None = None,
        api_secret: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
        page_size: int = 1000,
    ) -> None:
        self._get_json = get_json or (lambda url, headers=None: http_get_json(url, headers))
        self.data_base_url = data_base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = (
            api_secret if api_secret is not None else os.environ.get("BINANCE_API_SECRET", "")
        )
        self._sleep = sleep
        self._now = now or (lambda: datetime.now(UTC))
        self.page_size = page_size

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        self._validate(symbol, interval)
        if start is None:
            params: dict[str, object] = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit or 500,
            }
            rows = self._public("/api/v3/klines", params)
            return self._finalize(rows, end)

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000) if end is not None else None
        rows: list[Any] = []
        pages = 0
        while True:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "limit": self.page_size,
            }
            if end_ms is not None:
                params["endTime"] = end_ms
            batch = self._public("/api/v3/klines", params)
            pages += 1
            if not batch:
                break
            rows.extend(batch)
            last_open = int(batch[-1][0])
            next_open = last_open + 1
            if len(batch) < self.page_size:
                break
            if end_ms is not None and next_open > end_ms:
                break
            if pages > 40:
                raise AdapterError(f"stopped pagination for {symbol} {interval} after 40 pages")
            start_ms = next_open
            self._sleep(0.05)
        return self._finalize(rows, end)

    def get_ticker(self, symbol: str) -> Ticker:
        self._validate(symbol, "1m")
        payload = self._public("/api/v3/ticker/24hr", {"symbol": symbol})
        if not isinstance(payload, dict):
            raise DataError("ticker payload is not an object")
        return parse_ticker(payload)

    def get_account(self) -> AccountSnapshot | None:
        """Signed GET /api/v3/account. Returns None when the key pair is absent."""
        if not self.api_key or not self.api_secret:
            return None
        query = urllib.parse.urlencode({"recvWindow": 5000, "timestamp": int(time.time() * 1000)})
        signature = sign_query(self.api_secret, query)
        url = f"{self.api_base_url}/api/v3/account?{query}&signature={signature}"
        if self.api_secret in url:
            raise AdapterError("refusing to send a URL that contains the API secret")
        payload = self._get(url, {"X-MBX-APIKEY": self.api_key})
        if not isinstance(payload, dict):
            raise DataError("account payload is not an object")
        return parse_account(payload)

    def _public(self, path: str, params: dict[str, object]) -> Any:
        url = build_url(self.data_base_url, path, params)
        return self._get(url, None)

    def _get(self, url: str, headers: dict[str, str] | None) -> Any:
        try:
            return self._get_json(url, headers)
        except AdapterError as exc:
            text = str(exc)
            if "451" in text or "restricted location" in text:
                raise AdapterUnavailable(
                    "Binance refused this host (HTTP 451). Public klines use "
                    "https://data-api.binance.vision via BINANCE_DATA_BASE_URL. "
                    "The signed account host api.binance.com can still be blocked here. "
                    "No Cloudflare bypass is attempted."
                ) from exc
            raise

    def _finalize(self, rows: list[Any], end: datetime | None) -> list[Candle]:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        candles: list[Candle] = []
        seen: set[datetime] = set()
        for row in rows:
            candle = parse_kline(row)
            if candle.open_time in seen:
                continue
            if candle.close_time > now:
                continue
            if end is not None and candle.close_time > end:
                continue
            seen.add(candle.open_time)
            candles.append(candle)
        candles.sort(key=lambda item: item.open_time)
        return candles

    @staticmethod
    def _validate(symbol: str, interval: str) -> None:
        if not _SYMBOL.match(symbol):
            raise DataError(f"invalid symbol {symbol!r}")
        if interval not in INTERVALS:
            raise DataError(f"unsupported interval {interval!r}")
