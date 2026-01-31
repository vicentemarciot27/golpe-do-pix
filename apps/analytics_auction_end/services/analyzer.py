"""
Analyzer service for auction end results.

Provides analysis and aggregation functions for auction data.
"""

from dataclasses import dataclass
from typing import Optional

from shared.domain.auction_end.entities import (
    AuctionEndResult,
    LotResult,
)
from shared.domain.auction_end.value_objects import BidStatus
from shared.ports.auction_end_storage import AuctionEndStorage


@dataclass
class LotAnalysis:
    """Analysis results for a single lot."""
    lot_number: int
    has_winner: bool
    winning_value: Optional[float]
    winner_cnpj: Optional[str]
    winner_name: Optional[str]
    total_proposals: int
    classified_proposals: int
    rejected_proposals: int
    total_bids: int
    winning_bids: int
    bid_increment_average: Optional[float]
    competition_level: str  # "low", "medium", "high"


@dataclass
class AuctionAnalysis:
    """Aggregated analysis for entire auction."""
    edital: str
    total_lots: int
    lots_with_winner: int
    lots_without_winner: int
    total_value: float
    average_lot_value: float
    total_proposals: int
    total_bids: int
    unique_bidders: int
    top_winner_cnpj: Optional[str]
    top_winner_name: Optional[str]
    top_winner_lots: int
    top_winner_value: float


class AuctionEndAnalyzer:
    """
    Analyzer for auction end results.

    Provides methods for analyzing parsed auction data
    and generating insights.
    """

    def __init__(self, storage: Optional[AuctionEndStorage] = None):
        """
        Initialize the analyzer.

        Args:
            storage: Optional storage for persisting/loading results.
        """
        self.storage = storage

    def analyze_lot(self, lot: LotResult) -> LotAnalysis:
        """
        Analyze a single lot result.

        Args:
            lot: The lot result to analyze.

        Returns:
            LotAnalysis with computed metrics.
        """
        # Count proposals by status
        classified = len(lot.classified_proposals)
        rejected = lot.total_proposals - classified

        # Count winning bids
        winning_bids = sum(
            1 for bid in lot.bid_history
            if bid.status == BidStatus.VENCEDOR
        )

        # Calculate average bid increment
        bid_increment_avg = self._calculate_bid_increment_avg(lot)

        # Determine competition level
        competition = self._determine_competition_level(lot)

        return LotAnalysis(
            lot_number=lot.lot_number,
            has_winner=lot.has_winner,
            winning_value=lot.winning_value,
            winner_cnpj=lot.winner.cnpj_cpf if lot.winner else None,
            winner_name=lot.winner.name if lot.winner else None,
            total_proposals=lot.total_proposals,
            classified_proposals=classified,
            rejected_proposals=rejected,
            total_bids=lot.total_bids,
            winning_bids=winning_bids,
            bid_increment_average=bid_increment_avg,
            competition_level=competition,
        )

    def analyze_auction(self, result: AuctionEndResult) -> AuctionAnalysis:
        """
        Analyze complete auction end result.

        Args:
            result: The auction end result to analyze.

        Returns:
            AuctionAnalysis with aggregated metrics.
        """
        lots_with_winner = result.lots_with_winner
        total_value = result.total_value

        # Calculate averages
        avg_value = total_value / len(lots_with_winner) if lots_with_winner else 0.0

        # Count totals
        total_proposals = sum(lot.total_proposals for lot in result.lot_results)
        total_bids = sum(lot.total_bids for lot in result.lot_results)

        # Find unique bidders
        unique_bidders = self._count_unique_bidders(result)

        # Find top winner
        top_winner = self._find_top_winner(result)

        return AuctionAnalysis(
            edital=result.edital,
            total_lots=result.total_lots,
            lots_with_winner=len(lots_with_winner),
            lots_without_winner=len(result.lots_without_winner),
            total_value=total_value,
            average_lot_value=avg_value,
            total_proposals=total_proposals,
            total_bids=total_bids,
            unique_bidders=unique_bidders,
            top_winner_cnpj=top_winner[0] if top_winner else None,
            top_winner_name=top_winner[1] if top_winner else None,
            top_winner_lots=top_winner[2] if top_winner else 0,
            top_winner_value=top_winner[3] if top_winner else 0.0,
        )

    def get_winner_summary(
        self, result: AuctionEndResult
    ) -> list[dict]:
        """
        Get summary of all winners in the auction.

        Args:
            result: The auction end result.

        Returns:
            List of dicts with winner info sorted by total value.
        """
        winners = {}

        for lot in result.lot_results:
            if lot.winner and lot.winning_value:
                cnpj = lot.winner.cnpj_cpf
                if cnpj not in winners:
                    winners[cnpj] = {
                        "cnpj_cpf": cnpj,
                        "name": lot.winner.name,
                        "lots_won": 0,
                        "total_value": 0.0,
                        "lot_numbers": [],
                    }
                winners[cnpj]["lots_won"] += 1
                winners[cnpj]["total_value"] += lot.winning_value
                winners[cnpj]["lot_numbers"].append(lot.lot_number)

        # Sort by total value descending
        return sorted(
            winners.values(),
            key=lambda x: x["total_value"],
            reverse=True,
        )

    def get_lots_for_winner(
        self, result: AuctionEndResult, cnpj_cpf: str
    ) -> list[LotResult]:
        """
        Get all lots won by a specific winner.

        Args:
            result: The auction end result.
            cnpj_cpf: The winner's CNPJ/CPF.

        Returns:
            List of LotResult for the winner.
        """
        return [
            lot for lot in result.lot_results
            if lot.winner and lot.winner.cnpj_cpf == cnpj_cpf
        ]

    def save_result(self, result: AuctionEndResult) -> int:
        """
        Save auction end result to storage.

        Args:
            result: The result to save.

        Returns:
            The ID of the saved result.

        Raises:
            ValueError: If storage is not configured.
        """
        if not self.storage:
            raise ValueError("Storage not configured")
        return self.storage.save_full_result(result)

    def load_result(self, edital: str) -> Optional[AuctionEndResult]:
        """
        Load auction end result from storage.

        Args:
            edital: The edital number.

        Returns:
            AuctionEndResult or None if not found.

        Raises:
            ValueError: If storage is not configured.
        """
        if not self.storage:
            raise ValueError("Storage not configured")
        return self.storage.get_by_edital(edital)

    def _calculate_bid_increment_avg(self, lot: LotResult) -> Optional[float]:
        """Calculate average bid increment for a lot."""
        if len(lot.bid_history) < 2:
            return None

        # Sort by sequence
        sorted_bids = sorted(lot.bid_history, key=lambda x: x.sequence)

        increments = []
        for i in range(1, len(sorted_bids)):
            increment = sorted_bids[i].value - sorted_bids[i - 1].value
            if increment > 0:
                increments.append(increment)

        return sum(increments) / len(increments) if increments else None

    def _determine_competition_level(self, lot: LotResult) -> str:
        """Determine competition level based on proposals and bids."""
        classified = len(lot.classified_proposals)

        if classified <= 1:
            return "low"
        elif classified <= 3:
            return "medium"
        else:
            return "high"

    def _count_unique_bidders(self, result: AuctionEndResult) -> int:
        """Count unique bidders across all lots."""
        bidders = set()
        for lot in result.lot_results:
            for proposal in lot.proposals:
                bidders.add(proposal.bidder_id)
            for bid in lot.bid_history:
                bidders.add(bid.bidder_id)
        return len(bidders)

    def _find_top_winner(
        self, result: AuctionEndResult
    ) -> Optional[tuple[str, str, int, float]]:
        """Find the winner with highest total value."""
        winners = self.get_winner_summary(result)
        if not winners:
            return None

        top = winners[0]
        return (
            top["cnpj_cpf"],
            top["name"],
            top["lots_won"],
            top["total_value"],
        )
