"""Role wiring: vetoes, the GMGN read client, and the live refusal."""

from __future__ import annotations

from datetime import datetime

from tests.support import Scripted, runtime, settings

from atlas.clock import UTC
from atlas.debate import DebateAdapter, DebateResult
from atlas.errors import CredentialsMissing, LiveTradingDisabled
from atlas.exec.gmgn import GMGNExecutor, GMGNReadClient
from atlas.models import Signal
from atlas.signals.smart_money import SmartMoneySignals, SmartMoneyView, flow_bias
from atlas.solana_kit import SolanaKit


def _signal() -> Signal:
    return Signal("BTCBRL", "enter_long", datetime(2024, 6, 1, tzinfo=UTC), "test")


def test_flow_bias_thresholds() -> None:
    assert flow_bias(1) == "bullish"
    assert flow_bias(-1) == "bearish"
    assert flow_bias(0.1, threshold=0.2) == "neutral"


def test_bearish_smart_money_vetoes_and_missing_key_does_not() -> None:
    config = settings()
    strategy = Scripted({})

    class Bearish:
        def view(self, symbol: str) -> SmartMoneyView:
            return SmartMoneyView(True, "bearish", 0.91, "wallets selling")

    blocked = runtime(strategy, config, {"BTCBRL"}, smart_money=Bearish())  # type: ignore[arg-type]
    decision = blocked.decide_entry(_signal(), 100, equity=1_000, cash=1_000, halted=False)
    assert decision.action == "reject" and decision.reason == "smart_money_veto"

    idle = SmartMoneySignals(GMGNReadClient(""))
    assert idle.view("BTCBRL").available is False


class _Oppose(DebateAdapter):
    def __init__(self) -> None:
        super().__init__(enabled=True)

    def review(self, signal: Signal) -> DebateResult:
        return DebateResult(True, "oppose", "no")


def test_debate_can_oppose_when_enabled() -> None:
    strategy = Scripted({})
    orch = runtime(strategy, settings(), {"BTCBRL"}, debate=_Oppose())
    decision = orch.decide_entry(_signal(), 100, equity=1_000, cash=1_000, halted=False)
    assert decision.reason == "debate_oppose"


def test_live_gate_blocks_even_if_someone_builds_the_orchestrator() -> None:
    strategy = Scripted({})
    orch = runtime(strategy, settings(), {"BTCBRL"}, mode="live")
    decision = orch.decide_entry(_signal(), 100, equity=1_000, cash=1_000, halted=False)
    assert decision.action == "reject"
    assert "live" in decision.reason
    exit_decision = orch.decide_exit(_signal())
    assert exit_decision.action == "reject"


def test_gmgn_reads_with_header_and_refuses_swap() -> None:
    seen: dict[str, object] = {}

    def get_json(url: str, headers: dict[str, str] | None = None):
        seen["url"] = url
        seen["headers"] = headers
        return {"data": []}

    client = GMGNReadClient("gmgn-test", get_json=get_json)
    assert client.trending(chain="sol", interval="1h", limit=3) == {"data": []}
    assert "/v1/market/rank" in str(seen["url"])
    assert "gmgn-test" not in str(seen["url"])
    headers = seen["headers"]
    assert isinstance(headers, dict) and headers["X-APIKEY"] == "gmgn-test"

    try:
        GMGNExecutor(client).swap(chain="sol")
    except LiveTradingDisabled:
        pass
    else:
        raise AssertionError("swap ran")

    try:
        GMGNReadClient("").token_info("sol", "addr")
    except CredentialsMissing:
        pass
    else:
        raise AssertionError("missing key called the network")

    try:
        SolanaKit().send("tx")
    except LiveTradingDisabled:
        pass
    else:
        raise AssertionError("solana send ran")


def test_disabled_debate_is_neutral() -> None:
    result = DebateAdapter(enabled=False).review(_signal())
    assert result.available is False
    assert result.stance == "neutral"
