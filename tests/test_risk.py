"""Sizing, the fixed bracket, and the daily loss cap."""

from __future__ import annotations

from datetime import datetime, timedelta

from atlas.clock import UTC
from atlas.models import Signal
from atlas.risk.manager import RiskConfig, RiskManager


def _signal(stop: float | None = None, take: float | None = None) -> Signal:
    return Signal(
        "BTCBRL",
        "enter_long",
        datetime(2024, 6, 1, tzinfo=UTC),
        "test",
        stop_distance=stop,
        take_distance=take,
    )


def test_position_is_capped_at_20_percent_and_fee_fits_in_cash() -> None:
    risk = RiskManager(RiskConfig(taker_fee=0.001, min_notional=10))
    plan, reason = risk.plan_entry(
        equity=500, cash=500, fill_price=100, signal=_signal(), halted=False
    )
    assert reason == "approved"
    assert plan is not None
    assert plan.notional == 100
    assert plan.fee == 0.1
    assert plan.qty == 1
    assert plan.stop == 97
    assert plan.take == 105
    assert 500 - plan.notional - plan.fee >= 0


def test_atr_distances_replace_the_fixed_bracket() -> None:
    risk = RiskManager()
    plan, _ = risk.plan_entry(
        equity=1_000,
        cash=1_000,
        fill_price=100,
        signal=_signal(stop=5, take=12),
        halted=False,
    )
    assert plan is not None
    assert plan.stop == 95
    assert plan.take == 112


def test_halt_and_min_notional_reject() -> None:
    risk = RiskManager(RiskConfig(min_notional=10))
    plan, reason = risk.plan_entry(
        equity=1_000, cash=1_000, fill_price=100, signal=_signal(), halted=True
    )
    assert plan is None and reason == "daily_loss_halt"
    plan, reason = risk.plan_entry(
        equity=40, cash=40, fill_price=100, signal=_signal(), halted=False
    )
    assert plan is None and reason == "min_notional"


def test_daily_loss_cap_trips_at_five_percent() -> None:
    assert RiskManager.daily_loss_reached(1_000, 950, 0.05)
    assert not RiskManager.daily_loss_reached(1_000, 950.02, 0.05)
    assert RiskManager.daily_loss_reached(1_000, 900, 0.05)


def test_cash_constraint_shrinks_notional() -> None:
    risk = RiskManager(RiskConfig(max_position_pct=1, taker_fee=0.001, min_notional=0))
    plan, reason = risk.plan_entry(
        equity=500, cash=500, fill_price=50, signal=_signal(), halted=False
    )
    assert reason == "approved" and plan is not None
    assert plan.notional + plan.fee <= 500 + 1e-9
    assert abs((plan.notional + plan.fee) - 500) < 1e-6


def test_manaus_day_changes_at_04_utc() -> None:
    from atlas.clock import day_key

    before = datetime(2024, 6, 1, 3, 59, tzinfo=UTC)
    after = before + timedelta(minutes=1)
    assert day_key(before) == "2024-05-31"
    assert day_key(after) == "2024-06-01"
