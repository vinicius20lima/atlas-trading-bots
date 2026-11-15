# Atlas Trading Bots

Sistema multiagente de trading de cripto em reais. A versão **0.1.0** só simula: backtest e paper trading. Não envia ordem para exchange nenhuma.

**Não há garantia de lucro.** Isto não é recomendação de investimento. Cripto pode ir a zero. Resultado passado, inclusive o desta página, não diz o que vai acontecer depois. Você pode perder todo o capital que um dia decidir arriscar.

## O que a v0.1 faz

- Baixa candles públicos de BTCBRL, ETHBRL e SOLBRL na Binance.
- Compara duas estratégias compradas (sem alavancagem e sem venda a descoberto).
- Aplica risco fixo: no máximo 20% da equity por posição, stop, alvo e um teto de perda diária.
- Grava um book de paper em `state/` (pasta ignorada pelo git).
- Recusa o comando `live`, com ou sem a flag reservada para o futuro.

A Binance é a fonte primária. A API pública do Mercado Bitcoin foi bloqueada por Cloudflare a partir do ambiente em que este repositório nasceu; o adaptador existe e explica isso, sem tentar furar o bloqueio. Foxbit e o kline da GMGN também são stubs. Leitura on-chain da GMGN fica no cliente de `atlas.exec.gmgn`, desligada sem `GMGN_API_KEY`, e qualquer swap é recusado.

## Instalação

Python 3.11 ou mais novo.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

O arquivo `.env` é opcional. Klines públicos não precisam de chave. Não commite `.env`, `*.pem`, `keys/`, `state/` nem `logs/`.

| Variável | Uso na v0.1 |
| --- | --- |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Só `python -m atlas account` (leitura). Sem elas, a conta é pulada. |
| `BINANCE_DATA_BASE_URL` | Padrão `https://data-api.binance.vision`. O host `api.binance.com` responde HTTP 451 em algumas regiões. |
| `BINANCE_API_BASE_URL` | Padrão `https://api.binance.com`, apenas para a conta assinada. |
| `GMGN_API_KEY` | Reservada. Sem ela, smart money fica neutro. |
| `ATLAS_TAKER_FEE` | Taxa taker por lado. Vazio = `0.001` (0,10%). |
| `ATLAS_STARTING_BALANCE` | Saldo virtual inicial. Vazio = `500`. |
| `ATLAS_STATE_DIR` | Pasta do paper. Vazio = `state`. |

Chaves de Foxbit, Mercado Bitcoin, Telegram, Solana e OpenTrade estão no exemplo porque versões futuras podem usá-las. A v0.1 não opera com elas.

## Comandos

```bash
python -m atlas backtest
python -m atlas backtest --strategy ema_crossover --days 30
python -m atlas paper
python -m atlas paper --strategy ema_crossover --reset
python -m atlas report
python -m atlas account
python -m atlas live
```

`backtest` compara `ema_crossover` e `atr_trend` nos últimos 90 dias (mude com `--days`). Cada estratégia começa do zero, com o mesmo saldo. O padrão é R$ 500.

`paper` roda **um** ciclo e sai. O primeiro ciclo só arma o cursor no último candle fechado: ele não reimporta o passado. O ciclo seguinte pode comprar no open do candle novo. `--watch` repete a cada `--poll` segundos (padrão 60). O padrão da estratégia no paper é `atr_trend`, porque opera menos que o protótipo de 15m. Isso não significa que ela seja lucrativa.

`report` lê `state/state.json` e `state/trades.csv`.

`live` termina com código 2. `--enable-live` e `ATLAS_LIVE_CONFIRM=YES` não mudam isso na v0.1: não existe cliente de ordem.

## Regras de execução

O sinal nasce quando o candle **fecha**. A compra ou a venda simulada acontece no **open do candle seguinte**. Se, nessa barra, o stop e o alvo são os dois atingidos, o stop ganha. Um gap que abre além do stop vende no open (preço pior). Um gap que abre além do alvo vende no open (preço melhor).

Não há fila de slippage nem impacto de mercado. A equity marcada de uma posição ainda aberta não reserva a taxa de saída; essa taxa entra quando a posição fecha. O drawdown usa a equity nos fills e no fechamento de cada barra, não o pior tick dentro da barra.

O teto diário usa o calendário de **America/Manaus** (UTC−4, sem horário de verão). Se a equity do dia cai 5% ou mais em relação à equity do começo daquele dia, novas compras ficam bloqueadas até o dia seguinte. Stops e alvos continuam valendo.

Tamanho: no máximo 20% da equity de notional por ativo, limitado também pelo caixa e por um notional mínimo simulado de R$ 10 (filtro público `minNotional` de BTCBRL observado em 15 de novembro de 2026). A v0.1 não arredonda para o step da exchange.

### Taxa

0,10% taker **por lado**. É a tabela pública da Binance para usuário regular de spot (maker 0,100% / taker 0,100%), vista em novembro de 2026 em [binance.com/en/fee/trading](https://www.binance.com/en/fee/trading). Quem paga a taxa em BNB paga 0,075%; **isso não está na simulação**. A ordem simulada é tratada como taker porque entra e sai a mercado. Dá para trocar com `--fee` ou `ATLAS_TAKER_FEE`. Uma ida e volta custa cerca de 0,20% do notional antes de qualquer movimento de preço.

## Estratégias

Nenhuma das duas foi otimizada nesta amostra. Procurar parâmetros melhores está no roadmap, com walk-forward, para não escolher o número que só ficou bonito no passado.

### `ema_crossover` (protótipo, 15m)

Compra quando a EMA 9 cruza acima da EMA 21, o fechamento está acima da EMA 50 e o RSI(14) está entre 30 e 70, os dois inclusos. Vende no cruzamento inverso. Stop −3% e alvo +5% vêm do gerenciador de risco, não da estratégia.

Esse é o primeiro protótipo do dono do repositório. Numa leitura anterior, fora deste código, os últimos 30 dias tinham ficado perto de −27% com uns 10% de acerto, sobretudo por whipsaw e taxa. A corrida abaixo mede de novo, com as regras escritas aqui. Não é o mesmo código daquela leitura, então o número não precisa repetir −27%.

### `atr_trend` (4h)

Compra quando a EMA 20 cruza acima da EMA 50, o fechamento está acima da EMA 50 e o ATR(14) dividido pelo fechamento está entre 1,5% e 12%. A faixa existe para pular mercado morto (cruzamento que mal paga a taxa) e barra explosiva. O stop fica a 2 ATR e o alvo a 4 ATR do preço de entrada, no lugar dos −3% / +5%. A saída de sinal é o cruzamento inverso.

A ideia é operar menos. Em 30 dias um cruzamento de 4h pode quase não acontecer. Poucos trades não provam vantagem.

## Resultados de referência

Corrida em 15 de novembro de 2026 contra `https://data-api.binance.vision`, fim fixo `2026-11-15T18:00:00Z`, saldo **R$ 500 por estratégia**, livros separados, BTCBRL + ETHBRL + SOLBRL, taxa 0,10% taker por lado. Os parâmetros foram escolhidos antes de olhar esta saída. Não houve busca de parâmetro depois do resultado.

```bash
python -m atlas backtest --days 30 --balance 500 --end 2026-11-15T18:00:00+00:00
python -m atlas backtest --days 90 --balance 500 --end 2026-11-15T18:00:00+00:00
python -m atlas backtest --days 180 --balance 500 --end 2026-11-15T18:00:00+00:00
```

| Janela | Estratégia | Retorno | Trades | Acerto | Max DD | Fees |
| --- | --- | --- | --- | --- | --- | --- |
| 30d (16 out–15 nov) | ema_crossover | −8,10% | 145 | 21,38% | 9,29% | R$ 28,41 |
| 30d | atr_trend | −2,30% | 3 | 0% | 3,21% | R$ 0,59 |
| 90d (17 ago–15 nov) | ema_crossover | −8,23% | 438 | 26,94% | 13,96% | R$ 88,72 |
| 90d | atr_trend | −1,17% | 7 | 28,57% | 3,19% | R$ 1,40 |
| 180d (19 mai–15 nov) | ema_crossover | −36,37% | 965 | 23,21% | 36,38% | R$ 147,33 |
| 180d | atr_trend | +3,12% | 12 | 41,67% | 3,19% | R$ 2,50 |

Uma leitura anterior do protótipo, fora deste código, tinha ficado perto de −27% com cerca de 10% de acerto em 30 dias. **Esta** implementação, nesta janela de 30 dias, deu −8,10% com 21,38% de acerto. O número não bate, e não vou fingir que bate. O defeito é o mesmo: em 30 dias, 142 das 145 saídas foram o cruzamento inverso e só 3 atingiram +5%. Dos R$ 40,48 perdidos, R$ 28,41 foram taxa. Em 180 dias o baseline perde 36%, com 938 das 965 saídas no cruzamento inverso.

`atr_trend` opera pouco e sangra menos taxa (R$ 2,50 contra R$ 147,33 em 180 dias). Nos 30 e nos 90 dias ela também perdeu. Nos 180 dias ficou +3,12% em 12 trades, com drawdown de 3,19%. Doze trades numa janela só não são uma borda. O trecho mais recente (90 dias) continua negativo. Nada disso autoriza dinheiro real.

## Papéis

O orquestrador pede um sinal à estratégia, anota o que os outros papéis têm a dizer e só então chama o risco e o portão.

| Módulo | Estado na v0.1 |
| --- | --- |
| `atlas.signals.smart_money` | Neutro sem `GMGN_API_KEY`. Não transforma lista de carteiras em direção de BTCBRL. Um viés bearish com confiança ≥ 0,7 vetaria compra; o cliente atual não fabrica esse viés. |
| `atlas.exec.gmgn` | GET em `/v1/market/rank`, `/v1/token/info` e `/v1/user/smartmoney` quando há chave. `swap()` sempre levanta erro. |
| `atlas.debate` | Adaptador opcional para TauricResearch/TradingAgents. Desligado. Sem pacote instalado, a opinião é neutra. |
| `atlas.solana_kit` | Lugar do sendaifun/solana-agent-kit. Sem chave, sem transação. |
| `atlas.opentrade` | Portão local no espírito de 0xsyncroot/opentrade. Paper e backtest passam; `live` não passa. |
| `atlas.orchestrator` | Junta os papéis e decide. |

## Testes

```bash
pytest
ruff check src tests
ruff format --check src tests
```

Os testes usam candles fabricados. CI roda lint e pytest em Python 3.11 e 3.12. Nenhum job de teste fala com a Binance.

## Versões

Cada melhoria que muda o comportamento sai como uma **minor** (`0.2.0`, `0.3.0`, …), com entrada no `CHANGELOG.md`, teste e nota no README. Correção que não muda regra de trade pode ser patch. Trading real, se um dia existir, é outra conversa: só depois de paper com resultado positivo numa janela combinada antes, e mesmo assim com confirmação humana. Veja `docs/ROADMAP.md` e `CONTRIBUTING.md`.

## Licença

Ainda não há arquivo de licença. Até existir um, considere o código reservado ao autor do repositório.
