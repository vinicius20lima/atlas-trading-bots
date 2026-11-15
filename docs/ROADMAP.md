# Roadmap

A 0.1.0 é um esqueleto testável: dados públicos da Binance, duas estratégias, risco, backtest e paper. Não é um sistema lucrativo e não opera de verdade.

As versões abaixo são a ordem pretendida, não uma data.

## 0.2 — Parâmetros com walk-forward

- Busca de parâmetros fora da amostra que se quer avaliar.
- Walk-forward (janela de treino, janela de teste, andar para a frente) antes de trocar EMA, ATR ou RSI.
- Registrar a escolha no changelog. Não substituir o número da 0.1 por um número otimizado em silêncio.
- Custo de taxa e o teto diário continuam dentro do teste, não só no relatório final.

## 0.3 — Mais estratégias

- Outras regras de baixa frequência, ainda só compradas em BRL.
- Critério mínimo de amostra (trades e pares) antes de uma estratégia virar padrão do `paper`.
- Manter `ema_crossover` como baseline, mesmo que perca, para ter com o que comparar.

## 0.4 — GMGN com chave do dono

- Ligar leitura real (`market rank`, token, smart money) quando existir `GMGN_API_KEY`.
- Mapear fluxo para um viés só com uma regra escrita antes de olhar o resultado.
- Continuar sem swap e sem ordem. Klines de BRL seguem na Binance enquanto o Mercado Bitcoin estiver atrás de Cloudflare. Sem bypass.

## 0.5 — Alertas no Telegram

- Aviso de fill de paper, de halt diário e de erro de dados.
- `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` saem do estado “reservado”.
- Alerta não é ordem.

## 1.0 — Trading real, só se o paper justificar

Condições, todas juntas:

- Uma janela de paper definida **antes** de medir (pares, estratégia, saldo, taxa).
- Resultado líquido positivo depois da taxa, com drawdown que caiba no teto já codificado.
- Revisão humana. Flag `--enable-live` e `ATLAS_LIVE_CONFIRM=YES` passam a ser necessárias e deixam de ser ignoradas.
- O portão (`opentrade` ou o projeto upstream) continua podendo vetar.
- Primeiro um par, tamanho mínimo, sem alavancagem.

Se o paper não for positivo, a 1.0 não sai. Perder menos que o baseline não autoriza dinheiro real.

## Fora de escopo até lá

- Contornar Cloudflare do Mercado Bitcoin.
- Custódia de seed ou envio pela solana-agent-kit.
- Debate com LLM como dependência obrigatória (TauricResearch/TradingAgents continua opcional).
- Otimizar a 0.1 até a tabela do README ficar verde.
