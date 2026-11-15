"""Local safety gate standing in for 0xsyncroot/opentrade.

This is not a binding to that repository. It is the v0.1 policy: simulated
paper and backtest orders can pass; live mode cannot; size and symbol are
checked again even after the risk manager.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    reason: str


class OpenTradeGate:
    def __init__(self, allowed_symbols: set[str], max_position_pct: float = 0.20) -> None:
        self.allowed_symbols = allowed_symbols
        self.max_position_pct = max_position_pct

    def allow(self, *, mode: str, symbol: str, notional: float, equity: float) -> GateDecision:
        if mode == "live":
            return GateDecision(False, "opentrade: live trading blocked in v0.1.0")
        if mode not in {"paper", "backtest"}:
            return GateDecision(False, "opentrade: unknown mode")
        if symbol not in self.allowed_symbols:
            return GateDecision(False, "opentrade: symbol not allowed")
        if equity > 0 and notional > equity * self.max_position_pct + 1e-6:
            return GateDecision(False, "opentrade: notional above cap")
        return GateDecision(True, "opentrade: simulation allowed")

    def allow_exit(self, mode: str) -> GateDecision:
        if mode == "live":
            return GateDecision(False, "opentrade: live exit blocked in v0.1.0")
        if mode not in {"paper", "backtest"}:
            return GateDecision(False, "opentrade: unknown mode")
        return GateDecision(True, "opentrade: simulated exit allowed")
