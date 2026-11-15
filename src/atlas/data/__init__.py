"""Data adapters."""

from atlas.data.base import MarketDataAdapter
from atlas.data.binance import BinanceAdapter
from atlas.data.foxbit import FoxbitAdapter
from atlas.data.gmgn import GMGNMarketAdapter
from atlas.data.mercadobitcoin import MercadoBitcoinAdapter

__all__ = [
    "BinanceAdapter",
    "FoxbitAdapter",
    "GMGNMarketAdapter",
    "MarketDataAdapter",
    "MercadoBitcoinAdapter",
    "get_adapter",
]


def get_adapter(name: str) -> MarketDataAdapter:
    key = name.strip().lower()
    if key == "binance":
        return BinanceAdapter()
    if key == "foxbit":
        return FoxbitAdapter()
    if key in {"mercadobitcoin", "mercado", "mb"}:
        return MercadoBitcoinAdapter()
    if key == "gmgn":
        return GMGNMarketAdapter()
    raise KeyError(f"unknown adapter {name!r}")
