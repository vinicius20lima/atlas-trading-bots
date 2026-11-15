"""Position sizing and the daily loss cap.

Defaults:
- at most 20% of equity as notional per position
- stop −3% and take +5% from the fill, unless the signal carries ATR distances
- new entries stop for the America/Manaus day after a −5% day
- taker fee 0.10% per side (Binance spot regular user, no BNB discount)
- minimum notional R$10, the BTCBRL minNotional observed on the public
  exchange filter. v0.1 does not round to tick size or step size.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.models import Signal


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_position_pct: float = 0.20
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.05
    daily_loss_cap_pct: float = 0.05
    taker_fee: float = 0.001
    min_notional: float = 10.0

    def __post_init__(self) -> None:
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("max_position_pct must be in (0, 1]")
        if not 0 < self.stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be in (0, 1)")
        if not 0 < self.take_profit_pct < 1:
            raise ValueError("take_profit_pct must be in (0, 1)")
        if not 0 < self.daily_loss_cap_pct < 1:
            raise ValueError("daily_loss_cap_pct must be in (0, 1)")
        if not 0 <= self.taker_fee < 1:
            raise ValueError("taker_fee must be in [0, 1)")
        if self.min_notional < 0:
            raise ValueError("min_notional must be >= 0")


@dataclass(frozen=True, slots=True)
class EntryPlan:
    qty: float
    notional: float
    fee: float
    stop: float
    take: float


class RiskManager:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def bracket(self, fill_price: float, signal: Signal) -> tuple[float, float]:
        if signal.stop_distance is not None:
            stop = fill_price - signal.stop_distance
        else:
            stop = fill_price * (1.0 - self.config.stop_loss_pct)
        if signal.take_distance is not None:
            take = fill_price + signal.take_distance
        else:
            take = fill_price * (1.0 + self.config.take_profit_pct)
        return stop, take

    def plan_entry(
        self,
        *,
        equity: float,
        cash: float,
        fill_price: float,
        signal: Signal,
        halted: bool,
    ) -> tuple[EntryPlan | None, str]:
        if halted:
            return None, "daily_loss_halt"
        if fill_price <= 0 or equity <= 0:
            return None, "invalid_price"
        stop, take = self.bracket(fill_price, signal)
        if not stop < fill_price < take:
            return None, "invalid_bracket"
        fee_rate = self.config.taker_fee
        budget = equity * self.config.max_position_pct
        affordable = cash / (1.0 + fee_rate) if fee_rate else cash
        notional = min(budget, affordable)
        if notional + 1e-9 < self.config.min_notional:
            return None, "min_notional"
        # Keep the cap exact when cash is the constraint but still under the equity cap.
        if notional > budget:
            notional = budget
        qty = notional / fill_price
        fee = notional * fee_rate
        if cash + 1e-9 < notional + fee:
            return None, "insufficient_cash"
        return (
            EntryPlan(qty=qty, notional=notional, fee=fee, stop=stop, take=take),
            "approved",
        )

    @staticmethod
    def daily_loss_reached(day_start_equity: float, equity: float, cap_pct: float) -> bool:
        """True when the day's loss is at least `cap_pct`, compared in centavos."""
        if day_start_equity <= 0:
            return False
        loss_cents = int(round((day_start_equity - equity) * 100))
        cap_cents = int(round(day_start_equity * cap_pct * 100))
        return loss_cents >= cap_cents
