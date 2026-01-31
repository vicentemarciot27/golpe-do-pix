"""
Helper functions for auction end analytics.

These are pure functions (no Streamlit dependency) designed to be used
by the max_bid UI or any other consumer.

Example usage in max_bid UI:
    from apps.analytics_auction_end.helpers import AuctionEndHelper

    helper = AuctionEndHelper()
    result = helper.parse_pdf("path/to/winners.pdf", max_pages=5)
    lot = helper.get_lot_by_number(result, 3)
    winning_value = helper.get_winning_value(lot)
    comparison = helper.compare_with_max_bid(lot, calculated_max_bid)
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional

from apps.analytics_auction_end.services.pdf_parser import AuctionEndPDFParser
from apps.analytics_auction_end.services.analyzer import (
    AuctionEndAnalyzer,
    LotAnalysis,
    AuctionAnalysis,
)
from apps.analytics_auction_end.services.manual_entry import (
    ManualAuctionEndEntry,
    create_auction_end_from_data,
)
from shared.domain.auction_end.entities import (
    AuctionEndResult,
    LotResult,
)
from shared.domain.auction_end.value_objects import WinnerInfo
from shared.ports.auction_end_storage import AuctionEndStorage
from shared.adapters.outbound.postgres_auction_end_storage import (
    PostgresAuctionEndStorage,
)


@dataclass
class MaxBidComparison:
    """Result of comparing calculated max bid with actual winning bid."""
    lot_number: int
    calculated_max_bid: float
    actual_winning_bid: Optional[float]
    difference: Optional[float]  # winning - max_bid
    difference_percent: Optional[float]
    would_have_won: bool
    has_winner: bool
    winner_cnpj: Optional[str]
    winner_name: Optional[str]


@dataclass
class LotSummary:
    """Summary of a lot result for display."""
    lot_number: int
    has_winner: bool
    winner_cnpj: Optional[str]
    winner_name: Optional[str]
    winning_value: Optional[float]
    total_proposals: int
    classified_proposals: int
    total_bids: int


class AuctionEndHelper:
    """
    Helper class for auction end analytics.

    Provides pure functions (no Streamlit dependency) for:
    - Parsing auction end PDFs
    - Querying lot results
    - Comparing with max bid calculations
    - Persisting results to database
    """

    def __init__(self, storage: Optional[AuctionEndStorage] = None):
        """
        Initialize the helper.

        Args:
            storage: Optional storage adapter. If None, will create
                     PostgresAuctionEndStorage when needed.
        """
        self._storage = storage
        self._analyzer: Optional[AuctionEndAnalyzer] = None

    @property
    def storage(self) -> Optional[AuctionEndStorage]:
        """Get or create storage adapter."""
        if self._storage is None:
            try:
                self._storage = PostgresAuctionEndStorage()
            except Exception:
                pass
        return self._storage

    @property
    def analyzer(self) -> AuctionEndAnalyzer:
        """Get or create analyzer instance."""
        if self._analyzer is None:
            self._analyzer = AuctionEndAnalyzer(storage=self.storage)
        return self._analyzer

    # === PARSING ===

    def parse_pdf(
        self,
        file: str | Path | BinaryIO,
        max_pages: Optional[int] = None,
        use_ocr: bool = True,
    ) -> AuctionEndResult:
        """
        Parse an auction end PDF.

        Args:
            file: File path or file-like object.
            max_pages: Maximum pages to parse (None = all pages).
            use_ocr: Whether to use OCR for image-based PDFs.

        Returns:
            Parsed AuctionEndResult.
        """
        parser = AuctionEndPDFParser(max_pages=max_pages, use_ocr=use_ocr)

        if isinstance(file, (str, Path)):
            return parser.parse_file(file)
        else:
            return parser.parse_bytes(file)

    def parse_from_dict(self, data: dict) -> AuctionEndResult:
        """
        Create AuctionEndResult from dictionary data.

        Args:
            data: Dictionary with auction end data.

        Returns:
            AuctionEndResult.
        """
        return create_auction_end_from_data(data)

    def parse_from_csv(self, csv_content: str) -> AuctionEndResult:
        """
        Create AuctionEndResult from CSV string.

        Args:
            csv_content: CSV content as string.

        Returns:
            AuctionEndResult.
        """
        return ManualAuctionEndEntry.create_from_csv_string(csv_content)

    # === QUERYING ===

    def get_lot_by_number(
        self, result: AuctionEndResult, lot_number: int
    ) -> Optional[LotResult]:
        """
        Get a specific lot by number.

        Args:
            result: The auction end result.
            lot_number: The lot number to find.

        Returns:
            LotResult or None if not found.
        """
        for lot in result.lot_results:
            if lot.lot_number == lot_number:
                return lot
        return None

    def get_winning_value(self, lot: LotResult) -> Optional[float]:
        """
        Get winning value for a lot.

        Args:
            lot: The lot result.

        Returns:
            Winning value or None if lot has no winner.
        """
        return lot.winning_value if lot.has_winner else None

    def get_winner_info(self, lot: LotResult) -> Optional[WinnerInfo]:
        """
        Get winner info for a lot.

        Args:
            lot: The lot result.

        Returns:
            WinnerInfo or None if lot has no winner.
        """
        return lot.winner if lot.has_winner else None

    def get_lot_summary(self, lot: LotResult) -> LotSummary:
        """
        Get summary of a lot result.

        Args:
            lot: The lot result.

        Returns:
            LotSummary with key metrics.
        """
        return LotSummary(
            lot_number=lot.lot_number,
            has_winner=lot.has_winner,
            winner_cnpj=lot.winner.cnpj_cpf if lot.winner else None,
            winner_name=lot.winner.name if lot.winner else None,
            winning_value=lot.winning_value,
            total_proposals=lot.total_proposals,
            classified_proposals=len(lot.classified_proposals),
            total_bids=lot.total_bids,
        )

    def get_all_lot_summaries(self, result: AuctionEndResult) -> list[LotSummary]:
        """
        Get summaries for all lots in an auction.

        Args:
            result: The auction end result.

        Returns:
            List of LotSummary sorted by lot number.
        """
        return [
            self.get_lot_summary(lot)
            for lot in sorted(result.lot_results, key=lambda x: x.lot_number)
        ]

    def get_lots_with_winner(self, result: AuctionEndResult) -> list[LotResult]:
        """
        Get all lots that have a winner.

        Args:
            result: The auction end result.

        Returns:
            List of LotResult with winners.
        """
        return result.lots_with_winner

    def get_lots_without_winner(self, result: AuctionEndResult) -> list[LotResult]:
        """
        Get all lots without a winner.

        Args:
            result: The auction end result.

        Returns:
            List of LotResult without winners.
        """
        return result.lots_without_winner

    # === COMPARISON ===

    def compare_with_max_bid(
        self, lot: LotResult, calculated_max_bid: float
    ) -> MaxBidComparison:
        """
        Compare calculated max bid with actual winning bid.

        Args:
            lot: The lot result.
            calculated_max_bid: The calculated maximum bid.

        Returns:
            MaxBidComparison with analysis.
        """
        actual = lot.winning_value
        difference = None
        difference_percent = None
        would_have_won = False

        if actual is not None:
            difference = actual - calculated_max_bid
            if calculated_max_bid > 0:
                difference_percent = (difference / calculated_max_bid) * 100
            would_have_won = calculated_max_bid >= actual

        return MaxBidComparison(
            lot_number=lot.lot_number,
            calculated_max_bid=calculated_max_bid,
            actual_winning_bid=actual,
            difference=difference,
            difference_percent=difference_percent,
            would_have_won=would_have_won,
            has_winner=lot.has_winner,
            winner_cnpj=lot.winner.cnpj_cpf if lot.winner else None,
            winner_name=lot.winner.name if lot.winner else None,
        )

    def compare_all_lots(
        self, result: AuctionEndResult, max_bids: dict[int, float]
    ) -> list[MaxBidComparison]:
        """
        Compare calculated max bids with all lot results.

        Args:
            result: The auction end result.
            max_bids: Dict mapping lot_number to calculated max bid.

        Returns:
            List of MaxBidComparison for each lot with max bid data.
        """
        comparisons = []
        for lot in result.lot_results:
            if lot.lot_number in max_bids:
                comparison = self.compare_with_max_bid(lot, max_bids[lot.lot_number])
                comparisons.append(comparison)
        return comparisons

    # === ANALYSIS ===

    def analyze_lot(self, lot: LotResult) -> LotAnalysis:
        """
        Analyze a single lot.

        Args:
            lot: The lot result to analyze.

        Returns:
            LotAnalysis with computed metrics.
        """
        return self.analyzer.analyze_lot(lot)

    def analyze_auction(self, result: AuctionEndResult) -> AuctionAnalysis:
        """
        Analyze complete auction.

        Args:
            result: The auction end result.

        Returns:
            AuctionAnalysis with aggregated metrics.
        """
        return self.analyzer.analyze_auction(result)

    def get_winner_summary(self, result: AuctionEndResult) -> list[dict]:
        """
        Get summary of all winners.

        Args:
            result: The auction end result.

        Returns:
            List of winner summaries sorted by total value.
        """
        return self.analyzer.get_winner_summary(result)

    # === PERSISTENCE ===

    def save_to_database(self, result: AuctionEndResult) -> int:
        """
        Save auction end result to database.

        Args:
            result: The result to save.

        Returns:
            The ID of the saved result.

        Raises:
            ValueError: If storage is not available.
        """
        if not self.storage:
            raise ValueError("Database storage not available")
        return self.storage.save_full_result(result)

    def load_from_database(self, edital: str) -> Optional[AuctionEndResult]:
        """
        Load auction end result from database by edital.

        Args:
            edital: The edital number.

        Returns:
            AuctionEndResult or None if not found.

        Raises:
            ValueError: If storage is not available.
        """
        if not self.storage:
            raise ValueError("Database storage not available")
        return self.storage.get_by_edital(edital)

    def list_saved_analyses(self) -> list[dict]:
        """
        List all saved auction end analyses from database.

        Returns:
            List of dicts with analysis summary info.

        Raises:
            ValueError: If storage is not available.
        """
        if not self.storage:
            raise ValueError("Database storage not available")

        results = self.storage.list_all()
        return [
            {
                "id": r.id,
                "edital": r.edital,
                "auction_date": r.auction_date,
                "created_at": r.created_at,
                "total_lots": getattr(r, "_total_lots", 0),
                "lots_with_winner": getattr(r, "_lots_with_winner", 0),
                "total_value": getattr(r, "_total_value", 0.0),
            }
            for r in results
        ]

    def load_full_result(self, edital: str) -> Optional[AuctionEndResult]:
        """
        Load full auction end result with all lot details.

        Args:
            edital: The edital number.

        Returns:
            AuctionEndResult with lot_results populated, or None.
        """
        if not self.storage:
            raise ValueError("Database storage not available")

        result = self.storage.get_by_edital(edital)
        if result and result.id:
            # Load lot results
            result.lot_results = self.storage.get_lot_results(result.id)
            # Load proposals and bid history for each lot
            for lot in result.lot_results:
                if lot.id:
                    lot.proposals = self.storage.get_proposals(lot.id)
                    lot.bid_history = self.storage.get_bid_history(lot.id)
        return result

    # === UTILITIES ===

    @staticmethod
    def format_currency(value: float) -> str:
        """
        Format value as Brazilian currency.

        Args:
            value: The value to format.

        Returns:
            Formatted string like "R$ 1.234,56".
        """
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def format_cnpj(cnpj: str) -> str:
        """
        Format CNPJ for display.

        Args:
            cnpj: The CNPJ string.

        Returns:
            Formatted CNPJ.
        """
        # Already formatted if contains dots
        if "." in cnpj:
            return cnpj
        # Format: XX.XXX.XXX/XXXX-XX
        if len(cnpj) == 14:
            return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
        return cnpj


# Convenience functions for direct import

def parse_auction_end_pdf(
    file: str | Path | BinaryIO,
    max_pages: Optional[int] = None,
) -> AuctionEndResult:
    """
    Convenience function to parse auction end PDF.

    Args:
        file: File path or file-like object.
        max_pages: Maximum pages to parse (None = all pages).

    Returns:
        Parsed AuctionEndResult.
    """
    helper = AuctionEndHelper()
    return helper.parse_pdf(file, max_pages=max_pages)


def get_winning_bid_for_lot(
    result: AuctionEndResult, lot_number: int
) -> Optional[float]:
    """
    Convenience function to get winning bid for a lot.

    Args:
        result: The auction end result.
        lot_number: The lot number.

    Returns:
        Winning value or None.
    """
    helper = AuctionEndHelper()
    lot = helper.get_lot_by_number(result, lot_number)
    if lot:
        return helper.get_winning_value(lot)
    return None


def compare_max_bid_with_winner(
    result: AuctionEndResult,
    lot_number: int,
    calculated_max_bid: float,
) -> Optional[MaxBidComparison]:
    """
    Convenience function to compare max bid with actual winner.

    Args:
        result: The auction end result.
        lot_number: The lot number.
        calculated_max_bid: The calculated max bid.

    Returns:
        MaxBidComparison or None if lot not found.
    """
    helper = AuctionEndHelper()
    lot = helper.get_lot_by_number(result, lot_number)
    if lot:
        return helper.compare_with_max_bid(lot, calculated_max_bid)
    return None
