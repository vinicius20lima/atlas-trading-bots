# Changelog

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Este projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-11-15

### Added

- Pacote `atlas` (Python 3.11+) com CLI `backtest`, `paper`, `report`, `account` e `live`.
- Dados públicos da Binance para BTCBRL, ETHBRL e SOLBRL via `data-api.binance.vision`. Conta assinada é só leitura e opcional.
- Adaptadores stub para Foxbit, Mercado Bitcoin e GMGN no papel de fonte de kline em BRL. Mercado Bitcoin fica de fora porque a API pública foi bloqueada por Cloudflare; não há contorno.
- Estratégia `ema_crossover`: EMA 9/21 no 15m, filtro de tendência EMA 50 e RSI(14) em [30, 70]. Protótipo inicial, sem otimização.
- Estratégia `atr_trend`: cruzamento EMA 20/50 no 4h, filtro de volatilidade e stop/alvo em ATR (2x / 4x).
- Risco: no máximo 20% da equity por posição, stop −3% e alvo +5% (ou distâncias de ATR), teto diário de −5% em America/Manaus.
- Backtest com sinal no candle fechado, execução no open seguinte e stop antes do take quando os dois cabem na mesma barra. Taxa taker simulada de 0,10% por lado.
- Paper trading com saldo virtual padrão de R$ 500, `state/state.json` e `state/trades.csv`. O primeiro ciclo não reimporta o passado.
- Papéis `signals/smart_money`, `exec/gmgn` (leitura), `debate`, `solana_kit`, `opentrade` e `orchestrator`. Swap, envio Solana e trading real recusam.
- Testes pytest sem rede e workflow de CI (ruff + pytest em 3.11 e 3.12).

### Assumptions

- A taxa de 0,10% é a de usuário regular da Binance spot (maker e taker), sem desconto de BNB, conforme a tabela pública em novembro de 2026.
- Não há modelo de slippage além do open seguinte e da regra stop-antes-do-take. A equity de uma posição aberta não desconta a taxa de saída.
- O notional mínimo simulado é R$ 10, visto no filtro `minNotional` de BTCBRL. A v0.1 não arredonda para tick nem step da exchange.
