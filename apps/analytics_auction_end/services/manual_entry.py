"""
Manual/CSV data entry for Auction End Results.

Provides alternative ways to input auction end data when PDF parsing is not possible.
"""

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import TextIO

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


class ManualAuctionEndEntry:
    """
    Manual data entry for auction end results.

    Provides methods to create auction end results from:
    - Direct method calls
    - CSV files
    - Dictionary data
    """

    @staticmethod
    def create_from_dict(data: dict) -> AuctionEndResult:
        """
        Create AuctionEndResult from a dictionary.

        Expected structure:
        {
            "edital": "0800100/000008/2025",
            "auction_date": "2025-12-05",
            "report_date": "2025-12-05 11:38",
            "lots": [
                {
                    "lot_number": 1,
                    "winner_cnpj": "60.530.186/0001-12",
                    "winner_name": "XP MONEY INFORMATICA E SERVICOS LTDA",
                    "winning_value": 112000.00
                },
                ...
            ]
        }
        """
        # Parse dates
        auction_date = ManualAuctionEndEntry._parse_date(data.get("auction_date", ""))
        report_date = ManualAuctionEndEntry._parse_date(data.get("report_date", ""))

        # Parse lots
        lot_results = []
        for lot_data in data.get("lots", []):
            winner = None
            if lot_data.get("winner_cnpj"):
                winner = WinnerInfo(
                    cnpj_cpf=lot_data["winner_cnpj"],
                    name=lot_data.get("winner_name", ""),
                )

            lot = LotResult(
                lot_number=lot_data["lot_number"],
                winner=winner,
                winning_value=lot_data.get("winning_value"),
            )
            lot_results.append(lot)

        return AuctionEndResult(
            edital=data.get("edital", "UNKNOWN"),
            auction_date=auction_date,
            report_date=report_date,
            lot_results=lot_results,
        )

    @staticmethod
    def create_from_csv(file_path: str | Path | TextIO) -> AuctionEndResult:
        """
        Create AuctionEndResult from a CSV file.

        Expected CSV format:
        edital,auction_date,report_date
        0800100/000008/2025,2025-12-05,2025-12-05 11:38

        lot_number,winner_cnpj,winner_name,winning_value
        1,,-,
        2,,-,
        3,60.530.186/0001-12,XP MONEY INFORMATICA E SERVICOS LTDA,112000.00
        ...
        """
        if isinstance(file_path, (str, Path)):
            with open(file_path, "r", encoding="utf-8") as f:
                return ManualAuctionEndEntry._parse_csv(f)
        else:
            return ManualAuctionEndEntry._parse_csv(file_path)

    @staticmethod
    def create_from_csv_string(csv_content: str) -> AuctionEndResult:
        """Create AuctionEndResult from CSV string content."""
        return ManualAuctionEndEntry._parse_csv(StringIO(csv_content))

    @staticmethod
    def create_simple_result(
        edital: str,
        auction_date: datetime,
        lots: list[tuple[int, str | None, str | None, float | None]],
    ) -> AuctionEndResult:
        """
        Create a simple AuctionEndResult.

        Args:
            edital: The edital number.
            auction_date: The auction date.
            lots: List of tuples (lot_number, winner_cnpj, winner_name, winning_value).

        Returns:
            AuctionEndResult with the provided data.
        """
        lot_results = []
        for lot_number, cnpj, name, value in lots:
            winner = None
            if cnpj and cnpj != "-":
                winner = WinnerInfo(cnpj_cpf=cnpj, name=name or "")

            lot = LotResult(
                lot_number=lot_number,
                winner=winner,
                winning_value=value if value and value > 0 else None,
            )
            lot_results.append(lot)

        return AuctionEndResult(
            edital=edital,
            auction_date=auction_date,
            report_date=datetime.now(),
            lot_results=lot_results,
        )

    @staticmethod
    def _parse_csv(file: TextIO) -> AuctionEndResult:
        """Parse CSV file and create AuctionEndResult."""
        reader = csv.reader(file)
        rows = list(reader)

        if len(rows) < 4:
            raise ValueError("CSV must have at least 4 rows (2 headers + data)")

        # First header row
        header1 = rows[0]
        if "edital" not in [h.lower() for h in header1]:
            raise ValueError("First row must contain 'edital' header")

        # First data row
        data1 = rows[1]
        edital = data1[0] if data1 else "UNKNOWN"
        auction_date = ManualAuctionEndEntry._parse_date(data1[1] if len(data1) > 1 else "")
        report_date = ManualAuctionEndEntry._parse_date(data1[2] if len(data1) > 2 else "")

        # Skip empty row and second header
        lots_start = 3
        for i in range(2, len(rows)):
            if "lot_number" in [h.lower().strip() for h in rows[i]]:
                lots_start = i + 1
                break

        # Parse lots
        lot_results = []
        for row in rows[lots_start:]:
            if not row or not row[0].strip():
                continue

            try:
                lot_number = int(row[0])
            except ValueError:
                continue

            winner = None
            cnpj = row[1].strip() if len(row) > 1 else ""
            name = row[2].strip() if len(row) > 2 else ""
            value_str = row[3].strip() if len(row) > 3 else ""

            if cnpj and cnpj != "-":
                winner = WinnerInfo(cnpj_cpf=cnpj, name=name)

            winning_value = None
            if value_str and value_str != "-":
                try:
                    # Handle Brazilian number format
                    cleaned = value_str.replace(".", "").replace(",", ".")
                    winning_value = float(cleaned)
                except ValueError:
                    pass

            lot = LotResult(
                lot_number=lot_number,
                winner=winner,
                winning_value=winning_value,
            )
            lot_results.append(lot)

        return AuctionEndResult(
            edital=edital,
            auction_date=auction_date,
            report_date=report_date,
            lot_results=lot_results,
        )

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse date from various formats."""
        if not date_str:
            return datetime.now()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return datetime.now()


# Convenience function
def create_auction_end_from_data(data: dict) -> AuctionEndResult:
    """Convenience function to create AuctionEndResult from dictionary."""
    return ManualAuctionEndEntry.create_from_dict(data)
