# GEO_TRADE

<p align="center">
  <strong>Engenharia de Dados Financeiros · Pesquisa Quantitativa</strong><br/>
  Base modular para ingestão confiável de dados de mercado, pesquisas reproduzíveis e validação sistemática de estratégias.
</p>

<p align="center">
  <img src="docs/assets/geo-trade-architecture.svg" alt="Arquitetura da plataforma GEO_TRADE" width="100%"/>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="MetaTrader 5" src="https://img.shields.io/badge/Origem-MetaTrader%205-2B579A"/>
  <img alt="Dados" src="https://img.shields.io/badge/Dados-OHLCV%20%7C%20H1%20%7C%20M1-00A6A6"/>
  <img alt="Armazenamento" src="https://img.shields.io/badge/Armazenamento-CSV%20%7C%20SQLite-168B70"/>
  <img alt="Licença" src="https://img.shields.io/badge/Licen%C3%A7a-MIT-64748b"/>
</p>

## Visão geral

O GEO_TRADE é um projeto de engenharia em evolução, com foco na ingestão de dados de mercado, qualidade de dados, engenharia de atributos e pesquisa quantitativa. Atualmente, o repositório contém dois fluxos independentes de ingestão a partir do MetaTrader 5:

- **Fluxo de atributos H1:** coleta candles horários, valida registros OHLC, calcula atributos técnicos descritivos e exporta conjuntos de dados em CSV.
- **Fluxo histórico M1:** coleta candles de um minuto para um dia do calendário de Brasília, converte o intervalo solicitado para UTC e persiste candles e metadados dos instrumentos em SQLite.

Os fluxos atendem a necessidades distintas de pesquisa e possuem pontos de entrada e formatos de saída independentes.

> Transparência de escopo: a ingestão via MT5, o cálculo de atributos H1, a exportação CSV e a persistência M1 em SQLite estão implementados. Serviços de API, painéis, testes retrospectivos de estratégias, aprendizado de máquina e execução de ordens em corretoras permanecem no roteiro de evolução.

## Arquitetura da plataforma

| Camada | Responsabilidade | Situação |
|---|---|---|
| Dados de mercado | Terminal MetaTrader 5 | Implementado |
| Ingestão e qualidade | Extração H1/M1, validação OHLC, deduplicação e engenharia de atributos H1 | Implementação inicial |
| Armazenamento e consumo | Exportações CSV e persistência SQLite | Implementado |
| Pesquisa quantitativa e operação | Testes retrospectivos, validação de modelos, API, painel e observabilidade | No roteiro |

Consulte [as notas de arquitetura](docs/architecture.md) e [o diagrama em SVG](docs/assets/geo-trade-architecture.svg).

## Estrutura do repositório

```text
GEO_TRADE/
├── data/
│   └── exports/                       # Arquivos gerados (ignorados pelo Git)
├── docs/
│   ├── architecture.md
│   └── assets/
│       └── geo-trade-architecture.svg
├── src/
│   └── ingestion/
│       ├── market_ingestion.py        # H1 -> atributos -> CSV
│       └── trade2_geo_trade_v2.py     # M1 -> SQLite
├── tests/
│   └── test_features.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Fluxo H1: atributos e CSV

O ponto de entrada H1 é `src.ingestion.market_ingestion`.

1. Inicializa o terminal local do MetaTrader 5 e verifica a disponibilidade da conta.
2. Resolve os símbolos solicitados ou lista os símbolos disponíveis no terminal.
3. Recupera candles H1 com uma janela histórica adicional para aquecimento dos cálculos.
4. Valida colunas obrigatórias, timestamps finitos e representáveis, valores de mercado não booleanos e consistência OHLC; elimina candles duplicados idênticos e rejeita candles conflitantes no mesmo instante.
5. Ordena os candles cronologicamente antes de calcular anatomia dos candles, retornos, médias móveis, RSI, ATR, MACD, bandas de Bollinger e atributos temporais.
6. Filtra os registros para o dia UTC solicitado.
7. Elimina duplicidades por símbolo, período e timestamp e exporta um CSV consolidado.

Exemplos:

```powershell
python -m src.ingestion.market_ingestion
python -m src.ingestion.market_ingestion --date 2026-08-21
python -m src.ingestion.market_ingestion --date 2026-08-21 --symbols EURUSD GBPUSD USDJPY
```

Os indicadores são atributos descritivos, não sinais de negociação nem evidências de desempenho preditivo. O último candle H1 pode ainda estar em formação.

## Fluxo M1: candles históricos e SQLite

O ponto de entrada M1 é `src/ingestion/trade2_geo_trade_v2.py`. Ele armazena campos brutos de candles de um minuto no padrão OHLCV e metadados dos instrumentos; não calcula indicadores técnicos.

Comportamentos principais:

- Interpreta `--date` como uma data do calendário de Brasília (UTC−03:00); por padrão, processa o dia anterior em Brasília.
- Converte os limites do dia local para UTC e aplica um intervalo semiaberto: `[início, fim)`.
- Armazena timestamps em UTC e em horário de Brasília para cada candle.
- Valida cada candle M1 antes da persistência: preços finitos e positivos, limites OHLC coerentes e campos de volume/spread inteiros e não negativos; valores booleanos e registros inválidos são rejeitados antes da gravação no SQLite.
- Usa uma chave única em `(symbol, timeframe, timestamp_utc)` e `INSERT OR IGNORE` para tornar importações repetidas idempotentes.
- Atualiza metadados dos instrumentos sem substituir o registro principal.
- Informa instrumentos processados, candles encontrados e inseridos, erros e totais do banco; registros de mercado rejeitados podem ser inspecionados na saída de cada símbolo.
- Pode abrir opcionalmente o DB Browser for SQLite após a execução.

Exemplos (PowerShell):

```powershell
python .\src\ingestion\trade2_geo_trade_v2.py
python .\src\ingestion\trade2_geo_trade_v2.py --date 2026-08-21
python .\src\ingestion\trade2_geo_trade_v2.py --symbols EURUSD GBPUSD
python .\src\ingestion\trade2_geo_trade_v2.py --no-open-db
```

Argumentos opcionais:

- `--date AAAA-MM-DD`: data do calendário de Brasília a ser extraída.
- `--symbols`: um ou mais símbolos de instrumentos do MT5; sem esse argumento, o script lista os símbolos do terminal.
- `--terminal-path`: caminho para `terminal64.exe`.
- `--db-path`: destino do banco SQLite (padrão: `~/Downloads/geo_trade_completo.db`).
- `--no-open-db`: ignora a abertura opcional do DB Browser.

O script M1 exige os pacotes Python `MetaTrader5` e `colorama`. O terminal precisa estar instalado, em execução ou disponível para inicialização no caminho configurado, e autenticado com acesso ao histórico de mercado solicitado.

## Requisitos

- Windows com o terminal desktop MetaTrader 5 instalado.
- Conta válida e autenticada no terminal.
- Python 3.10 ou superior.
- Dependências listadas em `requirements.txt`.

## Configuração (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se a ativação de scripts estiver restrita, invoque diretamente o interpretador do ambiente virtual.

## Testes

```powershell
python -m pytest
```

Os testes automatizados cobrem o cálculo cronológico de atributos, os controles de qualidade do esquema/timestamps/duplicidades H1, a validação de tipos e valores OHLCV M1, a idempotência do SQLite e os limites de datas entre Brasília e UTC. A extração M1 em ambiente real ainda depende de um terminal MT5 autenticado localmente e deve ser testada nesse ambiente.

## Princípios de engenharia

- Timestamps UTC explícitos e conversão de fuso horário documentada.
- Histórico adicional antes do cálculo de indicadores móveis.
- Disciplina temporal e validação cronológica para futuros trabalhos com aprendizado de máquina.
- Verificações de qualidade de dados, identificadores determinísticos e exportações reproduzíveis.
- Persistência idempotente para importações M1 repetidas.
- Credenciais e dados de mercado gerados excluídos do controle de versão.
- Nenhuma alegação de rentabilidade sem evidências fora da amostra e custos realistas.

## Roteiro de evolução

- [x] Ingestão inicial MT5 H1 e exportação CSV.
- [x] Validação OHLC e implementação inicial de atributos técnicos.
- [x] Ingestão histórica M1 e persistência SQLite.
- [x] Documentação do repositório e diagrama de arquitetura.
- [ ] Teste automatizado de integração com um terminal MT5 ativo.
- [ ] Registro estruturado, metadados de execução e pontos de controle da ingestão.
- [ ] Migrações de banco de dados e estratégia de retenção.
- [ ] API e painel analítico.
- [ ] Testes retrospectivos com taxas, spread, derrapagem e avaliação progressiva no tempo.
- [ ] Experimentos de aprendizado de máquina com controles contra vazamento de dados, registro de modelos e monitoramento de deriva.


## Contrato de atributos H1

As janelas de aquecimento, fórmulas dos indicadores, regras de validação e convenções temporais estão descritas no [contrato de atributos H1](docs/h1-feature-contract.md).

## Segurança

Nunca envie ao repositório credenciais de corretoras, senhas, chaves de API, arquivos `.env`, diretórios de dados do terminal, identificadores de contas ou conjuntos de dados privados brutos. Utilize dados públicos de exemplo em demonstrações.

## Aviso

O GEO_TRADE é um projeto de engenharia de software e pesquisa quantitativa. Não fornece aconselhamento de investimento e atualmente não implementa execução de ordens em tempo real.
