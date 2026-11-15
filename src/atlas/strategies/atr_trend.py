"""Slower 4h trend follow. Chosen before looking at the v0.1 sample, not fitted to it.

Long entry on the closed candle when all of these are true:
- EMA(20) crosses above EMA(50)
- close is above EMA(50)
- ATR(14) / close is inside [1.5%, 12%]

The volatility band is there to skip a dead range (where a cross is mostly
noise and fees) and to skip blow-off bars. Stop distance is 2 * ATR and take
distance is 4 * ATR, both measured on the signal bar and applied to the next
open by the risk manager. That replaces the fixed −3% / +5% bracket.

Exit signal: EMA(20) crosses below EMA(50). Protective ATR orders can close
the trade earlier.

Fewer decisions is the point. A 4h cross can go months between trades, so a
short window can easily contain too few round trips to claim an edge.
"""

from __future__ import annotations

from collections.abc import Sequence

from atlas.indicators import atr, crossed_down, crossed_up, ema
from atlas.models import Candle, Signal
from atlas.strategies.base import Strategy


def should_enter(
    prev_fast: float,
    prev_slow: float,
    fast: float,
    slow: float,
    close: float,
    atr_value: float,
    min_atr_pct: float,
    max_atr_pct: float,
) -> bool:
    if close <= 0 or atr_value <= 0:
        return False
    atr_pct = atr_value / close
    return (
        crossed_up(prev_fast, prev_slow, fast, slow)
        and close > slow
        and min_atr_pct <= atr_pct <= max_atr_pct
    )


def should_exit(prev_fast: float, prev_slow: float, fast: float, slow: float) -> bool:
    return crossed_down(prev_fast, prev_slow, fast, slow)


class AtrTrendStrategy(Strategy):
    name = "atr_trend"
    interval = "4h"

    def __init__(
        self,
        fast: int = 20,
        slow: int = 50,
        atr_period: int = 14,
        stop_mult: float = 2.0,
        take_mult: float = 4.0,
        min_atr_pct: float = 0.015,
        max_atr_pct: float = 0.12,
        interval: str = "4h",
    ) -> None:
        if not (0 < fast < slow):
            raise ValueError("expected fast < slow")
        if stop_mult <= 0 or take_mult <= 0:
            raise ValueError("ATR multiples must be positive")
        if not (0 < min_atr_pct < max_atr_pct):
            raise ValueError("invalid ATR percent band")
        self.fast = fast
        self.slow = slow
        self.atr_period = atr_period
        self.stop_mult = stop_mult
        self.take_mult = take_mult
        self.min_atr_pct = min_atr_pct
        self.max_atr_pct = max_atr_pct
        self.interval = interval
        self.warmup_bars = max(slow, atr_period) + 2

    def generate(self, symbol: str, candles: Sequence[Candle]) -> list[Signal | None]:
        closes = [candle.close for candle in candles]
        fast = ema(closes, self.fast)
        slow = ema(closes, self.slow)
        ranges = atr(candles, self.atr_period)
        out: list[Signal | None] = [None] * len(candles)
        for i in range(1, len(candles)):
            values = (fast[i - 1], fast[i], slow[i - 1], slow[i], ranges[i])
            if any(item is None for item in values):
                continue
            prev_fast, cur_fast, prev_slow, cur_slow, cur_atr = values
            assert prev_fast is not None and cur_fast is not None
            assert prev_slow is not None and cur_slow is not None and cur_atr is not None
            if should_enter(
                prev_fast,
                prev_slow,
                cur_fast,
                cur_slow,
                closes[i],
                cur_atr,
                self.min_atr_pct,
                self.max_atr_pct,
            ):
                out[i] = Signal(
                    symbol,
                    "enter_long",
                    candles[i].close_time,
                    "atr_trend_cross_up",
                    stop_distance=cur_atr * self.stop_mult,
                    take_distance=cur_atr * self.take_mult,
                )
            elif should_exit(prev_fast, prev_slow, cur_fast, cur_slow):
                out[i] = Signal(
                    symbol,
                    "exit_long",
                    candles[i].close_time,
                    "atr_trend_cross_down",
                )
        return out
