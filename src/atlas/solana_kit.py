"""Placeholder for sendaifun/solana-agent-kit.

v0.1 holds no keypair and does not build or send transactions. The Binance
BRL spot path does not use this role.
"""

from __future__ import annotations

from atlas.errors import LiveTradingDisabled


class SolanaKit:
    def status_note(self) -> str:
        return "solana-agent-kit is not connected in v0.1.0; no transaction is signed"

    def send(self, *_args: object, **_kwargs: object) -> None:
        raise LiveTradingDisabled("solana-agent-kit send is not implemented in v0.1.0.")
