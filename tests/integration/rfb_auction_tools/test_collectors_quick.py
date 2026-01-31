"""
Integration tests for RFB Auction collectors.
These tests make real HTTP requests to the RFB API.
"""

import pytest

from apps.rfb_auction_tools.collectors import RFBAuctionCollector
from config.rfb_auction_tools.settings import RFBAuctionSettings


class TestRFBAuctionCollector:
    """Tests for RFBAuctionCollector."""

    @pytest.fixture
    def collector(self) -> RFBAuctionCollector:
        """Create a collector instance with default settings."""
        settings = RFBAuctionSettings()
        return RFBAuctionCollector(settings)

    def test_collect_test_sample(self, collector: RFBAuctionCollector, results):
        """
        Test collecting a sample following the test mode rules:
        1. One auction per distinct codigo_situacao
        2. One lot per auction collected
        3. All items for each lot collected

        Results are saved to tests/results/rfb_auction_tools/
        """
        # Collect test sample
        data = collector.collect_test_sample()

        # Save results
        results.store("rfb_auction_tools_test_sample", data)

        # Validate structure
        assert "auctions" in data
        assert "lots" in data
        assert "items" in data
        assert "lot_images" in data
        assert "avisos_erratas" in data

        # Validate that we collected at least one auction
        assert len(data["auctions"]) > 0, "Should collect at least one auction"

        # Validate that we collected one lot per auction
        assert len(data["lots"]) == len(data["auctions"]), (
            f"Should have same number of lots ({len(data['lots'])}) "
            f"as auctions ({len(data['auctions'])})"
        )

        # Validate that auctions have distinct codigo_situacao
        situacoes = {auction["codigo_situacao"] for auction in data["auctions"]}
        assert len(situacoes) == len(data["auctions"]), (
            "Each auction should have a distinct codigo_situacao"
        )

        # Log summary
        print(f"\n📊 Collection Summary:")
        print(f"   • Auctions: {len(data['auctions'])}")
        print(f"   • Lots: {len(data['lots'])}")
        print(f"   • Items: {len(data['items'])}")
        print(f"   • Images: {len(data['lot_images'])}")
        print(f"   • Avisos/Erratas: {len(data['avisos_erratas'])}")
        print(f"   • Situações: {sorted(situacoes)}")

    def test_fetch_available_auctions(self, collector: RFBAuctionCollector):
        """Test fetching the list of available auctions."""
        auctions = collector.fetch_available_auctions()

        assert len(auctions) > 0, "Should return at least one auction"

        # Validate first auction structure
        auction = auctions[0]
        assert auction.edital is not None
        assert auction.edle is not None
        assert auction.codigo_situacao in [2, 11, 12, 14, 15]

        print(f"\n📋 Found {len(auctions)} available auctions")
