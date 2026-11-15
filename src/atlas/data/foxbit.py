"""Foxbit stub. Public BRL candles come from Binance in v0.1."""

from __future__ import annotations

from datetime import datetime

from atlas.data.base import MarketDataAdapter
from atlas.errors import AdapterUnavailable
from atlas.models import Candle, Ticker

_REASON = (
    "Foxbit adapter is a stub in v0.1.0. "
    "Binance public market data is the primary source for BTCBRL, ETHBRL and SOLBRL."
)


class FoxbitAdapter(MarketDataAdapter):
    name = "foxbit"

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        raise AdapterUnavailable(_REASON)

    def get_ticker(self, symbol: str) -> Ticker:
        raise AdapterUnavailable(_REASON)
