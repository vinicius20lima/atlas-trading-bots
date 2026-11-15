"""Market-data interface shared by Binance and the exchange stubs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from atlas.models import AccountSnapshot, Candle, Ticker


class MarketDataAdapter(ABC):
    name: str

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        """Return closed candles, oldest first."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """Return the latest public quote."""

    def get_account(self) -> AccountSnapshot | None:
        """Optional read-only account. Default is unsupported."""
        return None
