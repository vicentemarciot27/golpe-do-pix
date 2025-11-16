# ML Prices

ML Prices coleta ofertas e retorna uma análise de preços no Mercado Livre.

## Como funciona
- Usa buscas (incluindo regex) para identificar anúncios relevantes.
- Pode invocar LLMs para confirmar se o produto corresponde ao alvo.
- Remove outliers e aplica filtros configuráveis antes dos cálculos.
- Produz relatórios com médias, dispersões e oportunidades.

## Integrações
- Consome heurísticas de comparação vindas de `shared`.
- Oferece dados refinados para `max-bid` definir lances ótimos.
