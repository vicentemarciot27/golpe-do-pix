"""
Integration tests for RFB Auction collectors - Full collection.
These tests make real HTTP requests to the RFB API and collect ALL data.
Used for performance analysis and benchmarking.
"""

import time
from dataclasses import asdict
from typing import Any

import pytest
import requests

from apps.rfb_auction_tools.collectors import (
    LotUnavailableError,
    RFBAuctionCollector,
)
from config.rfb_auction_tools.settings import RFBAuctionSettings


class TestRFBAuctionCollectorFull:
    """Full collection tests for RFBAuctionCollector."""

    @pytest.fixture
    def collector_no_retry(self) -> RFBAuctionCollector:
        """Create a collector without retry for first pass."""
        settings = RFBAuctionSettings(max_retries=1)
        return RFBAuctionCollector(settings)

    @pytest.fixture
    def collector_with_retry(self) -> RFBAuctionCollector:
        """Create a collector with retry for second pass."""
        settings = RFBAuctionSettings(max_retries=3)
        return RFBAuctionCollector(settings)

    def test_collect_all(
        self,
        collector_no_retry: RFBAuctionCollector,
        collector_with_retry: RFBAuctionCollector,
        results,
    ):
        """
        Collect ALL available auctions, lots, and items.

        This test is designed for performance analysis and timing studies.
        It collects everything from the RFB API and saves to results.
        """
        start_time = time.time()
        timing: dict[str, float] = {}

        result: dict[str, list[Any]] = {
            "auctions": [],
            "lots": [],
            "items": [],
            "lot_images": [],
            "avisos_erratas": [],
        }

        # Step 1: Fetch all available auctions (no retry needed - single request)
        step_start = time.time()
        available_auctions = collector_no_retry.fetch_available_auctions()
        timing["fetch_available_auctions"] = time.time() - step_start
        print(f"\n⏱️  fetch_available_auctions: {timing['fetch_available_auctions']:.2f}s")
        print(f"   📋 Found {len(available_auctions)} auctions")

        # Step 2: Fetch details for each auction (first pass, no retry)
        step_start = time.time()
        auction_details_list = []

        for i, auction in enumerate(available_auctions, 1):
            auction_start = time.time()
            details = collector_no_retry.fetch_auction_details(auction.edle)
            auction_time = time.time() - auction_start

            auction_details_list.append(details)

            # Convert to dict and store
            auction_dict = asdict(details)
            auction_dict["lotes"] = []  # Remove nested lotes
            auction_dict["avisos_erratas"] = []  # Will add separately
            result["auctions"].append(auction_dict)

            # Add auction-level avisos_erratas
            for aviso in details.avisos_erratas:
                aviso_dict = asdict(aviso)
                aviso_dict["_auction_edle"] = auction.edle
                result["avisos_erratas"].append(aviso_dict)

            print(f"   [{i}/{len(available_auctions)}] Edital {auction.edital}: "
                  f"{len(details.lotes)} lotes ({auction_time:.2f}s)")

        timing["fetch_all_auction_details"] = time.time() - step_start
        print(f"\n⏱️  fetch_all_auction_details: {timing['fetch_all_auction_details']:.2f}s")

        # Step 3: Fetch details for each lot (first pass, no retry)
        step_start = time.time()
        total_lots = sum(len(a.lotes) for a in auction_details_list)
        lot_count = 0
        failed_lots: list[dict[str, Any]] = []  # Real errors (500, timeout, etc) - will retry
        unavailable_lots: list[dict[str, Any]] = []  # HTTP 422 - lot in non-queryable state

        def process_lot(lot, edle: str) -> None:
            """Process a successfully fetched lot."""
            lot_dict = asdict(lot)
            lot_dict["itens"] = []
            lot_dict["imagens"] = []
            lot_dict["avisos_erratas"] = []
            lot_dict["_auction_edle"] = edle
            result["lots"].append(lot_dict)

            for item in lot.itens:
                item_dict = asdict(item)
                item_dict["_lot_rfb_id"] = lot.rfb_id
                item_dict["_auction_edle"] = edle
                result["items"].append(item_dict)

            for image in lot.imagens:
                image_dict = asdict(image)
                image_dict["_lot_rfb_id"] = lot.rfb_id
                image_dict["_auction_edle"] = edle
                result["lot_images"].append(image_dict)

            for aviso in lot.avisos_erratas:
                aviso_dict = asdict(aviso)
                aviso_dict["_lot_rfb_id"] = lot.rfb_id
                aviso_dict["_auction_edle"] = edle
                result["avisos_erratas"].append(aviso_dict)

        print("\n📥 First pass (no retry)...")
        for auction in auction_details_list:
            for lot_preview in auction.lotes:
                lot_count += 1
                lot_start = time.time()

                try:
                    lot = collector_no_retry.fetch_lot_details(
                        auction.edle, lot_preview.rfb_id
                    )
                    lot_time = time.time() - lot_start
                    process_lot(lot, auction.edle)

                except LotUnavailableError as e:
                    # HTTP 422 - lot in non-queryable state, no retry needed
                    lot_time = time.time() - lot_start
                    unavailable_lots.append({
                        "edle": auction.edle,
                        "lot_id": lot_preview.rfb_id,
                        "error": str(e),
                        "codigo_situacao": auction.codigo_situacao,
                    })

                except requests.exceptions.RequestException as e:
                    # Real errors (500, timeout, etc) - will retry
                    lot_time = time.time() - lot_start
                    failed_lots.append({
                        "edle": auction.edle,
                        "lot_id": lot_preview.rfb_id,
                        "error": str(e),
                        "codigo_situacao": auction.codigo_situacao,
                    })

                if lot_count % 50 == 0 or lot_count == total_lots:
                    print(f"   [{lot_count}/{total_lots}] Lots processed... ({lot_time:.2f}s last)")

        timing["fetch_all_lot_details_pass1"] = time.time() - step_start
        print(f"\n⏱️  First pass: {timing['fetch_all_lot_details_pass1']:.2f}s")
        print(f"   ✅ Collected: {len(result['lots'])}, 🚫 Unavailable: {len(unavailable_lots)}, ⚠️ Failed: {len(failed_lots)}")

        # Step 4: Retry failed lots only (with retry/backoff)
        # Note: unavailable_lots (HTTP 422) are NOT retried - they are in a non-queryable state
        if failed_lots:
            step_start = time.time()
            print(f"\n🔄 Second pass: retrying {len(failed_lots)} failed lots (real errors only)...")
            still_failed: list[dict[str, Any]] = []

            for i, fl in enumerate(failed_lots, 1):
                try:
                    lot = collector_with_retry.fetch_lot_details(fl["edle"], fl["lot_id"])
                    process_lot(lot, fl["edle"])
                    print(f"   [{i}/{len(failed_lots)}] ✅ Recovered: {fl['lot_id']}")
                except LotUnavailableError as e:
                    # Was a real error before, now it's unavailable
                    unavailable_lots.append({
                        "edle": fl["edle"],
                        "lot_id": fl["lot_id"],
                        "error": str(e),
                        "codigo_situacao": fl.get("codigo_situacao"),
                    })
                    print(f"   [{i}/{len(failed_lots)}] 🚫 Now unavailable: {fl['lot_id']}")
                except requests.exceptions.RequestException as e:
                    still_failed.append({
                        "edle": fl["edle"],
                        "lot_id": fl["lot_id"],
                        "error": str(e),
                        "codigo_situacao": fl.get("codigo_situacao"),
                    })
                    print(f"   [{i}/{len(failed_lots)}] ❌ Still failed: {fl['lot_id']}")

            timing["fetch_all_lot_details_pass2"] = time.time() - step_start
            recovered = len(failed_lots) - len(still_failed) - len([u for u in unavailable_lots if u.get("codigo_situacao") == fl.get("codigo_situacao")])
            print(f"\n⏱️  Second pass: {timing['fetch_all_lot_details_pass2']:.2f}s")
            print(f"   ✅ Recovered: {len(failed_lots) - len(still_failed)}, ❌ Still failed: {len(still_failed)}")
            failed_lots = still_failed

        timing["fetch_all_lot_details"] = timing.get("fetch_all_lot_details_pass1", 0) + timing.get("fetch_all_lot_details_pass2", 0)

        # Calculate totals
        total_time = time.time() - start_time
        timing["total"] = total_time

        # Add timing metadata to results
        result["_timing"] = timing
        result["_failed_lots"] = failed_lots
        result["_unavailable_lots"] = unavailable_lots
        result["_summary"] = {
            "total_auctions": len(result["auctions"]),
            "total_lots": len(result["lots"]),
            "total_items": len(result["items"]),
            "total_images": len(result["lot_images"]),
            "total_avisos_erratas": len(result["avisos_erratas"]),
            "total_unavailable_lots": len(unavailable_lots),
            "total_failed_lots": len(failed_lots),
            "total_time_seconds": total_time,
        }

        # Save results
        results.store("rfb_auction_tools_full_collection", result)

        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 FULL COLLECTION SUMMARY")
        print(f"{'='*60}")
        print(f"   • Auctions:           {len(result['auctions']):>6}")
        print(f"   • Lots:               {len(result['lots']):>6}")
        print(f"   • Items:              {len(result['items']):>6}")
        print(f"   • Images:             {len(result['lot_images']):>6}")
        print(f"   • Avisos/Erratas:     {len(result['avisos_erratas']):>6}")
        if unavailable_lots:
            print(f"   • Unavailable Lots:   {len(unavailable_lots):>6} 🚫")
        if failed_lots:
            print(f"   • Failed Lots:        {len(failed_lots):>6} ⚠️")
        print(f"{'='*60}")
        print(f"⏱️  TIMING BREAKDOWN")
        print(f"{'='*60}")
        print(f"   • Available auctions: {timing['fetch_available_auctions']:>8.2f}s")
        print(f"   • Auction details:    {timing['fetch_all_auction_details']:>8.2f}s")
        print(f"   • Lot details pass 1: {timing.get('fetch_all_lot_details_pass1', 0):>8.2f}s")
        if "fetch_all_lot_details_pass2" in timing:
            print(f"   • Lot details pass 2: {timing['fetch_all_lot_details_pass2']:>8.2f}s")
        print(f"   • TOTAL:              {total_time:>8.2f}s")
        print(f"{'='*60}")

        # Group unavailable lots by codigo_situacao
        if unavailable_lots:
            print(f"🚫 UNAVAILABLE LOTS ({len(unavailable_lots)}) - HTTP 422")
            print(f"{'='*60}")
            by_situacao: dict[int, int] = {}
            for ul in unavailable_lots:
                sit = ul.get("codigo_situacao", "unknown")
                by_situacao[sit] = by_situacao.get(sit, 0) + 1
            for sit, count in sorted(by_situacao.items(), key=lambda x: -x[1]):
                print(f"   • codigo_situacao={sit}: {count} lots")
            print(f"{'='*60}")

        # Group failed lots by error type
        if failed_lots:
            print(f"⚠️  FAILED LOTS ({len(failed_lots)}) - Real Errors")
            print(f"{'='*60}")
            by_error_type: dict[str, list[dict]] = {}
            for fl in failed_lots:
                error_msg = fl["error"]
                if "500" in error_msg:
                    error_type = "HTTP 500 (Server Error)"
                elif "404" in error_msg:
                    error_type = "HTTP 404 (Not Found)"
                elif "timeout" in error_msg.lower():
                    error_type = "Timeout"
                else:
                    error_type = "Other"
                if error_type not in by_error_type:
                    by_error_type[error_type] = []
                by_error_type[error_type].append(fl)

            for error_type, lots in sorted(by_error_type.items(), key=lambda x: -len(x[1])):
                print(f"\n   {error_type}: {len(lots)} lots")
                # Group by edle to show which auctions are affected
                by_edle: dict[str, int] = {}
                for lot in lots:
                    edle = lot["edle"]
                    by_edle[edle] = by_edle.get(edle, 0) + 1
                for edle, count in sorted(by_edle.items(), key=lambda x: -x[1])[:5]:
                    print(f"      - {edle}: {count} lots")
                if len(by_edle) > 5:
                    print(f"      ... and {len(by_edle) - 5} more editais")
            print(f"\n{'='*60}")

        # Validate structure
        assert len(result["auctions"]) > 0, "Should collect at least one auction"
        assert len(result["lots"]) > 0, "Should collect at least one lot"

