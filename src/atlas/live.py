"""Live trading stub. There is no order path in v0.1, with or without the future flags."""

from __future__ import annotations

from collections.abc import Mapping

LIVE_FLAG = "--enable-live"
CONFIRM_ENV = "ATLAS_LIVE_CONFIRM"
CONFIRM_VALUE = "YES"


def refusal_message(argv: list[str], env: Mapping[str, str]) -> str:
    has_flag = LIVE_FLAG in argv
    has_confirm = env.get(CONFIRM_ENV) == CONFIRM_VALUE
    return (
        "Live trading is not implemented in v0.1.0. No order was sent.\n"
        "A later version will require both the explicit flag --enable-live and "
        "ATLAS_LIVE_CONFIRM=YES, and only after a person reviews paper results. "
        "Passing them today still does nothing.\n"
        f"flag_present={has_flag} confirm_present={has_confirm}"
    )
