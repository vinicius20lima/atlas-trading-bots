"""Repo rules: secrets stay out, the version is 0.1.0, live orders are absent."""

from __future__ import annotations

import subprocess
from pathlib import Path

from atlas import __version__
from atlas.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_version() -> None:
    assert __version__ == "0.1.0"
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = { attr = "atlas.__version__" }' in text
    assert "0.1.0" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_default_fee_is_binance_spot_vip0() -> None:
    assert Settings().taker_fee == 0.001
    assert Settings().starting_balance == 500
    assert Settings().max_position_pct == 0.20
    assert Settings().stop_loss_pct == 0.03
    assert Settings().take_profit_pct == 0.05
    assert Settings().daily_loss_cap_pct == 0.05
    assert Settings().timezone == "America/Manaus"


def test_env_example_has_names_and_empty_values() -> None:
    keys: set[str] = set()
    for raw in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        assert value.strip() == ""
        keys.add(key.strip())
    required = {
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "GMGN_API_KEY",
        "FOXBIT_API_KEY",
        "FOXBIT_API_SECRET",
        "MERCADO_BITCOIN_API_KEY",
        "MERCADO_BITCOIN_API_SECRET",
    }
    assert required <= keys


def test_gitignore_blocks_secrets_and_keeps_the_example() -> None:
    ignored = [
        ".env",
        ".env.local",
        "wallet.pem",
        "keys/api.pem",
        "state/state.json",
        "logs/paper.log",
    ]
    for relative in ignored:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0, relative
    example = subprocess.run(
        ["git", "check-ignore", "-q", "--", ".env.example"],
        cwd=ROOT,
        check=False,
    )
    assert example.returncode == 1


def test_readme_states_there_is_no_profit_guarantee() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "não há garantia de lucro" in text
    assert "recomendação de investimento" in text


def test_source_has_no_order_endpoint() -> None:
    blob = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py"))
    assert "/api/v3/order" not in blob
    assert "/v1/trade/swap" not in blob
    http = (ROOT / "src/atlas/http.py").read_text(encoding="utf-8")
    assert 'method="POST"' not in http
    assert "method='POST'" not in http
