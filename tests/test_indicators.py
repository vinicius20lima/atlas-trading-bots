"""Hand-checked indicator values."""

from __future__ import annotations

from datetime import datetime, timedelta

from atlas.clock import UTC
from atlas.indicators import atr, ema, rsi
from atlas.models import Candle


def test_ema_seeds_with_sma_then_recurses() -> None:
    values = ema([1, 2, 3, 4, 5], 3)
    assert values[:2] == [None, None]
    assert values[2] == 2
    assert values[3] == 3
    assert values[4] == 4


def test_rsi_wilder() -> None:
    # deltas +1, +1, -1 then +2. Period 3.
    values = rsi([10, 11, 12, 11, 13], 3)
    assert values[3] == 100 - 100 / 3
    assert values[4] == 100 - 100 / 6


def test_atr_wilder() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [(10, 8, 9), (11, 9, 10), (12, 10, 11), (11, 7, 8)]
    candles = []
    for index, (high, low, close) in enumerate(rows):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                open=close,
                high=high,
                low=low,
                close=close,
                volume=1,
                close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
            )
        )
    values = atr(candles, 3)
    assert values[3] == (2 + 2 + 4) / 3
