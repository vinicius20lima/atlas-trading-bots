"""Candle builders shared by the tests. No network."""

from __future__ import annotations

from datetime import datetime, timedelta

from atlas.clock import UTC
from atlas.models import Candle


def make_candles(
    rows: list[tuple[float, float, float, float]],
    *,
    start: datetime | None = None,
    step: timedelta = timedelta(minutes=15),
) -> list[Candle]:
    origin = start or datetime(2024, 1, 2, 12, 0, tzinfo=UTC)
    candles: list[Candle] = []
    for index, (open_, high, low, close) in enumerate(rows):
        open_time = origin + step * index
        candles.append(
            Candle(
                open_time=open_time,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=1.0,
                close_time=open_time + step - timedelta(milliseconds=1),
            )
        )
    return candles


def flat(price: float, count: int) -> list[tuple[float, float, float, float]]:
    return [(price, price, price, price) for _ in range(count)]
