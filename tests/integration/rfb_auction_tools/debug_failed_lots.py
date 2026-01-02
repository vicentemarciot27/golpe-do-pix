#!/usr/bin/env python3
"""
Debug script to identify failure patterns by codigo_situacao.

This script tests the hypothesis that lot collection errors are concentrated
in auctions with specific codigo_situacao values.

Uses stratified sampling for fast execution (~2-5 min vs ~1.5h full scan).
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from requests.exceptions import RequestException

from apps.rfb_auction_tools.collectors import (
    LotUnavailableError,
    RFBAuctionCollector,
)
from config.rfb_auction_tools.settings import RFBAuctionSettings

# Sampling configuration
DEFAULT_AUCTIONS_PER_SITUACAO = 2
DEFAULT_LOTS_PER_AUCTION = 5

# Known codigo_situacao meanings (best guess from observed data)
SITUACAO_LABELS = {
    2: "Aberto para propostas",
    11: "Finalizado",
    12: "Em homologacao",
    14: "Suspenso/Cancelado",
    15: "Encerrado com resultado",
}


def run_debug_sampling(
    auctions_per_situacao: int = DEFAULT_AUCTIONS_PER_SITUACAO,
    lots_per_auction: int = DEFAULT_LOTS_PER_AUCTION,
    verbose: bool = False,
) -> dict:
    """
    Run stratified sampling to identify failure patterns by codigo_situacao.

    Args:
        auctions_per_situacao: Number of auctions to test per situacao code
        lots_per_auction: Number of lots to test per auction
        verbose: Print detailed progress

    Returns:
        Dict with results grouped by codigo_situacao
    """
    settings = RFBAuctionSettings(request_timeout=15, max_retries=1)
    collector = RFBAuctionCollector(settings)

    results = {
        "by_situacao": defaultdict(lambda: {
            "auctions_tested": 0,
            "lots_tested": 0,
            "lots_success": 0,
            "lots_unavailable": 0,
            "lots_failed": 0,
            "errors": [],
            "auctions_with_no_lots": 0,
        }),
        "timing": {},
        "config": {
            "auctions_per_situacao": auctions_per_situacao,
            "lots_per_auction": lots_per_auction,
        },
    }

    # Step 1: Fetch available auctions
    print("\n[1/3] Fetching available auctions...")
    t0 = time.time()
    try:
        auctions = collector.fetch_available_auctions()
    except RequestException as e:
        print(f"FATAL: Could not fetch auctions list: {e}")
        return results
    results["timing"]["fetch_available_auctions"] = time.time() - t0
    print(f"      Found {len(auctions)} auctions in {results['timing']['fetch_available_auctions']:.2f}s")

    # Step 2: Group auctions by codigo_situacao
    print("\n[2/3] Grouping by codigo_situacao...")
    by_situacao: dict[int, list] = defaultdict(list)
    for auction in auctions:
        by_situacao[auction.codigo_situacao].append(auction)

    situacoes_found = sorted(by_situacao.keys())
    print(f"      Found {len(situacoes_found)} distinct situacao codes: {situacoes_found}")
    for sit in situacoes_found:
        label = SITUACAO_LABELS.get(sit, "Desconhecido")
        print(f"        - {sit} ({label}): {len(by_situacao[sit])} auctions")

    # Step 3: Sample and test lots
    print(f"\n[3/3] Testing lots (sample: {auctions_per_situacao} auctions x {lots_per_auction} lots per situacao)...")
    t0 = time.time()

    for situacao in situacoes_found:
        auction_list = by_situacao[situacao]
        sample_auctions = auction_list[:auctions_per_situacao]

        sit_label = SITUACAO_LABELS.get(situacao, "?")
        print(f"\n      codigo_situacao={situacao} ({sit_label})")
        print(f"        Testing {len(sample_auctions)} auction(s)...")

        for auction in sample_auctions:
            results["by_situacao"][situacao]["auctions_tested"] += 1

            # Fetch auction details to get lot list
            try:
                auction_detail = collector.fetch_auction_details(auction.edle)
            except RequestException as e:
                if verbose:
                    print(f"          [WARN] Could not fetch auction {auction.edle}: {e}")
                continue

            lots_to_test = auction_detail.lotes[:lots_per_auction]
            if not lots_to_test:
                results["by_situacao"][situacao]["auctions_with_no_lots"] += 1
                if verbose:
                    print(f"          [INFO] Auction {auction.edle} has no lots")
                continue

            for lot in lots_to_test:
                results["by_situacao"][situacao]["lots_tested"] += 1

                try:
                    collector.fetch_lot_details(auction.edle, lot.rfb_id)
                    results["by_situacao"][situacao]["lots_success"] += 1
                    if verbose:
                        print(f"          [OK] Lot {lot.rfb_id}")
                except LotUnavailableError:
                    results["by_situacao"][situacao]["lots_unavailable"] += 1
                    if verbose:
                        print(f"          [UNAVAIL] Lot {lot.rfb_id}")
                except RequestException as e:
                    results["by_situacao"][situacao]["lots_failed"] += 1
                    error_info = {
                        "edle": auction.edle,
                        "lot_id": lot.rfb_id,
                        "lot_numero": lot.numero,
                        "error": str(e),
                    }
                    results["by_situacao"][situacao]["errors"].append(error_info)
                    if verbose:
                        print(f"          [FAIL] Lot {lot.rfb_id}: {e}")

        # Progress summary for this situacao
        sit_data = results["by_situacao"][situacao]
        tested = sit_data["lots_tested"]
        unavail = sit_data["lots_unavailable"]
        failed = sit_data["lots_failed"]
        fail_rate = (failed / tested * 100) if tested > 0 else 0
        unavail_rate = (unavail / tested * 100) if tested > 0 else 0
        print(f"        Result: {tested} tested, {unavail} unavailable ({unavail_rate:.1f}%), {failed} failed ({fail_rate:.1f}%)")

    results["timing"]["test_lots"] = time.time() - t0
    results["timing"]["total"] = (
        results["timing"]["fetch_available_auctions"] + results["timing"]["test_lots"]
    )

    # Convert defaultdict to regular dict for JSON serialization
    results["by_situacao"] = dict(results["by_situacao"])

    return results


def print_report(results: dict) -> None:
    """Print formatted report to console."""
    print("\n")
    print("=" * 60)
    print("DEBUG: FALHAS POR CODIGO_SITUACAO (AMOSTRAGEM)")
    print("=" * 60)

    by_situacao = results.get("by_situacao", {})
    if not by_situacao:
        print("\nNo data collected.")
        return

    # Summary table
    total_tested = 0
    total_unavailable = 0
    total_failed = 0
    worst_situacao = None
    worst_unavail_rate = -1

    for situacao in sorted(by_situacao.keys(), key=int):
        data = by_situacao[situacao]
        tested = data["lots_tested"]
        unavailable = data["lots_unavailable"]
        failed = data["lots_failed"]
        success = data["lots_success"]
        unavail_rate = (unavailable / tested * 100) if tested > 0 else 0
        fail_rate = (failed / tested * 100) if tested > 0 else 0

        total_tested += tested
        total_unavailable += unavailable
        total_failed += failed

        if unavail_rate > worst_unavail_rate and tested > 0:
            worst_unavail_rate = unavail_rate
            worst_situacao = situacao

        label = SITUACAO_LABELS.get(int(situacao), "Desconhecido")
        print(f"\ncodigo_situacao={situacao} ({label})")
        print(f"  Auctions testados: {data['auctions_tested']}")
        print(f"  Lotes testados:    {tested}")
        print(f"  Sucessos:          {success}")
        print(f"  Indisponiveis:     {unavailable} ({unavail_rate:.1f}%)")
        print(f"  Erros reais:       {failed} ({fail_rate:.1f}%)")

        if data["errors"]:
            # Group errors by type
            error_types: dict[str, int] = defaultdict(int)
            for err in data["errors"]:
                error_msg = err["error"]
                # Simplify error message
                if "500" in error_msg:
                    error_types["HTTP 500 (Server Error)"] += 1
                elif "404" in error_msg:
                    error_types["HTTP 404 (Not Found)"] += 1
                elif "timeout" in error_msg.lower():
                    error_types["Timeout"] += 1
                else:
                    error_types["Other"] += 1

            print("  Tipos de erro:")
            for err_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
                print(f"    - {err_type}: {count}")

    # Conclusion
    print("\n" + "=" * 60)
    print("CONCLUSAO")
    print("=" * 60)

    total_unavail_rate = (total_unavailable / total_tested * 100) if total_tested > 0 else 0
    total_fail_rate = (total_failed / total_tested * 100) if total_tested > 0 else 0
    print(f"\nTotal de lotes testados:   {total_tested}")
    print(f"Total de indisponiveis:    {total_unavailable} ({total_unavail_rate:.1f}%)")
    print(f"Total de erros reais:      {total_failed} ({total_fail_rate:.1f}%)")

    if worst_situacao is not None:
        label = SITUACAO_LABELS.get(int(worst_situacao), "?")
        print(f"\nSituacao com MAIOR taxa de indisponibilidade: {worst_situacao} ({label}) - {worst_unavail_rate:.1f}%")

        # Check if unavailable lots are concentrated
        worst_data = by_situacao[worst_situacao]
        if total_unavailable > 0 and worst_data["lots_unavailable"] > total_unavailable * 0.5:
            print(f"\nHIPOTESE CONFIRMADA: >50% dos lotes indisponiveis estao em codigo_situacao={worst_situacao}")
        elif total_unavailable == 0:
            print("\nNenhum lote indisponivel (HTTP 422) encontrado na amostra")
        else:
            print("\nHipotese NAO confirmada: lotes indisponiveis distribuidos entre multiplas situacoes")

    # Timing
    timing = results.get("timing", {})
    print(f"\nTempo total: {timing.get('total', 0):.1f}s")
    print("=" * 60)


def save_results(results: dict, results_dir: Path) -> Path:
    """Save results to JSON file."""
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"debug_failed_lots_{timestamp}.json"
    filepath = results_dir / filename

    # Add metadata
    output = {
        **results,
        "_metadata": {
            "script": "debug_failed_lots.py",
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nResultados salvos: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Debug script to identify lot collection failure patterns by codigo_situacao"
    )
    parser.add_argument(
        "--auctions", "-a",
        type=int,
        default=DEFAULT_AUCTIONS_PER_SITUACAO,
        help=f"Auctions to test per situacao (default: {DEFAULT_AUCTIONS_PER_SITUACAO})",
    )
    parser.add_argument(
        "--lots", "-l",
        type=int,
        default=DEFAULT_LOTS_PER_AUCTION,
        help=f"Lots to test per auction (default: {DEFAULT_LOTS_PER_AUCTION})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress",
    )
    args = parser.parse_args()

    results = run_debug_sampling(
        auctions_per_situacao=args.auctions,
        lots_per_auction=args.lots,
        verbose=args.verbose,
    )

    print_report(results)

    # Save to tests/results/
    results_dir = ROOT_DIR / "tests" / "results"
    save_results(results, results_dir)


if __name__ == "__main__":
    main()
