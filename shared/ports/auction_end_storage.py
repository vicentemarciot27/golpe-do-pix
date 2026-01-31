"""
Port interface for auction end results storage.
"""

from abc import ABC, abstractmethod
from typing import Optional

from shared.domain.auction_end.entities import (
    AuctionEndResult,
    LotResult,
    Proposal,
    BidHistoryEntry,
)


class AuctionEndStorage(ABC):
    """Interface for persisting auction end results."""

    # === AUCTION END RESULT ===
    @abstractmethod
    def get_by_edital(self, edital: str) -> Optional[AuctionEndResult]:
        """Get auction end result by edital number."""
        pass

    @abstractmethod
    def get_by_auction_id(self, auction_id: int) -> Optional[AuctionEndResult]:
        """Get auction end result by auction ID."""
        pass

    @abstractmethod
    def create(self, result: AuctionEndResult) -> int:
        """Create auction end result and return the ID."""
        pass

    @abstractmethod
    def update(self, result: AuctionEndResult) -> None:
        """Update existing auction end result."""
        pass

    @abstractmethod
    def delete(self, result_id: int) -> None:
        """Delete auction end result and all related data."""
        pass

    # === LOT RESULT ===
    @abstractmethod
    def get_lot_results(self, auction_end_id: int) -> list[LotResult]:
        """Get all lot results for an auction end."""
        pass

    @abstractmethod
    def get_lot_result_by_number(
        self, auction_end_id: int, lot_number: int
    ) -> Optional[LotResult]:
        """Get lot result by lot number."""
        pass

    @abstractmethod
    def create_lot_result(self, lot: LotResult, auction_end_id: int) -> int:
        """Create lot result and return the ID."""
        pass

    # === PROPOSAL ===
    @abstractmethod
    def get_proposals(self, lot_result_id: int) -> list[Proposal]:
        """Get all proposals for a lot result."""
        pass

    @abstractmethod
    def create_proposal(self, proposal: Proposal, lot_result_id: int) -> int:
        """Create proposal and return the ID."""
        pass

    # === BID HISTORY ===
    @abstractmethod
    def get_bid_history(self, lot_result_id: int) -> list[BidHistoryEntry]:
        """Get bid history for a lot result."""
        pass

    @abstractmethod
    def create_bid_history_entry(
        self, entry: BidHistoryEntry, lot_result_id: int
    ) -> int:
        """Create bid history entry and return the ID."""
        pass

    # === BULK OPERATIONS ===
    @abstractmethod
    def save_full_result(self, result: AuctionEndResult) -> int:
        """
        Save complete auction end result including all lot results,
        proposals, and bid history. Returns the auction_end_result ID.
        """
        pass

    @abstractmethod
    def list_all(self) -> list[AuctionEndResult]:
        """
        List all saved auction end results (without lot details).
        Returns list of AuctionEndResult with basic info only.
        """
        pass

    # === CONNECTION ===
    @abstractmethod
    def closeall(self) -> None:
        """Close all connections."""
        pass
