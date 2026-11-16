# Contrato de atributos H1 e validação de mercado

Este documento registra as convenções numéricas e os invariantes do fluxo H1 do GEO_TRADE. Os nomes das colunas e as fórmulas aqui descritas integram o contrato dos dados exportados.

## Janela de aquecimento e recorte temporal

- A ingestão solicita uma janela de aquecimento de 14 dias corridos antes do dia UTC solicitado.
- A janela anterior fornece contexto para indicadores recursivos, inclusive em períodos que atravessam fins de semana sem negociação.
- A exportação final é filtrada novamente para o dia UTC solicitado, sem incluir candles da janela de aquecimento.
- O último candle H1 pode ainda estar em formação; sua presença não deve ser interpretada como candle fechado.

## Validação da entrada

A etapa de validação trabalha sobre uma cópia do DataFrame recebido do provedor e não modifica o objeto original.

- Os rótulos das colunas devem ser únicos; colunas duplicadas são rejeitadas antes do cálculo.
- Os campos OHLC e o timestamp devem ser válidos, finitos e representáveis.
- Registros idênticos no mesmo instante podem ser deduplicados de forma determinística.
- Registros conflitantes para o mesmo símbolo, timeframe e timestamp são rejeitados.
- A saída informa a quantidade de linhas rejeitadas, separadamente da quantidade de linhas aceitas.
- Valores não finitos em métricas derivadas são rejeitados, exceto os valores ausentes previstos nas janelas de aquecimento documentadas abaixo.

## Convenções dos indicadores

As convenções atuais são deliberadamente explícitas. Alterar suavização, janela ou denominador modifica valores históricos e exige versionamento do contrato.

| Atributo | Convenção |
|---|---|
| `sma_5` / `sma_10` | Média móvel simples do fechamento em janelas de 5 e 10 candles |
| `ema_5` / `ema_10` | Média móvel exponencial com `adjust=False` |
| `rsi_14` | Médias móveis simples de 14 variações positivas e negativas do fechamento; não utiliza a suavização de Wilder |
| `atr_14` | Média móvel simples de 14 valores de True Range; não utiliza a suavização de Wilder |
| `macd` | EMA(12) menos EMA(26); `macd_signal` é a EMA(9) do MACD |
| Bandas de Bollinger | Média simples de 20 candles mais/menos duas vezes o desvio-padrão amostral da janela |
| `volatility_10` | Desvio-padrão amostral móvel de 10 retornos simples entre fechamentos |
| `volatility_pct` | `volatility_10` multiplicada por 100 |

Para o RSI, uma janela plana recebe 50; uma janela com ganhos e sem perdas recebe 100. A primeira janela completa de 14 variações surge após a linha inicial necessária ao cálculo das diferenças. Valores ausentes de aquecimento são esperados somente onde a janela móvel ainda não está completa.

## Exportação e isolamento de execuções

Os arquivos H1 incluem microssegundos no nome para reduzir colisões entre execuções iniciadas no mesmo segundo. A exportação deve preservar o conjunto já publicado quando uma nova gravação falhar antes da substituição atômica.

## Contrato temporal do fluxo M1

O fluxo M1 interpreta a data solicitada no fuso IANA `America/Sao_Paulo`, aplicando as regras históricas de horário de verão disponíveis no banco de fusos. Os limites locais são convertidos para UTC e usados como intervalo semiaberto `[início, fim)`. Os timestamps UTC e de Brasília são persistidos separadamente.

A dependência `tzdata` é necessária em ambientes cuja distribuição não forneça uma base IANA de fusos atualizada.

## Encerramento dos recursos

Falhas ao encerrar a sessão MT5 ou fechar a conexão SQLite devem ser refletidas em um código de saída diferente de zero. Uma extração que processou candles, mas não conseguiu liberar um recurso obrigatório, não deve ser reportada como execução plenamente bem-sucedida.
