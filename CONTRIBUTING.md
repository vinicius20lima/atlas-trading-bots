# Como contribuir

O dono do repositório é brasileiro. Documentação em português. Identificadores e comentários de código em inglês.

## Segredos

O repositório é público.

- Não commite `.env`, chave, seed, PEM, `state/` ou `logs/`.
- `.env.example` só tem nomes de variável e valores vazios.
- Log e mensagem de erro não podem imprimir `BINANCE_API_SECRET`, `GMGN_API_KEY` nem conteúdo de PEM.
- Não adicione cliente de ordem “só para testar”. `python -m atlas live` tem de continuar recusando.

## O que entra em cada versão

O projeto usa semver, declarado em `src/atlas/__init__.py`.

- **Patch** (`0.1.x`): correção que não muda sinal, fill, taxa, risco nem formato do `state.json`.
- **Minor** (`0.x.0`): qualquer melhoria de comportamento. Estratégia nova, parâmetro novo, fonte de dados, alerta, mudança de relatório. Uma melhoria, uma minor. Não acumule várias features soltas na mesma versão.
- **Major** (`1.0.0` ou quebra de `state.json` / CLI): só com nota de migração no changelog. Trading com dinheiro real não entra numa minor.

Cada versão publicada atualiza:

1. `src/atlas/__version__`
2. `CHANGELOG.md` (Keep a Changelog), com a data e as premissas que mudaram
3. README, se o comando ou o risco visível mudou
4. Testes. Estratégia, risco e backtest precisam de teste sem rede.

Parâmetro de estratégia não é “ajustado no mesmo PR em que se olha o resultado”. Otimização fica para uma versão própria e tem de ser walk-forward, ou o número só descreve o passado.

## Fluxo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check src tests && ruff format --check src tests
```

O CI faz a mesma checagem em 3.11 e 3.12. Se mexer em UI web no futuro, teste o fluxo no browser; a v0.1 é só CLI.

## Trading real

Não implemente. O roadmap só admite essa discussão depois de um período de paper combinado **antes** da medição e com resultado positivo líquido de taxa. Mesmo então, o comando precisa de flag explícita e de confirmação humana. O portão em `atlas.opentrade` bloqueia `mode="live"` de propósito.
