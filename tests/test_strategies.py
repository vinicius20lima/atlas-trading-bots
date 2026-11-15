"""Strategy rules and the no-lookahead property."""

from __future__ import annotations

import random

from tests.conftest import make_candles

from atlas.strategies.atr_trend import AtrTrendStrategy
from atlas.strategies.atr_trend import should_enter as atr_enter
from atlas.strategies.atr_trend import should_exit as atr_exit
from atlas.strategies.ema_crossover import EmaCrossoverStrategy
from atlas.strategies.ema_crossover import should_enter as ema_enter
from atlas.strategies.ema_crossover import should_exit as ema_exit


def test_ema_entry_requires_cross_trend_and_rsi_band() -> None:
    assert ema_enter(1, 2, 3, 2.5, close=10, trend=9, rsi_value=50)
    assert not ema_enter(1, 2, 3, 2.5, close=10, trend=9, rsi_value=70.01)
    assert not ema_enter(1, 2, 3, 2.5, close=10, trend=9, rsi_value=29.9)
    assert not ema_enter(1, 2, 3, 2.5, close=8, trend=9, rsi_value=50)
    assert not ema_enter(3, 2, 4, 2.5, close=10, trend=9, rsi_value=50)
    assert ema_enter(2, 2, 2.1, 2, close=3, trend=2.5, rsi_value=30)
    assert ema_enter(2, 2, 2.1, 2, close=3, trend=2.5, rsi_value=70)


def test_ema_exit_is_the_down_cross() -> None:
    assert ema_exit(3, 2, 2, 2.5)
    assert not ema_exit(1, 2, 3, 2.5)


def test_atr_entry_uses_the_volatility_band() -> None:
    assert atr_enter(1, 2, 3, 2.5, close=10, atr_value=0.2, min_atr_pct=0.015, max_atr_pct=0.12)
    assert not atr_enter(
        1, 2, 3, 2.5, close=10, atr_value=0.01, min_atr_pct=0.015, max_atr_pct=0.12
    )
    assert not atr_enter(1, 2, 3, 2.5, close=10, atr_value=2, min_atr_pct=0.015, max_atr_pct=0.12)
    assert not atr_enter(1, 2, 3, 2.5, close=2, atr_value=0.2, min_atr_pct=0.015, max_atr_pct=0.12)
    assert atr_exit(3, 2, 1, 2)
    assert not atr_exit(1, 2, 3, 2)


def test_signals_do_not_depend_on_future_bars() -> None:
    rng = random.Random(7)
    price = 100.0
    rows = []
    for _ in range(80):
        price *= 1 + rng.uniform(-0.02, 0.02)
        rows.append((price, price * 1.01, price * 0.99, price))
    candles = make_candles(rows)
    for strategy in (
        EmaCrossoverStrategy(fast=3, slow=5, trend=8, rsi_period=3),
        AtrTrendStrategy(fast=3, slow=8, atr_period=3, min_atr_pct=0.001, max_atr_pct=0.2),
    ):
        full = strategy.generate("BTCBRL", candles)
        assert len(full) == len(candles)
        for index in range(len(candles)):
            prefix = strategy.generate("BTCBRL", candles[: index + 1])
            assert prefix[-1] == full[index]


def test_default_timeframes() -> None:
    assert EmaCrossoverStrategy().interval == "15m"
    assert AtrTrendStrategy().interval == "4h"
    assert AtrTrendStrategy().stop_mult == 2
    assert AtrTrendStrategy().take_mult == 4
