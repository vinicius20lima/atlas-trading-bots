"""Close-only indicators. Values before the seed window are None.

EMA is the standard recursive form seeded with an SMA.
RSI and ATR use Wilder's smoothing.
"""

from __future__ import annotations

from collections.abc import Sequence

from atlas.models import Candle


def ema(values: Sequence[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    k = 2.0 / (period + 1.0)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def rsi(values: Sequence[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gain_sum = 0.0
    loss_sum = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gain_sum += max(delta, 0.0)
        loss_sum += max(-delta, 0.0)
    avg_gain = gain_sum / period
    avg_loss = loss_sum / period
    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def _rsi(avg_gain: float, avg_loss: float) -> float:
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles: Sequence[Candle], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    n = len(candles)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    true_ranges = [0.0] * n
    for i in range(1, n):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        true_ranges[i] = max(high - low, abs(high - prev_close), abs(low - prev_close))
    prev = sum(true_ranges[1 : period + 1]) / period
    out[period] = prev
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + true_ranges[i]) / period
        out[i] = prev
    return out


def crossed_up(prev_fast: float, prev_slow: float, fast: float, slow: float) -> bool:
    return prev_fast <= prev_slow and fast > slow


def crossed_down(prev_fast: float, prev_slow: float, fast: float, slow: float) -> bool:
    return prev_fast >= prev_slow and fast < slow
