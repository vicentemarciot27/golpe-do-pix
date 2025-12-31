from dataclasses import dataclass


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
