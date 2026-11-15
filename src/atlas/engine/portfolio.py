"""Cash account used by the backtest and the paper runner. Long only, no leverage."""

from __future__ import annotations

from datetime import datetime

from atlas.clock import day_key
from atlas.models import Fill, Position
from atlas.risk.manager import RiskManager


class Portfolio:
    def __init__(self, cash: float) -> None:
        if cash <= 0:
            raise ValueError("starting cash must be positive")
        self.cash = cash
        self.starting_balance = cash
        self.realized_pnl = 0.0
        self.fees_paid = 0.0
        self.peak_equity = cash
        self.max_drawdown_pct = 0.0
        self.day: str | None = None
        self.day_start_equity = cash
        self.halted = False
        self.positions: dict[str, Position] = {}
        self.last_marks: dict[str, float] = {}
        self.fills: list[Fill] = []

    def equity(self) -> float:
        total = self.cash
        for symbol, position in self.positions.items():
            price = self.last_marks.get(symbol, position.entry_price)
            total += position.qty * price
        return total

    def update_drawdown(self, equity: float | None = None) -> float:
        marked = self.equity() if equity is None else equity
        if marked > self.peak_equity:
            self.peak_equity = marked
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - marked) / self.peak_equity
            if drawdown > self.max_drawdown_pct:
                self.max_drawdown_pct = drawdown
        return marked

    def roll_day(self, when: datetime) -> None:
        """Start a new America/Manaus day using the current marks, before this bar's trades."""
        key = day_key(when)
        if self.day == key:
            return
        self.day = key
        self.day_start_equity = self.equity()
        self.halted = False

    def refresh_halt(self, cap_pct: float) -> bool:
        if RiskManager.daily_loss_reached(self.day_start_equity, self.equity(), cap_pct):
            self.halted = True
        return self.halted

    def open_long(
        self,
        symbol: str,
        *,
        qty: float,
        notional: float,
        fee: float,
        stop: float,
        take: float,
        time: datetime,
        reason: str,
        fill_price: float,
    ) -> Fill:
        self.cash -= notional + fee
        self.fees_paid += fee
        self.positions[symbol] = Position(
            qty=qty,
            entry_price=fill_price,
            entry_notional=notional,
            entry_fee=fee,
            stop=stop,
            take=take,
            entry_time=time,
            entry_reason=reason,
        )
        self.last_marks[symbol] = fill_price
        equity = self.update_drawdown()
        fill = Fill(
            time=time,
            side="BUY",
            pair=symbol,
            qty=qty,
            price=fill_price,
            fee_brl=fee,
            pnl_brl=0.0,
            reason=reason,
            equity_after=equity,
        )
        self.fills.append(fill)
        return fill

    def close_long(
        self,
        symbol: str,
        *,
        time: datetime,
        price: float,
        reason: str,
        fee_rate: float,
    ) -> Fill:
        position = self.positions.pop(symbol)
        notional = position.qty * price
        fee = notional * fee_rate
        self.cash += notional - fee
        pnl = notional - fee - position.entry_notional - position.entry_fee
        self.realized_pnl += pnl
        self.fees_paid += fee
        self.last_marks[symbol] = price
        equity = self.update_drawdown()
        fill = Fill(
            time=time,
            side="SELL",
            pair=symbol,
            qty=position.qty,
            price=price,
            fee_brl=fee,
            pnl_brl=pnl,
            reason=reason,
            equity_after=equity,
        )
        self.fills.append(fill)
        return fill
