"""Smart-money context from GMGN. Read-only, and neutral unless a flow is supplied.

v0.1 does not turn a wallet list into a BRL-spot direction. `flow_bias` is the
hook a later version can call once a net-flow figure exists. A bearish view
with confidence >= 0.7 vetoes new longs in the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from atlas.exec.gmgn import GMGNReadClient

Bias = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True, slots=True)
class SmartMoneyView:
    available: bool
    bias: Bias
    confidence: float
    notes: str


def flow_bias(net_quote_flow: float, threshold: float = 0.0) -> Bias:
    """Map a net quote flow to a direction. Positive means net buying."""
    if net_quote_flow > threshold:
        return "bullish"
    if net_quote_flow < -threshold:
        return "bearish"
    return "neutral"


class SmartMoneySignals:
    def __init__(
        self,
        client: GMGNReadClient | None = None,
        allow_network: bool = False,
    ) -> None:
        self.client = client
        self.allow_network = allow_network

    def view(self, symbol: str) -> SmartMoneyView:
        del symbol  # BRL spot symbols are not GMGN token addresses in v0.1.
        if self.client is None or not self.client.available:
            return SmartMoneyView(
                False,
                "neutral",
                0.0,
                "smart money idle: GMGN_API_KEY is not set",
            )
        if not self.allow_network:
            return SmartMoneyView(
                False,
                "neutral",
                0.0,
                "smart money idle: network is off for this cycle",
            )
        self.client.smart_money()
        return SmartMoneyView(
            True,
            "neutral",
            0.0,
            "GMGN smart-money wallets were fetched; v0.1 does not map them to a BRL direction",
        )
