"""GMGN is not a Binance-style BRL kline source.

Read-only GMGN OpenAPI calls live in atlas.exec.gmgn. This adapter only exists
so the data registry can say, clearly, that GMGN does not replace Binance for
BTCBRL / ETHBRL / SOLBRL in v0.1.
"""

from __future__ import annotations

from datetime import datetime

from atlas.data.base import MarketDataAdapter
from atlas.errors import AdapterUnavailable
from atlas.models import Candle, Ticker

_REASON = (
    "GMGN does not provide Binance-style BRL klines. "
    "On-chain reads go through atlas.exec.gmgn and require GMGN_API_KEY. "
    "Swap routes are disabled in v0.1.0."
)


class GMGNMarketAdapter(MarketDataAdapter):
    name = "gmgn"

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
