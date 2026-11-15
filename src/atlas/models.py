"""Shared market and order models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from atlas.errors import DataError


def _finite(name: str, value: float) -> float:
    if value != value or value in (float("inf"), float("-inf")):  # NaN
        raise DataError(f"{name} is not finite")
    return value


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime

    def __post_init__(self) -> None:
        if self.open_time.tzinfo is None or self.close_time.tzinfo is None:
            raise DataError("candle timestamps must be timezone-aware")
        if self.close_time < self.open_time:
            raise DataError("candle close_time is before open_time")
        for name in ("open", "high", "low", "close", "volume"):
            _finite(name, getattr(self, name))
        if self.volume < 0:
            raise DataError("volume is negative")
        if self.low > self.high:
            raise DataError("low is above high")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise DataError("high/low do not contain the open and close")


@dataclass(frozen=True, slots=True)
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    time: datetime


@dataclass(frozen=True, slots=True)
class Balance:
    asset: str
    free: float
    locked: float


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Read-only view of a spot account. v0.1 never places orders from this."""

    can_trade: bool
    balances: tuple[Balance, ...]
    taker_commission: float | None = None
    maker_commission: float | None = None


Action = Literal["enter_long", "exit_long"]


@dataclass(frozen=True, slots=True)
class Signal:
    """Decision known at `time` (a candle close). Filled on the next open, not here."""

    symbol: str
    action: Action
    time: datetime
    reason: str
    stop_distance: float | None = None
    take_distance: float | None = None

    def __post_init__(self) -> None:
        if self.time.tzinfo is None:
            raise DataError("signal time must be timezone-aware")
        for name in ("stop_distance", "take_distance"):
            value = getattr(self, name)
            if value is not None and (value != value or value <= 0):
                raise DataError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class Fill:
    time: datetime
    side: Literal["BUY", "SELL"]
    pair: str
    qty: float
    price: float
    fee_brl: float
    pnl_brl: float
    reason: str
    equity_after: float


@dataclass(slots=True)
class Position:
    qty: float
    entry_price: float
    entry_notional: float
    entry_fee: float
    stop: float
    take: float
    entry_time: datetime
    entry_reason: str
