"""Mercado Bitcoin stub.

The public API was blocked by Cloudflare from the environment that bootstrapped
this repository. v0.1 does not try to bypass that block. Binance is primary.
"""

from __future__ import annotations

from datetime import datetime

from atlas.data.base import MarketDataAdapter
from atlas.errors import AdapterUnavailable
from atlas.models import Candle, Ticker

_REASON = (
    "Mercado Bitcoin public API is not used in v0.1.0: requests were blocked by "
    "Cloudflare. This adapter does not bypass that block. Use Binance for "
    "BTCBRL, ETHBRL and SOLBRL."
)


class MercadoBitcoinAdapter(MarketDataAdapter):
    name = "mercadobitcoin"

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
