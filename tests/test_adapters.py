"""Adapter parsing and stubs. HTTP is injected; nothing here touches the network."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from atlas.data.binance import (
    SIGN_EXAMPLE_QUERY,
    SIGN_EXAMPLE_SECRET,
    SIGN_EXAMPLE_SIGNATURE,
    BinanceAdapter,
    parse_account,
    parse_kline,
    sign_query,
)
from atlas.data.foxbit import FoxbitAdapter
from atlas.data.gmgn import GMGNMarketAdapter
from atlas.data.mercadobitcoin import MercadoBitcoinAdapter
from atlas.errors import AdapterError, AdapterUnavailable

ROOT = Path(__file__).resolve().parents[1]


def _kline(open_ms: int, price: str = "100") -> list[object]:
    return [
        open_ms,
        price,
        "101",
        "99",
        price,
        "5",
        open_ms + 59_999,
        "0",
        1,
        "0",
        "0",
        "0",
    ]


def test_sign_query_matches_openssl_vector() -> None:
    assert sign_query(SIGN_EXAMPLE_SECRET, SIGN_EXAMPLE_QUERY) == SIGN_EXAMPLE_SIGNATURE


def test_parse_kline_and_account() -> None:
    candle = parse_kline(_kline(1_700_000_000_000, "100"))
    assert candle.open == 100
    assert candle.close_time > candle.open_time
    account = parse_account(
        {
            "canTrade": True,
            "commissionRates": {"maker": "0.001", "taker": "0.001"},
            "balances": [
                {"asset": "BRL", "free": "12.5", "locked": "0"},
                {"asset": "BTC", "free": "0", "locked": "0"},
            ],
        }
    )
    assert account.can_trade is True
    assert account.taker_commission == 0.001
    assert [item.asset for item in account.balances] == ["BRL"]


def test_pagination_dedupes_and_drops_the_open_candle() -> None:
    calls: list[str] = []

    def get_json(url: str, headers: dict[str, str] | None = None):
        del headers
        calls.append(url)
        if len(calls) == 1:
            return [_kline(0), _kline(60_000)]
        if len(calls) == 2:
            return [_kline(60_000), _kline(120_000)]
        return []

    from atlas.clock import UTC

    adapter = BinanceAdapter(
        get_json=get_json,
        sleep=lambda _seconds: None,
        now=lambda: datetime(2024, 1, 2, tzinfo=UTC),
        page_size=2,
    )
    candles = adapter.get_klines("BTCBRL", "1m", start=datetime(1970, 1, 1, tzinfo=UTC))
    assert [int(candle.open_time.timestamp() * 1000) for candle in candles] == [0, 60_000, 120_000]
    assert len(calls) == 3
    assert "startTime=60001" in calls[1]

    forming = _kline(int(datetime(2024, 1, 2, 0, 30, tzinfo=UTC).timestamp() * 1000))
    closed = _kline(int(datetime(2024, 1, 1, 12, tzinfo=UTC).timestamp() * 1000))

    def one_shot(url: str, headers: dict[str, str] | None = None):
        del url, headers
        return [closed, forming]

    later = BinanceAdapter(
        get_json=one_shot,
        now=lambda: datetime(2024, 1, 2, tzinfo=UTC),
    )
    only = later.get_klines("ETHBRL", "1m")
    assert len(only) == 1


def test_signed_account_url_does_not_carry_the_secret() -> None:
    seen: dict[str, object] = {}

    def get_json(url: str, headers: dict[str, str] | None = None):
        seen["url"] = url
        seen["headers"] = headers
        return {"canTrade": False, "balances": [], "commissionRates": {"taker": "0.001"}}

    adapter = BinanceAdapter(
        get_json=get_json,
        api_key="key-id",
        api_secret=SIGN_EXAMPLE_SECRET,
    )
    snapshot = adapter.get_account()
    assert snapshot is not None and snapshot.taker_commission == 0.001
    assert SIGN_EXAMPLE_SECRET not in str(seen["url"])
    assert "signature=" in str(seen["url"])
    headers = seen["headers"]
    assert isinstance(headers, dict) and headers["X-MBX-APIKEY"] == "key-id"


def test_restricted_location_is_explained() -> None:
    def get_json(url: str, headers: dict[str, str] | None = None):
        del url, headers
        raise AdapterError("HTTP 451 /api/v3/klines: restricted location")

    adapter = BinanceAdapter(get_json=get_json)
    try:
        adapter.get_ticker("BTCBRL")
    except AdapterUnavailable as exc:
        assert "451" in str(exc)
        assert "data-api.binance.vision" in str(exc)
    else:
        raise AssertionError("451 was not translated")


def test_stubs_do_not_call_the_network() -> None:
    try:
        MercadoBitcoinAdapter().get_klines("BTCBRL", "15m")
    except AdapterUnavailable as exc:
        assert "Cloudflare" in str(exc)
    else:
        raise AssertionError("mercado bitcoin ran")
    for adapter in (FoxbitAdapter(), GMGNMarketAdapter()):
        try:
            adapter.get_ticker("BTCBRL")
        except AdapterUnavailable:
            continue
        raise AssertionError(adapter.name)
    for relative in (
        "src/atlas/data/foxbit.py",
        "src/atlas/data/mercadobitcoin.py",
        "src/atlas/data/gmgn.py",
    ):
        assert "urlopen" not in (ROOT / relative).read_text(encoding="utf-8")


def test_missing_keys_skip_the_account_call() -> None:
    def get_json(url: str, headers: dict[str, str] | None = None):
        raise AssertionError(url)

    adapter = BinanceAdapter(get_json=get_json, api_key="", api_secret="")
    assert adapter.get_account() is None
