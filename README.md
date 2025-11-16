# Golpe do Pix - Projeto Base

Coleção de serviços que ajudam a analisar oportunidades de venda e tributação envolvendo Mercado Livre e Receita Federal.

## Apps
- `apps/max-bid`: calcula o maior lance que ainda mantém a margem desejada.
- `apps/ml-prices`: analisa preços do Mercado Livre usando regex, filtros e LLMs.
- `apps/rfb-auction-lots`: lista e normaliza lotes de leilões da Receita Federal.
- `apps/rfb-ncm`: devolve dados tributários por NCM (com fallback configurável).
- `apps/ncm-classifier`: classifica descrições livres no NCM correto via LLMs.

## Pastas de suporte
- `shared/`: contratos, clientes e utilidades compartilhadas.
- `config/`: presets de ambiente e padrões de configuração (@README.md).

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
SHARED_DB_URL=postgres://user:pass@host:5432/ml_shared
```

```
# apps/ml-prices/.env.example
ML_PRICES_FEATURE_REGEX=true
ML_PRICES_LLM_PROVIDER=bedrock
```

Cada diretório possui um README curto com o estado atual e próximos passos.
