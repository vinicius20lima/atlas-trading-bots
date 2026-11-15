"""Runtime settings. Secrets stay in the environment and are never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env without overriding existing variables."""
    env_path = path if path is not None else Path(".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _symbols_env(default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get("ATLAS_SYMBOLS", "").strip()
    if not raw:
        return default
    symbols = tuple(part.strip().upper() for part in raw.split(",") if part.strip())
    if not symbols:
        return default
    return symbols


@dataclass(frozen=True, slots=True)
class Settings:
    """Simulation defaults. Empty environment variables keep these values."""

    taker_fee: float = 0.001
    starting_balance: float = 500.0
    max_position_pct: float = 0.20
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.05
    daily_loss_cap_pct: float = 0.05
    min_notional: float = 10.0
    timezone: str = "America/Manaus"
    state_dir: Path = Path("state")
    symbols: tuple[str, ...] = ("BTCBRL", "ETHBRL", "SOLBRL")
    # Public market data. api.binance.com returns HTTP 451 from some regions.
    binance_data_base_url: str = "https://data-api.binance.vision"
    # Signed read-only account calls. Not used to place orders.
    binance_api_base_url: str = "https://api.binance.com"
    gmgn_base_url: str = "https://openapi.gmgn.ai"

    def with_overrides(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)


def load_settings() -> Settings:
    load_dotenv()
    data_base = os.environ.get("BINANCE_DATA_BASE_URL", "").strip()
    api_base = os.environ.get("BINANCE_API_BASE_URL", "").strip()
    gmgn_base = os.environ.get("GMGN_BASE_URL", "").strip()
    state_dir = os.environ.get("ATLAS_STATE_DIR", "").strip() or "state"
    return Settings(
        taker_fee=_float_env("ATLAS_TAKER_FEE", 0.001),
        starting_balance=_float_env("ATLAS_STARTING_BALANCE", 500.0),
        state_dir=Path(state_dir),
        symbols=_symbols_env(("BTCBRL", "ETHBRL", "SOLBRL")),
        binance_data_base_url=data_base or "https://data-api.binance.vision",
        binance_api_base_url=api_base or "https://api.binance.com",
        gmgn_base_url=gmgn_base or "https://openapi.gmgn.ai",
    )
