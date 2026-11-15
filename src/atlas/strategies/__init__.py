"""Strategies shipped in v0.1."""

from atlas.strategies.atr_trend import AtrTrendStrategy
from atlas.strategies.base import Strategy
from atlas.strategies.ema_crossover import EmaCrossoverStrategy

STRATEGIES: dict[str, type[Strategy]] = {
    "ema_crossover": EmaCrossoverStrategy,
    "atr_trend": AtrTrendStrategy,
}


def build_strategy(name: str) -> Strategy:
    try:
        cls = STRATEGIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(STRATEGIES))
        raise KeyError(f"unknown strategy {name!r}; choose {known}") from exc
    return cls()


__all__ = [
    "AtrTrendStrategy",
    "EmaCrossoverStrategy",
    "STRATEGIES",
    "Strategy",
    "build_strategy",
]
