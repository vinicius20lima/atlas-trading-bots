"""CLI behavior that must stay offline."""

from __future__ import annotations

from atlas.cli import main
from atlas.live import CONFIRM_ENV, refusal_message


def test_live_refuses_with_and_without_the_future_flags(capsys, monkeypatch) -> None:
    monkeypatch.delenv(CONFIRM_ENV, raising=False)
    assert main(["live"]) == 2
    err = capsys.readouterr().err
    assert "not implemented" in err
    assert "flag_present=False" in err

    monkeypatch.setenv(CONFIRM_ENV, "YES")
    assert main(["live", "--enable-live"]) == 2
    err = capsys.readouterr().err
    assert "flag_present=True" in err
    assert "confirm_present=True" in err
    assert "No order was sent" in err


def test_report_without_state(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path / "state"))
    # Avoid picking up a developer .env from a parent directory.
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_API_SECRET", raising=False)
    assert main(["report", "--state-dir", str(tmp_path / "missing")]) == 0
    out = capsys.readouterr().out
    assert "não iniciado" in out
    assert "R$ 500.00" in out


def test_help(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("help did not exit")
    assert "backtest" in capsys.readouterr().out


def test_refusal_text_never_claims_an_order_was_sent() -> None:
    text = refusal_message(["--enable-live"], {CONFIRM_ENV: "YES", "BINANCE_API_SECRET": "nope"})
    assert "nope" not in text
    assert "No order was sent" in text
