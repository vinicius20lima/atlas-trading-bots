"""Paper state: no backfill, then a fill on the next closed candle."""

from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import make_candles
from tests.support import Scripted, runtime, settings

from atlas.clock import UTC
from atlas.engine.paper import load_book, new_book, save_book, step_book
from atlas.engine.report import render_paper


def test_first_cycle_does_not_backfill_and_second_cycle_fills(tmp_path) -> None:
    config = settings(state_dir=tmp_path)
    strategy = Scripted({2: "enter_long"})
    start = datetime(2024, 6, 1, 12, tzinfo=UTC)
    first = make_candles(
        [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)],
        start=start,
        step=timedelta(hours=1),
    )
    book = new_book(config, strategy, ["BTCBRL"], source="binance")
    assert (
        step_book(book, {"BTCBRL": first}, strategy, runtime(strategy, config, {"BTCBRL"}, "paper"))
        is None
    )
    assert book.fills == []
    assert book.cash == 1_000

    later_rows = [(100, 101, 99, 100)] * 3 + [(110, 111, 109, 110)]
    second = make_candles(later_rows, start=start, step=timedelta(hours=1))
    step_book(book, {"BTCBRL": second}, strategy, runtime(strategy, config, {"BTCBRL"}, "paper"))
    assert len(book.fills) == 1
    assert book.fills[0]["side"] == "BUY"
    assert book.fills[0]["price"] == 110

    save_book(book, tmp_path)
    loaded = load_book(tmp_path)
    assert loaded is not None
    assert loaded.cash == book.cash
    assert (tmp_path / "trades.csv").read_text(encoding="utf-8").count("BUY") == 1

    text = render_paper(loaded, datetime(2024, 6, 2, tzinfo=UTC), started=True)
    assert "BTCBRL" in text
    assert "simulado, sem dinheiro real" in text
    assert "110" in text


def test_old_signal_is_not_imported(tmp_path) -> None:
    config = settings()
    strategy = Scripted({0: "enter_long"})
    start = datetime(2024, 6, 1, tzinfo=UTC)
    book = new_book(config, strategy, ["BTCBRL"], "binance")
    history = make_candles([(100, 100, 100, 100)] * 3, start=start, step=timedelta(hours=1))
    step_book(book, {"BTCBRL": history}, strategy, runtime(strategy, config, {"BTCBRL"}, "paper"))
    extended = make_candles([(100, 100, 100, 100)] * 4, start=start, step=timedelta(hours=1))
    step_book(book, {"BTCBRL": extended}, strategy, runtime(strategy, config, {"BTCBRL"}, "paper"))
    assert book.fills == []
