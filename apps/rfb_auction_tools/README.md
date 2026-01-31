# RFB Auction Lots
Serviço responsável por consultar e expor os lotes de leilões da Receita Federal.

## Escopo
- Rastrea editais e catálogos oficiais.
- Normaliza os lotes em um formato único para os demais serviços.
- Mantém histórico simples para análises de apetite de mercado.

## Futuras evoluções
- Enriquecer os lotes com metadados vindos de `shared`.
- Publicar webhooks para disparar análises de preço automaticamente.

## Desenvolvimento atual

### Endpoints públicos RFB
- Available Auctions: retorna N avaliable auctions no formato de `apps/rfb_auction_tools/sample_avaliable_auctions.json`
```http
GET http://www25.receita.fazenda.gov.br/sle-sociedade/api/editais-disponiveis
```
- Auction Details: retorna N lot de cada auction no formato de `apps/rfb_auction_tools/sample_auctions_details.json`
```http
@edle = 800100/10/2025
GET http://www25.receita.fazenda.gov.br/sle-sociedade/api/edital/{{edle}}

```
- Lot details: retorna N items de cada lot avaliable auctions no formato de `apps/rfb_auction_tools/sample_lot_details.json`
```http
@edle = 800100/10/2025
@loleNrSq = 1
GET http://www25.receita.fazenda.gov.br/sle-sociedade/api/lote/{{edle}}/{{loleNrSq}}
```

### Estrutura de Entidades

A hierarquia de dados segue: **Auction** (1) → **Lot** (N) → **Item** (N).

As entidades do domínio estão implementadas em `shared/domain/auction/` com arquitetura hexagonal:

- **`entities/auction.py`**: Edital/leilão da RFB (raiz da agregação)
- **`entities/lot.py`**: Lote dentro de um leilão
- **`entities/item.py`**: Mercadoria dentro de um lote
- **`value_objects.py`**: `LotImage` (imagem de lote) e `AvisoErrata` (avisos/erratas)

Para definições completas com todos os campos, tipos e documentação, consulte os arquivos fonte acima.

### Mapeamento de Situações (códigos observados)

| Código | Provável Significado |
|--------|---------------------|
| 2      | Aberto para propostas (futuro) |
| 11     | Encerrado/Finalizado |
| 12     | Em análise/Homologação |
| 14     | Suspenso/Cancelado |
| 15     | Encerrado com resultado |

### Diagrama de Relacionamentos

```
┌─────────────────────────────────────────────────────────────────┐
│                         AUCTION                                 │
│  (edital/leilão)                                                │
├─────────────────────────────────────────────────────────────────┤
│  edital: "0800100/000010/2025"                                  │
│  edle: "800100/10/2025"                                         │
│  cidade: "SÃO PAULO"                                            │
│  data_abertura_lances: "2026-01-08 10:00"                       │
│  total_lotes: 14                                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 1:N
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                           LOT                                   │
│  (lote)                                                         │
├─────────────────────────────────────────────────────────────────┤
│  id: 1                                                          │
│  numero: 1                                                      │
│  tipo: "MOTOCICLETA/ACESSÓRIO"                                  │
│  valor_minimo: 170000  (R$ 170.000,00)                          │
│  permite_pf: false                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 1:N
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                          ITEM                                   │
│  (mercadoria)                                                   │
├─────────────────────────────────────────────────────────────────┤
│  recinto_armazenador: "SBC LACHMANN"                            │
│  quantidade: 50                                                 │
│  unidade_medida: "un"                                           │
│  descricao: "[DI 20/1038859-2] MINI MOTO ELETRICA..."           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Sincronização

O módulo `sync.py` sincroniza dados coletados da API RFB com o banco de dados PostgreSQL.

### Características principais

- **Detecção de mudanças**: Hash SHA256 por entidade
- **Hash scope**: Apenas campos diretos (Lots têm hash próprio)
- **Sync de Lots**: **Sempre verificar**, mesmo se Auction não mudou
- **Histórico**: Tabela `auction_audit` separada
- **Erros**: Campos `error_status`/`error_message` + tabela `sync_errors`
- **Remoção**: Soft delete (`is_active`)
- **Batch tracking**: UUID `sync_batch_id` para rastreamento

### Fluxograma

```
┌─────────────────────────────────────────────────────────────────┐
│                    sync_all() iniciado                          │
│                    (gera batch_id UUID)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│        Coletar auctions disponíveis da API RFB                  │
│        collector.fetch_available_auctions()                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│        Comparar com auctions ativos no banco                    │
│        storage.get_active_auction_edles()                       │
│                                                                 │
│        new_edles = rfb - stored                                 │
│        existing_edles = rfb ∩ stored                            │
│        removed_edles = stored - rfb                             │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌───────────┐       ┌───────────┐       ┌───────────┐
    │   NOVOS   │       │ EXISTENTES│       │ REMOVIDOS │
    └───────────┘       └───────────┘       └───────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌───────────────────┐  ┌─────────────────┐
│ Para cada novo: │  │ Para cada um:     │  │ soft_delete     │
│                 │  │                   │  │ (is_active=F)   │
│ 1. fetch_details│  │ 1. fetch_details  │  │                 │
│ 2. calc hash    │  │ 2. calc hash      │  │ Registra audit  │
│ 3. INSERT       │  │ 3. hash diferente?│  │ action='DELETE' │
│ 4. audit CREATE │  │    SIM: UPDATE    │  │                 │
│                 │  │    audit UPDATE   │  │                 │
│ 5. sync_lots    │  │                   │  │                 │
│    (novos)      │  │ 4. SEMPRE         │  │                 │
│                 │  │    sync_lots ◄────┼──┼── IMPORTANTE!   │
└─────────────────┘  └───────────────────┘  └─────────────────┘
          │                   │
          └─────────┬─────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      sync_lots()                                │
│                                                                 │
│   Para cada lot, compara rfb_id:                                │
│   - Novo: INSERT + audit + sync_items                           │
│   - Existente: compara hash → UPDATE se diferente               │
│                SEMPRE sync_items                                │
│   - Removido: soft_delete                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      sync_items()                               │
│                                                                 │
│   Para cada item (replace strategy):                            │
│   - DELETE todos os items existentes do lot                     │
│   - INSERT todos os items novos                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│   Retorna SyncResult com contadores:                            │
│   - auctions: created, updated, deleted, errors                 │
│   - lots: created, updated, deleted, errors                     │
│   - items: synced                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Tratamento de Erros

Quando `LotUnavailableError` ou outras exceções ocorrem:

1. Atualiza `error_status` e `error_message` na entidade
2. Registra em `sync_errors` com stack_trace
3. Registra audit com `action='ERROR'`
4. Continua processando outras entidades

### Exemplo de uso

```python
from config.rfb_auction_tools.settings import get_settings
from apps.rfb_auction_tools.collectors import RFBAuctionCollector
from apps.rfb_auction_tools.sync import RFBAuctionSync
from shared.adapters.outbound.postgres_auction_storage import PostgresAuctionStorage

settings = get_settings()
collector = RFBAuctionCollector(settings)
storage = PostgresAuctionStorage()

sync = RFBAuctionSync(collector, storage)
result = sync.sync_all(fetch_lot_details=True)

print(f"Batch: {result.batch_id}")
print(f"Auctions: {result.auctions}")
print(f"Lots: {result.lots}")
print(f"Items: {result.items}")
```
