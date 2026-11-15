"""Backtest driver. Candles may include a warmup pad; fills start at `window_start`."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from atlas.config import Settings
from atlas.engine.metrics import TradeStats, summarize
from atlas.engine.portfolio import Portfolio
from atlas.engine.simulator import simulate
from atlas.models import Candle
from atlas.orchestrator import build_orchestrator
from atlas.strategies.base import Strategy


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy: str
    interval: str
    symbols: tuple[str, ...]
    window_start: datetime | None
    first_bar: datetime | None
    last_bar: datetime | None
    bars: int
    starting_balance: float
    ending_equity: float
    realized_pnl: float
    fees_paid: float
    max_drawdown_pct: float
    stats: TradeStats
    rejections: tuple[tuple[str, int], ...]
    taker_fee: float
    open_positions: int

    @property
    def return_pct(self) -> float:
        if self.starting_balance == 0:
            return 0.0
        return (self.ending_equity / self.starting_balance - 1.0) * 100.0


def run_backtest(
    candles_by_symbol: dict[str, list[Candle]],
    strategy: Strategy,
    settings: Settings,
    window_start: datetime | None = None,
) -> BacktestResult:
    symbols = tuple(sorted(candles_by_symbol))
    only_after: dict[str, datetime | None] | None = None
    if window_start is not None:
        only_after = {}
        for symbol, series in candles_by_symbol.items():
            prior = [candle for candle in series if candle.open_time < window_start]
            only_after[symbol] = prior[-1].close_time if prior else None

    orchestrator = build_orchestrator(strategy, settings, "backtest", set(symbols))
    portfolio = Portfolio(settings.starting_balance)
    outcome = simulate(
        candles_by_symbol,
        strategy,
        orchestrator,
        portfolio,
        only_after_close=only_after,
    )
    processed = [
        candle
        for symbol, series in candles_by_symbol.items()
        for candle in series
        if _in_play(candle, None if only_after is None else only_after.get(symbol))
    ]
    processed.sort(key=lambda candle: candle.open_time)
    reasons = Counter(reason for _, _, reason in outcome.rejections)
    return BacktestResult(
        strategy=strategy.name,
        interval=strategy.interval,
        symbols=symbols,
        window_start=window_start,
        first_bar=processed[0].open_time if processed else None,
        last_bar=processed[-1].close_time if processed else None,
        bars=len(processed),
        starting_balance=portfolio.starting_balance,
        ending_equity=portfolio.equity(),
        realized_pnl=portfolio.realized_pnl,
        fees_paid=portfolio.fees_paid,
        max_drawdown_pct=portfolio.max_drawdown_pct,
        stats=summarize(portfolio.fills),
        rejections=tuple(sorted(reasons.items())),
        taker_fee=settings.taker_fee,
        open_positions=len(portfolio.positions),
    )


def window_change(
    curve: list[tuple[datetime, float]], start: datetime, ending: float
) -> float | None:
    """Equity change from the last mark at or before `start` to `ending`.

    Returns None when the curve has no point at or before `start`.
    """
    baseline: float | None = None
    for moment, equity in curve:
        if moment <= start:
            baseline = equity
        else:
            break
    if baseline is None or baseline == 0:
        return None
    return (ending / baseline - 1.0) * 100.0


def slice_start(end: datetime, days: int) -> datetime:
    return end - timedelta(days=days)


def _in_play(candle: Candle, cursor: datetime | None) -> bool:
    if cursor is None:
        return True
    return candle.close_time > cursor
