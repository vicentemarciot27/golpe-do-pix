"""
UI helpers for analytics_auction_end module.

Provides helper functions to be used in the max_bid UI or other Streamlit apps.

Two approaches are available:

1. Streamlit-dependent (session state management):
   Use functions from this module for full Streamlit integration.

2. Pure helpers (no Streamlit dependency):
   from apps.analytics_auction_end import AuctionEndHelper
   Use AuctionEndHelper class for clean, testable code.
"""

# Constants (no Streamlit dependency)
from apps.analytics_auction_end.ui.constants import (
    COMPETITION_LEVEL_LABELS,
    PROPOSAL_STATUS_LABELS,
    BID_STATUS_LABELS,
    DEFAULT_MAX_PAGES,
)

# Pure helpers (no Streamlit dependency)
from apps.analytics_auction_end.helpers import (
    AuctionEndHelper,
    MaxBidComparison,
    LotSummary,
)

# Streamlit-dependent services - lazy import to avoid import errors
# when streamlit is not available
def __getattr__(name):
    """Lazy import Streamlit-dependent functions."""
    _streamlit_exports = {
        "initialize_auction_end_storage",
        "parse_auction_end_pdf",
        "get_lot_result_for_lot",
        "get_winning_bid_for_lot",
        "render_auction_end_summary",
        "render_lot_result_details",
        "render_winner_comparison",
        "format_currency",
        "load_auction_end_from_dict",
        "load_auction_end_from_csv",
        "render_manual_entry_form",
        "render_csv_upload",
        "save_auction_end_result",
        "render_lot_selector",
        "get_auction_end_analysis",
        "get_lot_analysis",
    }
    if name in _streamlit_exports:
        from apps.analytics_auction_end.ui import services
        return getattr(services, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Constants (always available)
    "COMPETITION_LEVEL_LABELS",
    "PROPOSAL_STATUS_LABELS",
    "BID_STATUS_LABELS",
    "DEFAULT_MAX_PAGES",
    # Pure helpers (always available)
    "AuctionEndHelper",
    "MaxBidComparison",
    "LotSummary",
    # Streamlit services (lazy loaded)
    "initialize_auction_end_storage",
    "parse_auction_end_pdf",
    "load_auction_end_from_dict",
    "load_auction_end_from_csv",
    "get_lot_result_for_lot",
    "get_winning_bid_for_lot",
    "get_auction_end_analysis",
    "get_lot_analysis",
    "render_auction_end_summary",
    "render_lot_result_details",
    "render_winner_comparison",
    "render_lot_selector",
    "render_manual_entry_form",
    "render_csv_upload",
    "save_auction_end_result",
    "format_currency",
]

__all__ = [
    # Services - Loading
    "initialize_auction_end_storage",
    "parse_auction_end_pdf",
    "load_auction_end_from_dict",
    "load_auction_end_from_csv",
    # Services - Querying
    "get_lot_result_for_lot",
    "get_winning_bid_for_lot",
    "get_auction_end_analysis",
    "get_lot_analysis",
    # Services - Rendering
    "render_auction_end_summary",
    "render_lot_result_details",
    "render_winner_comparison",
    "render_lot_selector",
    "render_manual_entry_form",
    "render_csv_upload",
    # Services - Persistence
    "save_auction_end_result",
    # Utilities
    "format_currency",
    # Constants
    "COMPETITION_LEVEL_LABELS",
    "PROPOSAL_STATUS_LABELS",
    "BID_STATUS_LABELS",
    "DEFAULT_MAX_PAGES",
    # Pure helpers (no Streamlit dependency)
    "AuctionEndHelper",
    "MaxBidComparison",
    "LotSummary",
]
