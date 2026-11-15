"""Optional adapter for TauricResearch/TradingAgents.

The package is not a dependency. With the adapter disabled, or enabled but
not installed, the review is neutral and does not block the strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from atlas.models import Signal

Stance = Literal["support", "oppose", "neutral"]


@dataclass(frozen=True, slots=True)
class DebateResult:
    available: bool
    stance: Stance
    notes: str


class DebateAdapter:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def review(self, signal: Signal) -> DebateResult:
        del signal
        if not self.enabled:
            return DebateResult(False, "neutral", "debate disabled")
        return DebateResult(
            False,
            "neutral",
            "TauricResearch/TradingAgents is not installed; no LLM debate in v0.1.0",
        )
