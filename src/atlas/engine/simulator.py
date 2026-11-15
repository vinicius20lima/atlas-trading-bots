"""Shared fill model for backtest and paper.

Rules:
- a signal is known only after its candle closes
- the fill is the next candle's open
- a position opened at that open can be stopped or taken on the same candle
- if stop and take are both touched, the stop fills (conservative)
- a gap through the stop fills at the open; a gap through the take fills at the open
- an enter signal does not fire if that symbol was already in a position at the open
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.engine.portfolio import Portfolio
from atlas.errors import AtlasError, LiveTradingDisabled
from atlas.models import Candle, Signal
from atlas.orchestrator import Orchestrator
from atlas.strategies.base import Strategy


@dataclass(slots=True)
class SimulationResult:
    portfolio: Portfolio
    rejections: list[tuple[datetime, str, str]]
    equity_curve: list[tuple[datetime, float]]


def simulate(
    candles_by_symbol: dict[str, list[Candle]],
    strategy: Strategy,
    orchestrator: Orchestrator,
    portfolio: Portfolio,
    only_after_close: dict[str, datetime | None] | None = None,
) -> SimulationResult:
    if orchestrator.mode == "live":
        raise LiveTradingDisabled("the simulator does not run in live mode")

    signal_at: dict[str, dict[datetime, Signal | None]] = {}
    by_open: dict[str, dict[datetime, Candle]] = {}
    for symbol, candles in candles_by_symbol.items():
        signals = strategy.generate(symbol, candles)
        if len(signals) != len(candles):
            raise AtlasError(f"{strategy.name} returned the wrong number of signals for {symbol}")
        for candle, signal in zip(candles, signals, strict=True):
            if signal is not None and signal.time != candle.close_time:
                raise AtlasError("signal time must equal the candle close time")
        signal_at[symbol] = {
            candle.open_time: signal for candle, signal in zip(candles, signals, strict=True)
        }
        by_open[symbol] = {candle.open_time: candle for candle in candles}

    queued: dict[str, Signal | None] = {symbol: None for symbol in candles_by_symbol}
    if only_after_close:
        for symbol, cursor in only_after_close.items():
            if cursor is None or symbol not in by_open:
                continue
            match = next(
                (candle for candle in candles_by_symbol[symbol] if candle.close_time == cursor),
                None,
            )
            if match is None:
                raise AtlasError(
                    f"missing cursor candle for {symbol}. Fetch more history or reset paper state."
                )
            queued[symbol] = signal_at[symbol][match.open_time]

    def active(symbol: str, candle: Candle) -> bool:
        if not only_after_close or symbol not in only_after_close:
            return True
        cursor = only_after_close[symbol]
        if cursor is None:
            return True
        return candle.close_time > cursor

    times = sorted(
        {
            candle.open_time
            for symbol, candles in candles_by_symbol.items()
            for candle in candles
            if active(symbol, candle)
        }
    )
    rejections: list[tuple[datetime, str, str]] = []
    curve: list[tuple[datetime, float]] = []
    fee = orchestrator.risk.config.taker_fee
    cap = orchestrator.risk.config.daily_loss_cap_pct

    for timestamp in times:
        bars = {
            symbol: by_open[symbol][timestamp]
            for symbol in by_open
            if timestamp in by_open[symbol] and active(symbol, by_open[symbol][timestamp])
        }
        if not bars:
            continue
        portfolio.roll_day(timestamp)
        held_at_open = {symbol for symbol in bars if symbol in portfolio.positions}
        for symbol in held_at_open:
            portfolio.last_marks[symbol] = bars[symbol].open

        for symbol in sorted(bars):
            _exit_at_open(portfolio, symbol, bars[symbol], queued.get(symbol), fee, orchestrator)

        portfolio.refresh_halt(cap)

        for symbol in sorted(bars):
            pending = queued.get(symbol)
            candle = bars[symbol]
            if pending is None or pending.action != "enter_long":
                continue
            if symbol in held_at_open:
                rejections.append((candle.open_time, symbol, "already_in_position"))
                continue
            decision = orchestrator.decide_entry(
                pending,
                candle.open,
                equity=portfolio.equity(),
                cash=portfolio.cash,
                halted=portfolio.halted,
            )
            if decision.action != "enter_long":
                rejections.append((candle.open_time, symbol, decision.reason))
                continue
            portfolio.open_long(
                symbol,
                qty=decision.qty,
                notional=decision.notional,
                fee=decision.fee,
                stop=decision.stop if decision.stop is not None else candle.open,
                take=decision.take if decision.take is not None else candle.open,
                time=candle.open_time,
                reason=pending.reason,
                fill_price=candle.open,
            )

        for symbol in sorted(bars):
            _exit_intrabar(portfolio, symbol, bars[symbol], fee)

        for symbol, candle in bars.items():
            portfolio.last_marks[symbol] = candle.close
            queued[symbol] = signal_at[symbol][candle.open_time]

        portfolio.refresh_halt(cap)
        curve.append((timestamp, portfolio.update_drawdown()))

    return SimulationResult(portfolio=portfolio, rejections=rejections, equity_curve=curve)


def _exit_at_open(
    portfolio: Portfolio,
    symbol: str,
    candle: Candle,
    pending: Signal | None,
    fee: float,
    orchestrator: Orchestrator,
) -> None:
    position = portfolio.positions.get(symbol)
    if position is None:
        return
    if candle.open <= position.stop:
        portfolio.close_long(
            symbol,
            time=candle.open_time,
            price=candle.open,
            reason="stop_loss",
            fee_rate=fee,
        )
        return
    if pending is not None and pending.action == "exit_long":
        decision = orchestrator.decide_exit(pending)
        if decision.action == "exit_long":
            portfolio.close_long(
                symbol,
                time=candle.open_time,
                price=candle.open,
                reason=pending.reason,
                fee_rate=fee,
            )
            return
    if candle.open >= position.take:
        portfolio.close_long(
            symbol,
            time=candle.open_time,
            price=candle.open,
            reason="take_profit",
            fee_rate=fee,
        )


def _exit_intrabar(portfolio: Portfolio, symbol: str, candle: Candle, fee: float) -> None:
    position = portfolio.positions.get(symbol)
    if position is None:
        return
    # Open-gaps were already handled. Both sides touched -> stop fills first.
    stop_hit = candle.low <= position.stop
    take_hit = candle.high >= position.take
    if stop_hit:
        portfolio.close_long(
            symbol,
            time=candle.open_time,
            price=position.stop,
            reason="stop_loss",
            fee_rate=fee,
        )
        return
    if take_hit:
        portfolio.close_long(
            symbol,
            time=candle.open_time,
            price=position.take,
            reason="take_profit",
            fee_rate=fee,
        )
