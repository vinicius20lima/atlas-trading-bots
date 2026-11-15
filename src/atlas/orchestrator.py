"""Gather role notes, then let the strategy signal through the risk manager."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from atlas.config import Settings
from atlas.debate import DebateAdapter
from atlas.exec.gmgn import GMGNExecutor, GMGNReadClient
from atlas.models import Signal
from atlas.opentrade import OpenTradeGate
from atlas.risk.manager import RiskConfig, RiskManager
from atlas.signals.smart_money import SmartMoneySignals
from atlas.solana_kit import SolanaKit
from atlas.strategies.base import Strategy

DecisionAction = Literal["enter_long", "exit_long", "reject"]


@dataclass(frozen=True, slots=True)
class Decision:
    action: DecisionAction
    reason: str
    qty: float = 0.0
    notional: float = 0.0
    fee: float = 0.0
    stop: float | None = None
    take: float | None = None
    notes: tuple[str, ...] = ()


class Orchestrator:
    def __init__(
        self,
        *,
        strategy: Strategy,
        risk: RiskManager,
        mode: str,
        smart_money: SmartMoneySignals,
        debate: DebateAdapter,
        opentrade: OpenTradeGate,
        solana_kit: SolanaKit,
        gmgn: GMGNExecutor,
    ) -> None:
        if mode not in {"paper", "backtest", "live"}:
            raise ValueError(f"unknown mode {mode}")
        self.strategy = strategy
        self.risk = risk
        self.mode = mode
        self.smart_money = smart_money
        self.debate = debate
        self.opentrade = opentrade
        self.solana_kit = solana_kit
        self.gmgn = gmgn

    def decide_entry(
        self,
        signal: Signal,
        fill_price: float,
        *,
        equity: float,
        cash: float,
        halted: bool,
    ) -> Decision:
        view = self.smart_money.view(signal.symbol)
        notes = [view.notes, self.solana_kit.status_note(), self.gmgn.status_note()]
        if view.available and view.bias == "bearish" and view.confidence >= 0.7:
            return Decision("reject", "smart_money_veto", notes=tuple(notes))
        if self.debate.enabled:
            review = self.debate.review(signal)
            notes.append(review.notes)
            if review.available and review.stance == "oppose":
                return Decision("reject", "debate_oppose", notes=tuple(notes))
        plan, reason = self.risk.plan_entry(
            equity=equity,
            cash=cash,
            fill_price=fill_price,
            signal=signal,
            halted=halted,
        )
        if plan is None:
            return Decision("reject", reason, notes=tuple(notes))
        gate = self.opentrade.allow(
            mode=self.mode,
            symbol=signal.symbol,
            notional=plan.notional,
            equity=equity,
        )
        if not gate.allowed:
            return Decision("reject", gate.reason, notes=tuple([*notes, gate.reason]))
        return Decision(
            "enter_long",
            signal.reason,
            qty=plan.qty,
            notional=plan.notional,
            fee=plan.fee,
            stop=plan.stop,
            take=plan.take,
            notes=tuple([*notes, gate.reason]),
        )

    def decide_exit(self, signal: Signal) -> Decision:
        gate = self.opentrade.allow_exit(self.mode)
        if not gate.allowed:
            return Decision("reject", gate.reason)
        return Decision("exit_long", signal.reason, notes=(gate.reason,))


def build_orchestrator(
    strategy: Strategy,
    settings: Settings,
    mode: str,
    symbols: set[str],
    *,
    smart_money: SmartMoneySignals | None = None,
    debate: DebateAdapter | None = None,
    taker_fee: float | None = None,
) -> Orchestrator:
    risk = RiskManager(
        RiskConfig(
            max_position_pct=settings.max_position_pct,
            stop_loss_pct=settings.stop_loss_pct,
            take_profit_pct=settings.take_profit_pct,
            daily_loss_cap_pct=settings.daily_loss_cap_pct,
            taker_fee=settings.taker_fee if taker_fee is None else taker_fee,
            min_notional=settings.min_notional,
        )
    )
    client = GMGNReadClient(
        api_key=os.environ.get("GMGN_API_KEY", ""),
        base_url=settings.gmgn_base_url,
    )
    return Orchestrator(
        strategy=strategy,
        risk=risk,
        mode=mode,
        smart_money=smart_money
        if smart_money is not None
        else SmartMoneySignals(client, allow_network=False),
        debate=debate if debate is not None else DebateAdapter(enabled=False),
        opentrade=OpenTradeGate(set(symbols), settings.max_position_pct),
        solana_kit=SolanaKit(),
        gmgn=GMGNExecutor(client),
    )
