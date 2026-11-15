"""Scripted strategy and a small settings builder for engine tests."""

from __future__ import annotations

from atlas.config import Settings
from atlas.models import Candle, Signal
from atlas.orchestrator import build_orchestrator
from atlas.strategies.base import Strategy


class Scripted(Strategy):
    name = "scripted"
    interval = "1h"
    warmup_bars = 0

    def __init__(
        self,
        actions: dict[int, str],
        stop_distance: float | None = None,
    ) -> None:
        self.actions = actions
        self.stop_distance = stop_distance

    def generate(self, symbol: str, candles: list[Candle]) -> list[Signal | None]:
        output: list[Signal | None] = []
        for index, candle in enumerate(candles):
            action = self.actions.get(index)
            if action not in {"enter_long", "exit_long"}:
                output.append(None)
                continue
            output.append(
                Signal(
                    symbol,
                    action,  # type: ignore[arg-type]
                    candle.close_time,
                    action,
                    stop_distance=self.stop_distance if action == "enter_long" else None,
                )
            )
        return output


def settings(**overrides: object) -> Settings:
    base = Settings(
        starting_balance=1_000.0,
        taker_fee=0.0,
        min_notional=0.0,
        symbols=("BTCBRL",),
    )
    if not overrides:
        return base
    return base.with_overrides(**overrides)


def runtime(
    strategy: Strategy, config: Settings, symbols: set[str], mode: str = "backtest", **kwargs
):
    return build_orchestrator(strategy, config, mode, symbols, **kwargs)
