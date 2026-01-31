"""
Analytics Auction End module.

Provides services for parsing and analyzing auction end results
from RFB's 'Relatório Relação de Vencedores' PDFs.

Supports:
- PDF parsing (text-based and OCR)
- Manual data entry via dictionary/CSV
- Analysis and aggregation of results
- Helper functions for UI integration (no Streamlit dependency)

Usage for max_bid UI integration:
    from apps.analytics_auction_end import AuctionEndHelper

    helper = AuctionEndHelper()
    result = helper.parse_pdf("path/to/winners.pdf", max_pages=5)
    comparison = helper.compare_with_max_bid(lot, calculated_max_bid)
"""

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
from apps.analytics_auction_end.helpers import (
    AuctionEndHelper,
    MaxBidComparison,
    LotSummary,
    parse_auction_end_pdf,
    get_winning_bid_for_lot,
    compare_max_bid_with_winner,
)

__all__ = [
    # Core services
    "AuctionEndPDFParser",
    "AuctionEndAnalyzer",
    "ManualAuctionEndEntry",
    "create_auction_end_from_data",
    # Analysis dataclasses
    "LotAnalysis",
    "AuctionAnalysis",
    # Helper class and dataclasses (for max_bid UI)
    "AuctionEndHelper",
    "MaxBidComparison",
    "LotSummary",
    # Convenience functions
    "parse_auction_end_pdf",
    "get_winning_bid_for_lot",
    "compare_max_bid_with_winner",
]
