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
