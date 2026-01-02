from dataclasses import dataclass, field
from datetime import datetime

from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.value_objects import AvisoErrata


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
    mercadorias_apreendidas: bool | None = None  # mercadoriasApreendidas
    data_classificacao: datetime | None = None  # dataClassificacao (só em details)
    # Metadados (disponíveis em auction_details)
    forma_contato: str | None = None         # formaContato
    dados_publicacao: str | None = None      # dadosPublicacao
    numero_recursos: int = 0   # numeroRecursos
    numero_avisos: int = 0     # numeroAvisos
    numero_erratas: int = 0    # numeroErratas
    # Relacionamentos
    lotes: list[Lot] = field(default_factory=list)  # listaLotes - carregado em auction_details
    avisos_erratas: list[AvisoErrata] = field(default_factory=list)  # avisosErratas
    # Identificação interna
    id: int | None = None      # ID interno (PostgreSQL)
