from dataclasses import dataclass
from datetime import datetime


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

