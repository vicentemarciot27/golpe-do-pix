"""
Domain entities for auction end results (winners report).
"""

from shared.domain.auction_end.entities import (
    AuctionEndResult,
    LotResult,
    Proposal,
    BidHistoryEntry,
)
from shared.domain.auction_end.value_objects import (
    ProposalStatus,
    BidStatus,
    WinnerInfo,
)

__all__ = [
    "AuctionEndResult",
    "LotResult",
    "Proposal",
    "BidHistoryEntry",
    "ProposalStatus",
    "BidStatus",
    "WinnerInfo",
]
