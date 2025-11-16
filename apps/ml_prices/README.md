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
- Oferece dados refinados para `max_bid` definir lances ótimos a partir dos preços médios de um item.
- Utiliza LLMs (ou SLMs no futuro) para criar query de busca e filtrar resultados irrelevantes

## Tecnologia
### Scraping
O scraping será feito via playwright

### Testing
Os testes ocorrerão no diretório tests/, na raíz do projeto, usando pytest

## Arquitetura (Alto Nível)

Coisa simples:

ML Prices -> Postgres

## Variáveis de Ambiente

Copie `config/.env.example` para `config/.env` (ou `.env.local`) e ajuste os valores abaixo conforme necessário.

Variável | Descrição | Padrão
ML_PRICES_PAGES_TO_SCRAPE | Quantas páginas iniciais serão scrapadas | 3
ML_PRICES_HEADLESS | Define se o Playwright roda em modo headless (`true`/`false`) | false
ML_PRICES_PAGE_LOAD_TIMEOUT | Timeout para carregamento de página (segundos) | 40
ML_PRICES_EXPLICIT_WAIT | Timeout para esperas explícitas (segundos) | 20

**Nota**: O termo de busca (`search_term`) não é uma variável de ambiente, pois deve ser passado como parâmetro para cada chamada do scraper.

Os demais filtros continuarão seguindo esta ordem quando forem introduzidos:

Variável | Descrição
ML_PRICES_MIN_PRICE | Preço mínimo a ser analisado
ML_PRICES_MAX_PRICE | Preço máximo a ser analisado
ML_PRICES_MAX_OFFERS_TO_RETURN | Quantos itens serão retornados, no máximo
ML_PRICES_WRITE_SEARCH_QUERY_LLM_MODEL | Modelo que irá escrever a query de busca
ML_PRICES_FILTER_LLM_MODEL | Qual modelo de LLM será responsável por filtrar
