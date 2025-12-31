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

### Estrutura de Entidades Proposta
A hierarquia de dados, para posterior implementação de entidades em `shared/domain`: segue o fluxo: **Auction** (1) → **Lot** (N) → **Item** (N).

#### Value Objects (objetos de valor imutáveis)
```python
@dataclass(frozen=True)
class LotImage:
    """Imagem associada a um lote."""
    rfb_id: int         # imllNrSq - ID da imagem na RFB
    url: str            # src - URL da imagem em tamanho original
    thumbnail_url: str  # min - URL da miniatura
    width: int          # w
    height: int         # h
    is_featured: bool = False  # destaque
    # Identificação interna
    id: int | None = None      # ID interno (PostgreSQL)
    lot_id: int | None = None  # FK para Lot


@dataclass(frozen=True)
class AvisoErrata:
    """Aviso ou errata publicado para auction/lot."""
    data: datetime      # data - ex: "2025-12-10 07:28"
    codigo_tipo: int    # codigoTipo - 1=Aviso, 2=Errata
    tipo: str           # tipo - "Aviso" ou "Errata"
    texto: str          # texto - conteúdo do aviso
    # Identificação interna
    id: int | None = None           # ID interno (PostgreSQL)
    auction_id: int | None = None   # FK para Auction (se pertence a Auction)
    lot_id: int | None = None       # FK para Lot (se pertence a Lot)
```

#### Entidade: Item

```python
@dataclass
class Item:
    """
    Representa uma mercadoria/produto dentro de um lote.

    Granularidade mais fina - cada item é uma linha de mercadoria
    com quantidade e descrição específicas.
    """
    # Dados RFB
    recinto_armazenador: str   # recintoArmazenador - local físico de armazenamento
    quantidade: int            # quantidade
    unidade_medida: str        # unMedida - ex: "un"
    descricao: str             # descricao - formato típico: "[DI XX/XXXXXXX-X] DESCRIÇÃO..."
    nr_referencia: str | None = None  # nrReferencia - referência interna (opcional)
    # Identificação interna
    id: int | None = None      # ID interno (PostgreSQL)
    lot_id: int | None = None  # FK para Lot
```

#### Entidade: Lot

```python
@dataclass
class Lot:
    """
    Representa um lote dentro de um leilão (auction).

    Um lote agrupa N itens que serão vendidos juntos.
    Possui valor mínimo único para todo o conjunto.
    """
    # Identificação RFB
    rfb_id: int                # loleNrSq - ID sequencial único do lote na RFB
    numero: int                # nrAtribuido - número público atribuído ao lote
    # Referência ao Auction pai (dados RFB)
    edle: str                  # edle - ex: "800100/10/2025"
    edital: str                # edital - ex: "0800100/000010/2025"
    # Classificação
    tipo: str                  # tipo - categoria: "TÊXTIL", "MOTOCICLETA/ACESSÓRIO", etc.
    orgao: str                 # orgao - "Receita Federal do Brasil"
    cidade: str                # cidade - unidade regional
    # Valores
    valor_minimo: int          # valorMinimo - valor em reais inteiros (170000 = R$ 170.000,00)
    # Estado/Situação
    situacao_lote: int         # situacaoLote - código de status do lote
    situacao_edital: int       # situacaoEdital
    tipo_edital: int           # tipoEdital
    # Flags de permissão/visualização
    permite_pf: bool           # permitePF - permite Pessoa Física
    possui_imagens: bool       # possuiImagens
    destaque: bool             # destaque - lote em destaque
    # Contadores
    nr_avisos: int             # nrAvisos
    nr_erratas: int            # nrErratas
    # Relacionamentos (carregados sob demanda ou eager)
    itens: list[Item]          # itensDetalhesLote - lista de mercadorias
    imagens: list[LotImage]    # imagens
    avisos_erratas: list[AvisoErrata]  # avisosErratas
    # Identificação interna
    id: int | None = None           # ID interno (PostgreSQL)
    auction_id: int | None = None   # FK para Auction
```

#### Entidade: Auction

```python
@dataclass
class Auction:
    """
    Representa um edital/leilão da Receita Federal.

    É a entidade raiz que agrupa todos os lotes de um mesmo edital.
    Contém as datas importantes do ciclo de vida do leilão.
    """
    # Identificação RFB
    edital: str                # edital - ID completo: "0800100/000010/2025"
    edle: str                  # edle - ID curto para API: "800100/10/2025"
    # Classificação
    tipo: str                  # tipo - tipo do edital (ex: "1")
    orgao: str                 # orgao - "RFB" ou "Receita Federal do Brasil"
    # Localização
    cidade: str                # cidade - cidade da unidade
    unidade_nome: str          # uaNm - nome completo da unidade armazenadora
    # Estado/Situação
    codigo_situacao: int       # codigoSituacao - status do edital (2, 11, 12, 14, 15)
    # Flags
    permite_pf: bool           # permitePF - permite Pessoa Física participar
    # Datas do ciclo de vida
    data_inicio_propostas: datetime   # dataInicioPropostas
    data_fim_propostas: datetime      # dataFimPropostas
    data_abertura_lances: datetime    # dataAberturaLances
    # Contadores
    total_lotes: int           # lotes - quantidade total de lotes
    mercadorias_apreendidas: bool = False  # mercadoriasApreendidas
    data_classificacao: datetime | None = None  # dataClassificacao (só em details)
    # Metadados (disponíveis em auction_details)
    forma_contato: str | None = None         # formaContato
    dados_publicacao: str | None = None      # dadosPublicacao
    numero_recursos: int = 0   # numeroRecursos
    numero_avisos: int = 0     # numeroAvisos
    numero_erratas: int = 0    # numeroErratas
    # Relacionamentos
    lotes: list[Lot]           # listaLotes - carregado em auction_details
    avisos_erratas: list[AvisoErrata]  # avisosErratas
    # Identificação interna
    id: int | None = None      # ID interno (PostgreSQL)
```

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

### Considerações para Implementação

1. **Lazy vs Eager Loading**: `Lot.itens` e `Auction.lotes` podem ser carregados sob demanda para evitar chamadas desnecessárias à API.

2. **Imutabilidade**: Value Objects (`LotImage`, `AvisoErrata`) devem ser `frozen=True`.

3. **Validação de valores**: O campo `valor_minimo` é um inteiro representando reais (sem centavos). Considerar criar um Value Object `Money` para formatação e operações.

4. **Parsing de datas**: Formato da API é `"YYYY-MM-DD HH:MM"`. Criar factory methods para parsing consistente.

5. **Enums para situações**: Os códigos de `codigo_situacao` e `situacao_lote` podem ser mapeados para Enums com nomes descritivos.
 
### Tools de coleta e estruturação dos dados via http request
1. Usar http request simples e beautifull soup para parse da response
2. Utilizar as entidades definidas em `shared/domain/auction` para estruturação das responses recebidas
3. Considerando, `config/README.md`, prever um modo de teste que colete dados apenas:
    - de 1 edital para cada codigo_situacao distinto encontrado ;
    - de 1 lote para cada edital coletado ; 
    - de todos os itens do lote coletado 
4. Criar tools em novos arquivos:
    - apps/rfb_auction_tools/tools/__init__.py
    - apps/rfb_auction_tools/tools/collectors.py
