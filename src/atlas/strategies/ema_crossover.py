"""Baseline 15m EMA 9/21 crossover.

Entry (long only), all required on the closed candle:
- EMA(9) crosses above EMA(21)
- close is above EMA(50)
- RSI(14) is inside [30, 70]

Exit signal: EMA(9) crosses below EMA(21).
Stops and targets come from the risk manager (default −3% / +5%), not from this file.

These parameters are the first prototype. They were not optimized. On an early
manual run the owner saw about −27% and a 10% win rate over 30 days, mostly
whipsaw and fees. v0.1 re-measures that claim instead of tuning it away.
"""

from __future__ import annotations

from collections.abc import Sequence

from atlas.indicators import crossed_down, crossed_up, ema, rsi
from atlas.models import Candle, Signal
from atlas.strategies.base import Strategy


def should_enter(
    prev_fast: float,
    prev_slow: float,
    fast: float,
    slow: float,
    close: float,
    trend: float,
    rsi_value: float,
    rsi_low: float = 30.0,
    rsi_high: float = 70.0,
) -> bool:
    return (
        crossed_up(prev_fast, prev_slow, fast, slow)
        and close > trend
        and rsi_low <= rsi_value <= rsi_high
    )


def should_exit(
    prev_fast: float,
    prev_slow: float,
    fast: float,
    slow: float,
) -> bool:
    return crossed_down(prev_fast, prev_slow, fast, slow)


class EmaCrossoverStrategy(Strategy):
    name = "ema_crossover"
    interval = "15m"

    def __init__(
        self,
        fast: int = 9,
        slow: int = 21,
        trend: int = 50,
        rsi_period: int = 14,
        rsi_low: float = 30.0,
        rsi_high: float = 70.0,
        interval: str = "15m",
    ) -> None:
        if not (0 < fast < slow <= trend):
            raise ValueError("expected fast < slow <= trend")
        self.fast = fast
        self.slow = slow
        self.trend = trend
        self.rsi_period = rsi_period
        self.rsi_low = rsi_low
        self.rsi_high = rsi_high
        self.interval = interval
        self.warmup_bars = max(trend, rsi_period) + 2

    def generate(self, symbol: str, candles: Sequence[Candle]) -> list[Signal | None]:
        closes = [candle.close for candle in candles]
        fast = ema(closes, self.fast)
        slow = ema(closes, self.slow)
        trend = ema(closes, self.trend)
        momentum = rsi(closes, self.rsi_period)
        out: list[Signal | None] = [None] * len(candles)
        for i in range(1, len(candles)):
            values = (fast[i - 1], fast[i], slow[i - 1], slow[i], trend[i], momentum[i])
            if any(item is None for item in values):
                continue
            prev_fast, cur_fast, prev_slow, cur_slow, cur_trend, cur_rsi = values
            assert prev_fast is not None and cur_fast is not None
            assert prev_slow is not None and cur_slow is not None
            assert cur_trend is not None and cur_rsi is not None
            if should_enter(
                prev_fast,
                prev_slow,
                cur_fast,
                cur_slow,
                closes[i],
                cur_trend,
                cur_rsi,
                self.rsi_low,
                self.rsi_high,
            ):
                out[i] = Signal(symbol, "enter_long", candles[i].close_time, "ema_cross_up")
            elif should_exit(prev_fast, prev_slow, cur_fast, cur_slow):
                out[i] = Signal(symbol, "exit_long", candles[i].close_time, "ema_cross_down")
        return out
