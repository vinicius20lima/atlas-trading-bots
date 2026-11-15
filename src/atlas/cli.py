"""Command line. `python -m atlas backtest|paper|report|live|account`."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

from atlas import __version__
from atlas.clock import now_utc, parse_time
from atlas.config import Settings, load_settings
from atlas.data.binance import BinanceAdapter
from atlas.engine.backtest import run_backtest
from atlas.engine.paper import (
    TRADES_NAME,
    load_book,
    make_orchestrator,
    new_book,
    read_trades_csv,
    save_book,
    step_book,
)
from atlas.engine.report import render_backtest, render_comparison, render_header, render_paper
from atlas.errors import AtlasError, LiveTradingDisabled
from atlas.intervals import INTERVAL_DELTA
from atlas.live import refusal_message
from atlas.strategies import build_strategy

DEFAULT_DAYS = 90


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LiveTradingDisabled as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except AtlasError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m atlas",
        description=(
            f"Atlas {__version__}: simulação de trading cripto em BRL. A v0.1 não envia ordens."
        ),
    )
    parser.add_argument("--version", action="version", version=f"atlas {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    backtest = sub.add_parser("backtest", help="Compara estratégias em candles públicos.")
    backtest.add_argument(
        "--strategy",
        default="both",
        choices=["both", "ema_crossover", "atr_trend"],
    )
    backtest.add_argument("--days", type=int, default=DEFAULT_DAYS)
    backtest.add_argument("--symbols", default="", help="Lista separada por vírgula.")
    backtest.add_argument("--balance", type=float, default=None)
    backtest.add_argument("--fee", type=float, default=None, help="Taxa taker por lado. Ex.: 0.001")
    backtest.add_argument("--end", default="", help="Fim da janela em ISO-8601. Padrão: agora.")
    backtest.set_defaults(func=cmd_backtest)

    paper = sub.add_parser("paper", help="Um ciclo de paper trading (padrão) ou --watch.")
    paper.add_argument("--strategy", default="atr_trend", choices=["ema_crossover", "atr_trend"])
    paper.add_argument("--symbols", default="")
    paper.add_argument("--balance", type=float, default=None)
    paper.add_argument("--fee", type=float, default=None)
    paper.add_argument("--state-dir", default="")
    paper.add_argument("--reset", action="store_true", help="Apaga state.json e trades.csv antes.")
    paper.add_argument("--watch", action="store_true", help="Repete até Ctrl+C.")
    paper.add_argument(
        "--poll", type=float, default=60.0, help="Segundos entre ciclos com --watch."
    )
    paper.set_defaults(func=cmd_paper)

    report = sub.add_parser("report", help="Mostra o paper a partir de state.json e trades.csv.")
    report.add_argument("--state-dir", default="")
    report.set_defaults(func=cmd_report)

    live = sub.add_parser("live", help="Recusa. Trading real não existe na v0.1.")
    live.add_argument(
        "--enable-live",
        action="store_true",
        help="Reservado para uma versão futura. Hoje não liga nada.",
    )
    live.set_defaults(func=cmd_live)

    account = sub.add_parser("account", help="Leitura opcional da conta Binance. Sem ordens.")
    account.set_defaults(func=cmd_account)
    return parser


def cmd_backtest(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    if args.days <= 0:
        raise AtlasError("--days precisa ser positivo")
    end = parse_time(args.end) if args.end else now_utc()
    symbols = _symbols(args.symbols, settings)
    names = ["ema_crossover", "atr_trend"] if args.strategy == "both" else [args.strategy]
    print(render_header(settings, args.days, end, symbols))
    window_start = end - timedelta(days=args.days)
    results = []
    adapter = _adapter(settings)
    for name in names:
        strategy = build_strategy(name)
        pad = INTERVAL_DELTA[strategy.interval] * (strategy.warmup_bars + 2)
        candles = _fetch(adapter, symbols, strategy.interval, window_start - pad, end)
        result = run_backtest(candles, strategy, settings, window_start=window_start)
        results.append(result)
        print(render_backtest(result))
        print()
    if len(results) > 1:
        print(render_comparison(results))
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    strategy = build_strategy(args.strategy)
    symbols = _symbols(args.symbols, settings)
    directory = Path(args.state_dir) if args.state_dir else settings.state_dir
    if args.reset:
        _reset_state(directory)
    book = load_book(directory)
    if book is None:
        book = new_book(settings, strategy, list(symbols), source="binance")
    else:
        if book.strategy != strategy.name:
            raise AtlasError(
                f"state.json usa {book.strategy}. Rode com --strategy {book.strategy} ou --reset."
            )
        if list(symbols) != list(book.symbols) and set(symbols) != set(book.symbols):
            raise AtlasError(
                f"state.json usa {', '.join(book.symbols)}. Mude os símbolos só com --reset."
            )
        if args.fee is not None and abs(args.fee - book.taker_fee) > 1e-12:
            print(
                f"aviso: --fee {args.fee} ignorado; o livro já usa {book.taker_fee}.",
                file=sys.stderr,
            )
    adapter = _adapter(settings)
    while True:
        end = now_utc()
        start = _paper_start(book, strategy, end)
        candles = _fetch(adapter, tuple(book.symbols), strategy.interval, start, end)
        before = len(book.fills)
        outcome = step_book(book, candles, strategy, make_orchestrator(book, strategy, settings))
        save_book(book, directory)
        added = len(book.fills) - before
        if outcome is None:
            print(
                "Paper armado. Nenhum trade histórico foi importado. O próximo candle pode operar."
            )
        else:
            print(f"Ciclo ok. Novos fills: {added}.")
        print(render_paper(book, end, started=True))
        if not args.watch:
            return 0
        time.sleep(args.poll)


def cmd_report(args: argparse.Namespace) -> int:
    settings = load_settings()
    directory = Path(args.state_dir) if args.state_dir else settings.state_dir
    book = load_book(directory)
    started = book is not None
    if book is None:
        book = new_book(settings, build_strategy("atr_trend"), list(settings.symbols), "binance")
    csv_fills = read_trades_csv(directory / TRADES_NAME)
    if csv_fills:
        book.fills = csv_fills
    print(render_paper(book, now_utc(), started=started))
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    argv = ["--enable-live"] if args.enable_live else []
    print(refusal_message(argv, os.environ), file=sys.stderr)
    return 2


def cmd_account(_args: argparse.Namespace) -> int:
    settings = load_settings()
    snapshot = _adapter(settings).get_account()
    if snapshot is None:
        print("BINANCE_API_KEY e BINANCE_API_SECRET não estão definidos.")
        print("A conta é opcional. Klines públicos não usam chave.")
        print("A v0.1 não envia ordens mesmo que a chave exista.")
        return 0
    print("Conta Binance (somente leitura). Nenhuma ordem foi enviada.")
    print(f"can_trade={snapshot.can_trade}")
    if snapshot.taker_commission is not None:
        print(f"taker na conta: {snapshot.taker_commission * 100:.4f}%")
        print(f"taker simulado: {settings.taker_fee * 100:.4f}% (ATLAS_TAKER_FEE)")
    if snapshot.maker_commission is not None:
        print(f"maker na conta: {snapshot.maker_commission * 100:.4f}%")
    if not snapshot.balances:
        print("Saldos não zero: (nenhum)")
    else:
        print("Saldos não zero:")
        for balance in snapshot.balances:
            print(f"  {balance.asset}: livre={balance.free} bloqueado={balance.locked}")
    return 0


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = load_settings()
    overrides: dict[str, object] = {}
    if getattr(args, "balance", None) is not None:
        overrides["starting_balance"] = args.balance
    if getattr(args, "fee", None) is not None:
        overrides["taker_fee"] = args.fee
    if not overrides:
        return settings
    return settings.with_overrides(**overrides)


def _symbols(raw: str, settings: Settings) -> tuple[str, ...]:
    if not raw.strip():
        return settings.symbols
    symbols = tuple(part.strip().upper() for part in raw.split(",") if part.strip())
    if not symbols:
        raise AtlasError("lista de símbolos vazia")
    return symbols


def _adapter(settings: Settings) -> BinanceAdapter:
    return BinanceAdapter(
        data_base_url=settings.binance_data_base_url,
        api_base_url=settings.binance_api_base_url,
    )


def _fetch(adapter: BinanceAdapter, symbols: tuple[str, ...], interval: str, start, end):
    candles = {}
    for symbol in symbols:
        print(f"baixando {symbol} {interval}...", flush=True)
        series = adapter.get_klines(symbol, interval, start=start, end=end)
        print(f"  {len(series)} candles fechados", flush=True)
        candles[symbol] = series
    return candles


def _paper_start(book, strategy, end):
    pad = INTERVAL_DELTA[strategy.interval] * (strategy.warmup_bars + 5)
    if not book.cursors:
        return end - pad
    oldest = min(parse_time(value) for value in book.cursors.values())
    return oldest - pad


def _reset_state(directory: Path) -> None:
    for name in ("state.json", "trades.csv", "state.json.tmp"):
        path = directory / name
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    sys.exit(main())
