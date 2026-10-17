# Golpe do Pix - Projeto Base

Coleção de serviços que ajudam a analisar oportunidades de venda e tributação envolvendo Mercado Livre e Receita Federal.

Disclaimer: o nome "golpe do pix" é só uma brincadeira. Não tem nada de errado sendo feito aqui

## Apps
- `apps/max_bid`: calcula o maior lance que ainda mantém a margem desejada.
- `apps/ml_prices`: analisa preços do Mercado Livre usando regex, filtros e LLMs.
- `apps/rfb_auction_lots`: lista e normaliza lotes de leilões da Receita Federal.
- `apps/rfb_ncm`: devolve dados tributários por NCM (com fallback configurável).
- `apps/ncm_classifier`: classifica descrições livres no NCM correto via LLMs.

## Pastas de suporte
- `shared/`: portas (interfaces) e adaptadores (implementações) seguindo arquitetura hexagonal, com foco na porta de data-source que abstrai diferentes formas de persistência (filesystem, database, etc).
- `config/`: presets de ambiente e padrões de configuração (@README.md).

## Arquitetura
O projeto segue arquitetura hexagonal, onde a comunicação entre apps ocorre através de portas definidas em `shared/`, permitindo que cada serviço leia e escreva dados sem acoplamento a implementações específicas de persistência.

## .env etiquette
- Centralize variáveis comuns em `config/.env.example` (copie para `.env` e mantenha fora do git via `.env.local`).
- Cada app pode ter `apps/<serviço>/.env.example` apenas para chaves exclusivas; carregue primeiro o arquivo global, depois o específico.
- Para Docker Compose, referencie ambos com `env_file` ou passe via `--env-file config/.env`.
- Nunca comite segredos reais; use placeholders claros e documentados.

### Exemplos
```
# config/.env.example
ML_APP_ID=your-app-id
ML_APP_SECRET=replace-me
DATA_SOURCE_TYPE=database
DATA_DB_CONNECTION_STRING=your-database-connection-string
```

```
# apps/ml_prices/.env.example
ML_PRICES_FEATURE_REGEX=true
ML_PRICES_LLM_PROVIDER=bedrock
```

Cada diretório possui um README curto com o estado atual e próximos passos.

## Test etiquette
Test folder structure should mirror `apps/` up to the first subdirectory level.

**Example**:  
`tests/unit/ml_prices/scrapers/` is the deepest allowed folder nesting.  
Deeper nesting (such as `tests/unit/ml_prices/scrapers/offers/`) is **not permitted**.

Test types should include:
- unit
- integration
- end-to-end
