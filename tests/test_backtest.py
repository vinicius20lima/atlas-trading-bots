"""Backtest fills: next open, stop before take, fees, and the daily halt."""

from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import make_candles
from tests.support import Scripted, runtime, settings

from atlas.clock import UTC
from atlas.engine.backtest import run_backtest
from atlas.engine.portfolio import Portfolio
from atlas.engine.simulator import simulate
from atlas.errors import LiveTradingDisabled


def _run(rows, actions, *, start, step, config=None, stop_distance=None, symbols=("BTCBRL",)):
    config = settings() if config is None else config
    candles = {symbols[0]: make_candles(rows, start=start, step=step)}
    if len(symbols) > 1:
        raise AssertionError("use run_many")
    strategy = Scripted(actions, stop_distance=stop_distance)
    outcome = simulate(
        candles,
        strategy,
        runtime(strategy, config, set(symbols)),
        Portfolio(config.starting_balance),
    )
    return outcome


def test_signal_fills_on_the_next_open_not_the_close() -> None:
    rows = [(100, 101, 99, 100), (102, 103, 101, 102), (102, 103, 101, 102)]
    outcome = _run(
        rows, {0: "enter_long"}, start=datetime(2024, 6, 1, 12, tzinfo=UTC), step=timedelta(hours=1)
    )
    buys = [fill for fill in outcome.portfolio.fills if fill.side == "BUY"]
    assert len(buys) == 1
    assert buys[0].price == 102
    assert buys[0].time == outcome.portfolio.positions["BTCBRL"].entry_time
    position = outcome.portfolio.positions["BTCBRL"]
    assert position.stop == 102 * 0.97
    assert position.take == 102 * 1.05


def test_no_fill_without_a_following_bar() -> None:
    rows = [(100, 101, 99, 100)]
    outcome = _run(
        rows, {0: "enter_long"}, start=datetime(2024, 6, 1, tzinfo=UTC), step=timedelta(hours=1)
    )
    assert outcome.portfolio.fills == []


def test_stop_fills_before_take_when_both_are_touched() -> None:
    rows = [(100, 101, 99, 100), (100, 120, 90, 100)]
    outcome = _run(
        rows, {0: "enter_long"}, start=datetime(2024, 6, 1, tzinfo=UTC), step=timedelta(hours=1)
    )
    sells = [fill for fill in outcome.portfolio.fills if fill.side == "SELL"]
    assert len(sells) == 1
    assert sells[0].reason == "stop_loss"
    assert sells[0].price == 97


def test_gap_through_stop_fills_at_the_open() -> None:
    # Fill is the next open, so the stop is set from that open. The gap is the bar after.
    rows = [(100, 101, 99, 100), (100, 101, 99, 100), (90, 92, 80, 91)]
    outcome = _run(
        rows, {0: "enter_long"}, start=datetime(2024, 6, 1, tzinfo=UTC), step=timedelta(hours=1)
    )
    sell = next(fill for fill in outcome.portfolio.fills if fill.side == "SELL")
    assert sell.price == 90
    assert sell.reason == "stop_loss"


def test_take_profit_and_gap_through_target() -> None:
    start = datetime(2024, 6, 1, tzinfo=UTC)
    step = timedelta(hours=1)
    touched = _run(
        [(100, 101, 99, 100), (100, 106, 99, 104)],
        {0: "enter_long"},
        start=start,
        step=step,
    )
    sell = next(fill for fill in touched.portfolio.fills if fill.side == "SELL")
    assert sell.price == 105 and sell.reason == "take_profit"

    gapped = _run(
        [(100, 101, 99, 100), (100, 101, 99, 100), (110, 112, 108, 111)],
        {0: "enter_long"},
        start=start,
        step=step,
    )
    sell = next(fill for fill in gapped.portfolio.fills if fill.side == "SELL")
    assert sell.price == 110 and sell.reason == "take_profit"


def test_fees_are_charged_on_both_sides() -> None:
    config = settings(taker_fee=0.001)
    rows = [(100, 101, 99, 100), (100, 106, 99, 104)]
    outcome = _run(
        rows,
        {0: "enter_long"},
        start=datetime(2024, 6, 1, tzinfo=UTC),
        step=timedelta(hours=1),
        config=config,
    )
    buy, sell = outcome.portfolio.fills
    assert buy.fee_brl == 0.2
    assert abs(outcome.portfolio.cash - (1000 - 200 - 0.2 + 2 * 105 - 2 * 105 * 0.001)) < 1e-9
    assert sell.pnl_brl < (2 * 105 - 200)


def test_daily_loss_cap_blocks_same_day_entries_only() -> None:
    start = datetime(2024, 6, 1, 12, tzinfo=UTC)
    step = timedelta(hours=6)
    # 12:00, 18:00 still 1 Jun Manaus; next start is built explicitly below.
    rows = [
        (100, 101, 99, 100),
        (100, 101, 70, 90),
        (100, 101, 99, 100),
        (100, 101, 99, 100),
    ]
    candles = make_candles(rows, start=start, step=step)
    # Force the last bar onto the next Manaus day (04:00 UTC).
    last_open = datetime(2024, 6, 2, 12, tzinfo=UTC)
    candles[-1] = type(candles[-1])(
        open_time=last_open,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1,
        close_time=last_open + step - timedelta(milliseconds=1),
    )
    config = settings()
    strategy = Scripted({0: "enter_long", 1: "enter_long", 2: "enter_long"}, stop_distance=25)
    outcome = simulate(
        {"BTCBRL": candles},
        strategy,
        runtime(strategy, config, {"BTCBRL"}),
        Portfolio(config.starting_balance),
    )
    buys = [fill for fill in outcome.portfolio.fills if fill.side == "BUY"]
    sells = [fill for fill in outcome.portfolio.fills if fill.side == "SELL"]
    assert [fill.time for fill in buys] == [candles[1].open_time, candles[3].open_time]
    assert len(sells) == 1 and sells[0].price == 75 and sells[0].reason == "stop_loss"
    assert any(reason == "daily_loss_halt" for _, _, reason in outcome.rejections)
    assert outcome.portfolio.halted is False


def test_two_symbols_each_take_twenty_percent() -> None:
    rows = [(100, 100, 100, 100), (100, 100, 100, 100)]
    config = settings(symbols=("BTCBRL", "ETHBRL"))
    strategy = Scripted({0: "enter_long"})
    candles = {
        "ETHBRL": make_candles(
            rows, start=datetime(2024, 6, 1, tzinfo=UTC), step=timedelta(hours=1)
        ),
        "BTCBRL": make_candles(
            rows, start=datetime(2024, 6, 1, tzinfo=UTC), step=timedelta(hours=1)
        ),
    }
    outcome = simulate(
        candles,
        strategy,
        runtime(strategy, config, set(candles)),
        Portfolio(config.starting_balance),
    )
    assert set(outcome.portfolio.positions) == {"BTCBRL", "ETHBRL"}
    for position in outcome.portfolio.positions.values():
        assert position.entry_notional == 200
    assert outcome.portfolio.cash == 600


def test_window_does_not_replay_an_old_signal() -> None:
    rows = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)]
    start = datetime(2024, 6, 1, tzinfo=UTC)
    candles = make_candles(rows, start=start, step=timedelta(hours=1))
    config = settings()
    strategy = Scripted({0: "enter_long"})
    result = run_backtest(
        {"BTCBRL": candles},
        strategy,
        config,
        window_start=candles[2].open_time,
    )
    assert result.stats.fills == 0


def test_simulator_refuses_live_mode() -> None:
    config = settings()
    strategy = Scripted({0: "enter_long"})
    try:
        simulate(
            {"BTCBRL": make_candles([(100, 101, 99, 100), (100, 101, 99, 100)])},
            strategy,
            runtime(strategy, config, {"BTCBRL"}, mode="live"),
            Portfolio(config.starting_balance),
        )
    except LiveTradingDisabled:
        return
    raise AssertionError("live mode ran")
