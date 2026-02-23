"""
Domain entities for auction end results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from shared.domain.auction_end.value_objects import (
    ProposalStatus,
    BidStatus,
    WinnerInfo,
)


@dataclass
class BidHistoryEntry:
    """
    Represents a single bid in the auction history.
    Maps to 'Histórico de Lances' table in the PDF.
    """
    sequence: int  # Seq. column
    timestamp: datetime  # Data/Hora Lance
    value: float  # Valor Lance (R$) - in centavos or reais
    status: BidStatus  # Situação
    bidder_id: str  # Licitante (e.g., "licitante12607")

    # Database fields
    id: Optional[int] = None
    lot_result_id: Optional[int] = None


@dataclass
class Proposal:
    """
    Represents a proposal submitted by a bidder.
    Maps to 'Relação de Propostas' table in the PDF.
    """
    bidder_id: str  # Proponente (e.g., "licitante12607")
    status: ProposalStatus  # Status da Proposta
    value: float  # Valor Proposta (R$)
    timestamp: datetime  # Data/Hora

    # Database fields
    id: Optional[int] = None
    lot_result_id: Optional[int] = None


@dataclass
class LotResult:
    """
    Represents the result of a single lot in an auction.
    Aggregates winner info, proposals, and bid history.
    """
    lot_number: int  # Lote:X
    winner: Optional[WinnerInfo]  # Vencedor info (CNPJ + name)
    winning_value: Optional[float]  # Valor (R$)

    # Related data
    proposals: list[Proposal] = field(default_factory=list)
    bid_history: list[BidHistoryEntry] = field(default_factory=list)

    # Database fields
    id: Optional[int] = None
    auction_end_result_id: Optional[int] = None

    @property
    def has_winner(self) -> bool:
        """Check if the lot has a winner."""
        return self.winner is not None and self.winning_value is not None

    @property
    def total_proposals(self) -> int:
        """Count total proposals."""
        return len(self.proposals)

    @property
    def total_bids(self) -> int:
        """Count total bids in history."""
        return len(self.bid_history)

    @property
    def classified_proposals(self) -> list[Proposal]:
        """Get only classified proposals."""
        return [p for p in self.proposals if p.status == ProposalStatus.CLASSIFICADA]


@dataclass
class AuctionEndResult:
    """
    Root aggregate for auction end results.
    Represents the full 'Relatório Relação de Vencedores' document.
    """
    edital: str  # e.g., "0800100/000008/2025"
    auction_date: datetime  # Date the auction was held
    report_date: datetime  # Date the report was generated

    # Related data
    lot_results: list[LotResult] = field(default_factory=list)

    # Database fields
    id: Optional[int] = None
    auction_id: Optional[int] = None  # FK to auctions table
    created_at: Optional[datetime] = None

    @property
    def total_lots(self) -> int:
        """Count total lots."""
        return len(self.lot_results)

    @property
    def lots_with_winner(self) -> list[LotResult]:
        """Get lots that have a winner."""
        return [lot for lot in self.lot_results if lot.has_winner]

    @property
    def lots_without_winner(self) -> list[LotResult]:
        """Get lots that don't have a winner."""
        return [lot for lot in self.lot_results if not lot.has_winner]

    @property
    def total_value(self) -> float:
        """Sum of all winning values."""
        return sum(
            lot.winning_value for lot in self.lot_results
            if lot.winning_value is not None
        )
