from dataclasses import dataclass, field

from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import AvisoErrata, LotImage


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
    valor_minimo: int          # valorMinimo - valor em reais inteiros (1000 = R$ 1.000,00)
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
    itens: list[Item] = field(default_factory=list)              # itensDetalhesLote
    imagens: list[LotImage] = field(default_factory=list)        # imagens
    avisos_erratas: list[AvisoErrata] = field(default_factory=list)  # avisosErratas
    # Identificação interna
    id: int | None = None           # ID interno (PostgreSQL)
    auction_id: int | None = None   # FK para Auction
    is_active: bool = True          # Soft delete flag
    data_hash: str | None = None    # Hash para detecção de mudanças
