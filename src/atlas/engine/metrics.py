"""Trade statistics shared by the backtest report and the paper report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from atlas.models import Fill


@dataclass(frozen=True, slots=True)
class TradeStats:
    fills: int
    round_trips: int
    wins: int
    losses: int
    win_rate: float
    fees: float
    realized_pnl: float
    exit_reasons: tuple[tuple[str, int], ...]

    @property
    def win_rate_pct(self) -> float:
        return self.win_rate * 100.0


def summarize(fills: Sequence[Fill]) -> TradeStats:
    sells = [fill for fill in fills if fill.side == "SELL"]
    wins = sum(1 for fill in sells if fill.pnl_brl > 0)
    losses = sum(1 for fill in sells if fill.pnl_brl <= 0)
    reasons = Counter(fill.reason for fill in sells)
    trips = len(sells)
    return TradeStats(
        fills=len(fills),
        round_trips=trips,
        wins=wins,
        losses=losses,
        win_rate=(wins / trips) if trips else 0.0,
        fees=sum(fill.fee_brl for fill in fills),
        realized_pnl=sum(fill.pnl_brl for fill in sells),
        exit_reasons=tuple(sorted(reasons.items())),
    )
