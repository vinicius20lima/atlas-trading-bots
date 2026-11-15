"""Strategy interface. A signal at candle close is not a fill."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from atlas.models import Candle, Signal


class Strategy(ABC):
    name: str
    interval: str
    warmup_bars: int

    @abstractmethod
    def generate(self, symbol: str, candles: Sequence[Candle]) -> list[Signal | None]:
        """Return one item per candle. Index i may only depend on candles[: i + 1]."""


def assert_aligned(candles: Sequence[Candle], signals: Sequence[Signal | None]) -> None:
    if len(candles) != len(signals):
        raise ValueError("strategy signal list length does not match candles")
    for candle, signal in zip(candles, signals, strict=True):
        if signal is not None and signal.time != candle.close_time:
            raise ValueError("signal time must be the candle close time")
