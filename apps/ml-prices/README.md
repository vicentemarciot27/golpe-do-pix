# ML Prices

ML Prices coleta ofertas e retorna uma análise de preços no Mercado Livre.

O Objeto que este módulo devolve, para todos os fins, será chamado de Offer

## Como funciona
- Usa buscas (incluindo regex) para identificar anúncios relevantes.
- Pode invocar LLMs para confirmar se o produto corresponde ao alvo.
- Remove outliers e aplica filtros configuráveis antes dos cálculos.
- Produz relatórios com médias, dispersões e oportunidades.

## Integrações
- Consome heurísticas de comparação vindas de `shared`.
- Oferece dados refinados para `max-bid` definir lances ótimos.

## Arquitetura (Alto Nível)

Coisa simples:

ML Prices -> Postgres

## Variáveis de Ambiente

As variáveis serão analisadas nesta ordem, sequencialmente. Ou seja, a primeira linha corresponde ao primeiro filtro a ser aplicado, e após isso, os outros

Variável | Descrição
ML_PRICES_PAGES_TO_SCRAPE | Quantas páginas iniciais serão scrapadas
ML_PRICES_MIN_PRICE | Preço míni
ML_PRICES_MAX_PRICE | Preço máximo a ser analisado
ML_PRICES_MAX_OFFERS_TO_RETURN | Quantos itens serão retornados, no máximo
ML_PRICES_WRITE_SEARCH_QUERY_LLM_MODEL | Modelo que irá escrever a query de busca
ML_PRICES_FILTER_LLM_MODEL | Qual modelo de LLM será responsável por filtrar