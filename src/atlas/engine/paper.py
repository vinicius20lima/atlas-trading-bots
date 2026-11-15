"""Paper book. The first cycle only arms the cursor; later cycles fill new closes."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from atlas import __version__
from atlas.clock import parse_time
from atlas.config import Settings
from atlas.engine.portfolio import Portfolio
from atlas.engine.simulator import SimulationResult, simulate
from atlas.errors import AtlasError
from atlas.models import Candle, Fill, Position
from atlas.orchestrator import Orchestrator, build_orchestrator
from atlas.strategies.base import Strategy

STATE_NAME = "state.json"
TRADES_NAME = "trades.csv"
CSV_FIELDS = [
    "time",
    "side",
    "pair",
    "qty",
    "price",
    "fee_brl",
    "pnl_brl",
    "reason",
    "equity_after",
]


@dataclass
class PaperBook:
    version: str
    source: str
    strategy: str
    interval: str
    started_at: datetime
    cash: float
    starting_balance: float
    realized_pnl: float
    fees_paid: float
    peak_equity: float
    max_drawdown_pct: float
    day: str | None
    day_start_equity: float
    halted: bool
    positions: dict[str, dict[str, object]]
    last_marks: dict[str, float]
    cursors: dict[str, str]
    fills: list[dict[str, object]] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    taker_fee: float = 0.001

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "source": self.source,
            "strategy": self.strategy,
            "interval": self.interval,
            "started_at": self.started_at.isoformat(),
            "cash": self.cash,
            "starting_balance": self.starting_balance,
            "realized_pnl": self.realized_pnl,
            "fees_paid": self.fees_paid,
            "peak_equity": self.peak_equity,
            "max_drawdown_pct": self.max_drawdown_pct,
            "day": self.day,
            "day_start_equity": self.day_start_equity,
            "halted": self.halted,
            "positions": self.positions,
            "last_marks": self.last_marks,
            "cursors": self.cursors,
            "fills": self.fills,
            "symbols": self.symbols,
            "taker_fee": self.taker_fee,
            "equity": self.equity(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PaperBook:
        return cls(
            version=str(payload.get("version", __version__)),
            source=str(payload.get("source", "binance")),
            strategy=str(payload["strategy"]),
            interval=str(payload["interval"]),
            started_at=parse_time(str(payload["started_at"])),
            cash=float(payload["cash"]),
            starting_balance=float(payload["starting_balance"]),
            realized_pnl=float(payload.get("realized_pnl", 0.0)),
            fees_paid=float(payload.get("fees_paid", 0.0)),
            peak_equity=float(payload.get("peak_equity", payload["cash"])),
            max_drawdown_pct=float(payload.get("max_drawdown_pct", 0.0)),
            day=payload.get("day") if isinstance(payload.get("day"), str) else None,
            day_start_equity=float(payload.get("day_start_equity", payload["starting_balance"])),
            halted=bool(payload.get("halted", False)),
            positions=dict(payload.get("positions") or {}),
            last_marks={k: float(v) for k, v in dict(payload.get("last_marks") or {}).items()},
            cursors={k: str(v) for k, v in dict(payload.get("cursors") or {}).items()},
            fills=list(payload.get("fills") or []),
            symbols=list(payload.get("symbols") or []),
            taker_fee=float(payload.get("taker_fee", 0.001)),
        )

    def equity(self) -> float:
        total = self.cash
        for symbol, raw in self.positions.items():
            mark = self.last_marks.get(symbol)
            if mark is None:
                mark = float(raw["entry_price"])
            total += float(raw["qty"]) * mark
        return total

    def to_portfolio(self) -> Portfolio:
        portfolio = Portfolio(self.starting_balance)
        portfolio.cash = self.cash
        portfolio.realized_pnl = self.realized_pnl
        portfolio.fees_paid = self.fees_paid
        portfolio.peak_equity = self.peak_equity
        portfolio.max_drawdown_pct = self.max_drawdown_pct
        portfolio.day = self.day
        portfolio.day_start_equity = self.day_start_equity
        portfolio.halted = self.halted
        portfolio.last_marks = dict(self.last_marks)
        portfolio.fills = [_fill_from_dict(item) for item in self.fills]
        for symbol, raw in self.positions.items():
            portfolio.positions[symbol] = Position(
                qty=float(raw["qty"]),
                entry_price=float(raw["entry_price"]),
                entry_notional=float(raw["entry_notional"]),
                entry_fee=float(raw["entry_fee"]),
                stop=float(raw["stop"]),
                take=float(raw["take"]),
                entry_time=parse_time(str(raw["entry_time"])),
                entry_reason=str(raw["entry_reason"]),
            )
        return portfolio

    def absorb(self, portfolio: Portfolio) -> None:
        self.cash = portfolio.cash
        self.realized_pnl = portfolio.realized_pnl
        self.fees_paid = portfolio.fees_paid
        self.peak_equity = portfolio.peak_equity
        self.max_drawdown_pct = portfolio.max_drawdown_pct
        self.day = portfolio.day
        self.day_start_equity = portfolio.day_start_equity
        self.halted = portfolio.halted
        self.last_marks = dict(portfolio.last_marks)
        self.fills = [_fill_to_dict(fill) for fill in portfolio.fills]
        self.positions = {
            symbol: {
                "qty": position.qty,
                "entry_price": position.entry_price,
                "entry_notional": position.entry_notional,
                "entry_fee": position.entry_fee,
                "stop": position.stop,
                "take": position.take,
                "entry_time": position.entry_time.isoformat(),
                "entry_reason": position.entry_reason,
            }
            for symbol, position in portfolio.positions.items()
        }


def new_book(settings: Settings, strategy: Strategy, symbols: list[str], source: str) -> PaperBook:
    from atlas.clock import now_utc

    return PaperBook(
        version=__version__,
        source=source,
        strategy=strategy.name,
        interval=strategy.interval,
        started_at=now_utc(),
        cash=settings.starting_balance,
        starting_balance=settings.starting_balance,
        realized_pnl=0.0,
        fees_paid=0.0,
        peak_equity=settings.starting_balance,
        max_drawdown_pct=0.0,
        day=None,
        day_start_equity=settings.starting_balance,
        halted=False,
        positions={},
        last_marks={},
        cursors={},
        fills=[],
        symbols=list(symbols),
        taker_fee=settings.taker_fee,
    )


def step_book(
    book: PaperBook,
    candles_by_symbol: dict[str, list[Candle]],
    strategy: Strategy,
    orchestrator: Orchestrator,
) -> SimulationResult | None:
    """Advance the book. The first call records cursors and does not backfill trades."""
    if strategy.name != book.strategy or strategy.interval != book.interval:
        raise AtlasError(
            f"state.json was started with {book.strategy} ({book.interval}). "
            f"Use that strategy, or pass --reset."
        )
    for symbol, series in candles_by_symbol.items():
        if not series:
            raise AtlasError(f"no closed candles for {symbol}")

    portfolio = book.to_portfolio()
    if not book.cursors:
        for symbol, series in candles_by_symbol.items():
            last = series[-1]
            book.cursors[symbol] = last.close_time.isoformat()
            portfolio.last_marks[symbol] = last.close
        portfolio.roll_day(max(series[-1].open_time for series in candles_by_symbol.values()))
        book.absorb(portfolio)
        return None

    cursors: dict[str, datetime | None] = {}
    for symbol in candles_by_symbol:
        raw = book.cursors.get(symbol)
        if raw is None:
            raise AtlasError(f"no cursor for {symbol}. Reset paper state before adding symbols.")
        cursors[symbol] = parse_time(raw)

    outcome = simulate(
        candles_by_symbol,
        strategy,
        orchestrator,
        portfolio,
        only_after_close=cursors,
    )
    for symbol, series in candles_by_symbol.items():
        book.cursors[symbol] = series[-1].close_time.isoformat()
    book.absorb(outcome.portfolio)
    return outcome


def load_book(directory: Path) -> PaperBook | None:
    path = directory / STATE_NAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AtlasError("state.json is not an object")
    return PaperBook.from_dict(payload)


def save_book(book: PaperBook, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STATE_NAME
    temporary = directory / "state.json.tmp"
    temporary.write_text(json.dumps(book.to_dict(), indent=2), encoding="utf-8")
    os.replace(temporary, path)
    _write_trades(directory / TRADES_NAME, book.fills)


def make_orchestrator(book: PaperBook, strategy: Strategy, settings: Settings) -> Orchestrator:
    symbols = set(book.symbols) or set(settings.symbols)
    return build_orchestrator(
        strategy,
        settings,
        "paper",
        symbols,
        taker_fee=book.taker_fee,
    )


def read_trades_csv(path: Path) -> list[dict[str, object]]:
    """Rows from trades.csv. Empty when the file is missing or has only a header."""
    if not path.is_file() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    parsed: list[dict[str, object]] = []
    for row in rows:
        if not row.get("time"):
            continue
        parsed.append(
            {
                "time": row["time"],
                "side": row.get("side", ""),
                "pair": row.get("pair", ""),
                "qty": float(row.get("qty") or 0),
                "price": float(row.get("price") or 0),
                "fee_brl": float(row.get("fee_brl") or 0),
                "pnl_brl": float(row.get("pnl_brl") or 0),
                "reason": row.get("reason", ""),
                "equity_after": float(row.get("equity_after") or 0),
            }
        )
    return parsed


def _write_trades(path: Path, fills: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for fill in fills:
            writer.writerow({key: fill.get(key, "") for key in CSV_FIELDS})


def _fill_to_dict(fill: Fill) -> dict[str, object]:
    return {
        "time": fill.time.isoformat(),
        "side": fill.side,
        "pair": fill.pair,
        "qty": fill.qty,
        "price": fill.price,
        "fee_brl": fill.fee_brl,
        "pnl_brl": fill.pnl_brl,
        "reason": fill.reason,
        "equity_after": fill.equity_after,
    }


def _fill_from_dict(payload: dict[str, object]) -> Fill:
    side = str(payload["side"])
    if side not in {"BUY", "SELL"}:
        raise AtlasError(f"bad fill side {side}")
    return Fill(
        time=parse_time(str(payload["time"])),
        side=side,  # type: ignore[arg-type]
        pair=str(payload["pair"]),
        qty=float(payload["qty"]),
        price=float(payload["price"]),
        fee_brl=float(payload["fee_brl"]),
        pnl_brl=float(payload["pnl_brl"]),
        reason=str(payload["reason"]),
        equity_after=float(payload["equity_after"]),
    )
