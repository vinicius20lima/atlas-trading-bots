"""Text reports for paper state and backtests."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from atlas import __version__
from atlas.clock import MANAUS
from atlas.config import Settings
from atlas.engine.backtest import BacktestResult
from atlas.engine.metrics import summarize
from atlas.engine.paper import PaperBook
from atlas.models import Fill

FEE_ASSUMPTION = (
    "Taxa simulada de 0,10% taker por lado: tabela pública da Binance para usuário "
    "regular (maker/taker 0,100%/0,100%, conferida em nov/2026 em "
    "https://www.binance.com/en/fee/trading). O desconto de 25% pagando com BNB "
    "(0,075%) não entra. A execução simulada é taker porque compra e vende a "
    "mercado no open seguinte. Configurável por ATLAS_TAKER_FEE ou --fee."
)


def brl(amount: float) -> str:
    return f"R$ {amount:,.2f}"


def render_paper(book: PaperBook, now: datetime, started: bool) -> str:
    equity = book.equity()
    pnl = equity - book.starting_balance
    ret = (equity / book.starting_balance - 1.0) * 100.0 if book.starting_balance else 0.0
    unrealized = equity - book.starting_balance - book.realized_pnl
    fills = [_fill(item) for item in book.fills]
    stats = summarize(fills)
    local = now.astimezone(MANAUS)
    lines = [
        "=== Atlas paper (simulado, sem dinheiro real) ===",
        f"Versão:            {__version__}",
        f"Quando:            {local.isoformat()} ({MANAUS.key})",
        f"Fonte:             {book.source if started else '(não iniciado)'}",
        f"Estratégia:        {book.strategy} ({book.interval})",
        f"Caixa:             {brl(book.cash)}",
        f"Equity:            {brl(equity)}",
        f"Inicial:           {brl(book.starting_balance)}",
        f"P&L:               {brl(pnl)} ({ret:.2f}%)",
        f"P&L realizado:     {brl(book.realized_pnl)}",
        f"P&L não realizado: {brl(unrealized)}",
        f"Max drawdown:      {book.max_drawdown_pct * 100:.2f}%",
        (
            f"Dia {book.day or '-'}: equity inicial {brl(book.day_start_equity)} "
            f"| halted={book.halted}"
        ),
        f"Taxa taker:        {book.taker_fee * 100:.2f}% por lado",
        "",
        "Posições abertas:",
    ]
    if not book.positions:
        lines.append("  (nenhuma)")
    else:
        for pair, raw in book.positions.items():
            mark = book.last_marks.get(pair)
            qty = float(raw["qty"])
            entry = float(raw["entry_price"])
            upnl = None
            if mark is not None:
                upnl = qty * mark - float(raw["entry_notional"]) - float(raw["entry_fee"])
            mark_s = brl(mark) if mark is not None else "n/a"
            upnl_s = brl(upnl) if upnl is not None else "n/a"
            lines.append(
                f"  {pair}: qty={qty:.8f} entry={brl(entry)} mark={mark_s} "
                f"stop={brl(float(raw['stop']))} take={brl(float(raw['take']))} "
                f"uPnL={upnl_s} desde {raw['entry_time']}"
            )
    lines.extend(
        [
            "",
            "Resumo dos trades:",
            (
                f"  fills={stats.fills}  round_trips={stats.round_trips}  "
                f"wins={stats.wins}  losses={stats.losses}  "
                f"win_rate={stats.win_rate_pct:.2f}%  fees={brl(stats.fees)}"
            ),
        ]
    )
    if not fills:
        lines.append("  (sem trades de paper ainda)")
    else:
        lines.append("  últimos 10 fills:")
        for fill in fills[-10:]:
            lines.append(
                f"    {fill.time.isoformat()} {fill.side:4} {fill.pair} "
                f"qty={fill.qty:.8f} @ {brl(fill.price)} "
                f"pnl={brl(fill.pnl_brl)} [{fill.reason}] "
                f"equity={brl(fill.equity_after)}"
            )
    if not started:
        lines.extend(["", "Nenhum ciclo de paper foi gravado ainda. Rode: python -m atlas paper"])
    return "\n".join(lines)


def render_backtest(result: BacktestResult) -> str:
    stats = result.stats
    lines = [
        f"--- {result.strategy} ({result.interval}) ---",
        f"Candles na janela: {result.bars} (soma dos símbolos)",
        f"Equity final:      {brl(result.ending_equity)}",
        (
            f"P&L:               {brl(result.ending_equity - result.starting_balance)} "
            f"({result.return_pct:.2f}%)"
        ),
        f"P&L realizado:     {brl(result.realized_pnl)}",
        f"Max drawdown:      {result.max_drawdown_pct * 100:.2f}%",
        f"Posições abertas:  {result.open_positions}",
        (
            f"Trades:            fills={stats.fills}  round_trips={stats.round_trips}  "
            f"wins={stats.wins}  losses={stats.losses}  win_rate={stats.win_rate_pct:.2f}%"
        ),
        f"Fees:              {brl(result.fees_paid)}",
    ]
    if result.first_bar and result.last_bar:
        lines.insert(
            1, f"Dados:             {result.first_bar.isoformat()} → {result.last_bar.isoformat()}"
        )
    if stats.exit_reasons:
        rendered = ", ".join(f"{name}={count}" for name, count in stats.exit_reasons)
        lines.append(f"Saídas:            {rendered}")
    if result.rejections:
        rendered = ", ".join(f"{name}={count}" for name, count in result.rejections)
        lines.append(f"Entradas recusadas: {rendered}")
    if stats.round_trips < 5:
        lines.append(
            "Amostra:           menos de 5 operações encerradas; não dá para falar em vantagem."
        )
    return "\n".join(lines)


def render_comparison(results: list[BacktestResult], recent_days: int = 30) -> str:
    lines = ["--- comparação ---"]
    for result in results:
        lines.append(
            f"{result.strategy}: retorno {result.return_pct:.2f}% | "
            f"trades {result.stats.round_trips} | "
            f"win {result.stats.win_rate_pct:.2f}% | "
            f"max DD {result.max_drawdown_pct * 100:.2f}% | "
            f"fees {brl(result.fees_paid)}"
        )
    if len(results) >= 2:
        winner = max(results, key=lambda item: item.ending_equity)
        lines.append(f"Maior equity final nesta janela: {winner.strategy}.")
    lines.append(
        "Parâmetros escolhidos antes da amostra, sem otimização. "
        "Um resultado melhor aqui não é evidência de lucro futuro."
    )
    if any(result.stats.round_trips < 5 for result in results):
        lines.append("Pelo menos uma estratégia fechou menos de 5 trades nesta janela.")
    del recent_days
    return "\n".join(lines)


def render_header(settings: Settings, days: int, end: datetime, symbols: tuple[str, ...]) -> str:
    start = end - timedelta(days=days)
    return "\n".join(
        [
            f"=== Atlas backtest v{__version__} (simulado, sem dinheiro real) ===",
            f"Janela pedida:     {start.isoformat()} → {end.isoformat()} ({days} dias)",
            f"Símbolos:          {', '.join(symbols)}",
            (
                f"Saldo inicial:     {brl(settings.starting_balance)} "
                "por estratégia (livros separados)"
            ),
            f"Taxa:              {settings.taker_fee * 100:.2f}% taker por lado",
            "Execução:          sinal no candle fechado, fill no open seguinte; "
            "stop antes do take se os dois ocorrerem no mesmo candle",
            f"Limite diário:     -{settings.daily_loss_cap_pct * 100:.0f}% em {settings.timezone} "
            "trava novas entradas até o dia seguinte",
            "Posição:           no máximo "
            f"{settings.max_position_pct * 100:.0f}% da equity por ativo, só comprado",
            FEE_ASSUMPTION,
            "",
        ]
    )


def rejection_counts(pairs: list[tuple[datetime, str, str]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(reason for _, _, reason in pairs).items()))


def _fill(payload: dict[str, object]) -> Fill:
    from atlas.clock import parse_time

    side = str(payload["side"])
    if side not in {"BUY", "SELL"}:
        side = "BUY"
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
