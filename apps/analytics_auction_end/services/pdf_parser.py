"""
PDF Parser for Auction End Results (Relatório Relação de Vencedores).

Extracts structured data from RFB auction winner reports.

Supports:
- Text-based PDFs (direct extraction)
- Vector/image-based PDFs (OCR extraction with Tesseract)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional
import io

import pdfplumber

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

# Optional OCR imports
try:
    from pdf2image import convert_from_path, convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class AuctionEndPDFParser:
    """
    Parser for 'Relatório Relação de Vencedores' PDF files.

    Extracts:
    - Edital number and dates
    - Lot results with winner info
    - Proposals (Relação de Propostas)
    - Bid history (Histórico de Lances)
    """

    # Regex patterns for extraction
    EDITAL_PATTERN = re.compile(r"Edital\s+N[ºo°]\s*(\d{7}/\d{6}/\d{4})")
    DATE_PATTERN = re.compile(r"REALIZADO\s+EM\s+(\d{2}/\d{2}/\d{4})")
    REPORT_DATE_PATTERN = re.compile(r"Data:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})")
    LOT_HEADER_PATTERN = re.compile(r"Lote:(\d+)")
    WINNER_PATTERN = re.compile(r"Vencedor:(.+)")
    VALUE_PATTERN = re.compile(r"Valor:\s*([\d.,]+|-)")

    def __init__(self, max_pages: int | None = None, use_ocr: bool = True):
        """
        Initialize the parser.

        Args:
            max_pages: Maximum number of pages to parse (None for all).
            use_ocr: Whether to use OCR if text extraction fails.
        """
        self.max_pages = max_pages
        self.use_ocr = use_ocr

    def parse_file(self, file_path: str | Path) -> AuctionEndResult:
        """
        Parse a PDF file and extract auction end results.

        Args:
            file_path: Path to the PDF file.

        Returns:
            AuctionEndResult with all extracted data.
        """
        with pdfplumber.open(file_path) as pdf:
            return self._parse_pdf(pdf)

    def parse_bytes(self, pdf_bytes: BinaryIO) -> AuctionEndResult:
        """
        Parse PDF from bytes/file-like object.

        Args:
            pdf_bytes: File-like object containing PDF data.

        Returns:
            AuctionEndResult with all extracted data.
        """
        with pdfplumber.open(pdf_bytes) as pdf:
            return self._parse_pdf(pdf)

    def _parse_pdf(self, pdf: pdfplumber.PDF) -> AuctionEndResult:
        """Parse opened PDF and extract all data."""
        # Determine pages to process
        pages_to_process = pdf.pages
        if self.max_pages:
            pages_to_process = pages_to_process[: self.max_pages]

        # Try text extraction first
        first_page_text = pages_to_process[0].extract_text() or ""

        # Check if text extraction worked
        all_text = ""
        all_tables = []

        if first_page_text.strip():
            # Text extraction worked, use it
            for page in pages_to_process:
                all_text += (page.extract_text() or "") + "\n"
                tables = page.extract_tables()
                all_tables.extend(tables)
        elif self.use_ocr and OCR_AVAILABLE:
            # Try OCR extraction
            all_text = self._extract_text_with_ocr(pdf.path)
        else:
            # No text and OCR not available
            if not OCR_AVAILABLE:
                raise ValueError(
                    "PDF has no extractable text and OCR is not available. "
                    "Install Tesseract OCR and run: pip install pdf2image pytesseract"
                )
            else:
                raise ValueError("PDF has no extractable text.")

        # Extract header info
        edital = self._extract_edital(all_text)
        auction_date = self._extract_auction_date(all_text)
        report_date = self._extract_report_date(all_text)

        # Parse lot results from text
        lot_results = self._parse_lot_results(all_text, all_tables)

        return AuctionEndResult(
            edital=edital,
            auction_date=auction_date,
            report_date=report_date,
            lot_results=lot_results,
        )

    def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """Extract text using OCR (requires Tesseract)."""
        if not OCR_AVAILABLE:
            raise ValueError("OCR not available. Install pdf2image and pytesseract.")

        try:
            # Convert PDF pages to images
            images = convert_from_path(
                pdf_path,
                first_page=1,
                last_page=self.max_pages if self.max_pages else None,
                dpi=300,  # Higher DPI for better OCR
            )

            # OCR each image
            all_text = ""
            for i, image in enumerate(images):
                # Use Portuguese language if available
                try:
                    text = pytesseract.image_to_string(image, lang='por')
                except Exception:
                    text = pytesseract.image_to_string(image)
                all_text += text + "\n"

            return all_text
        except Exception as e:
            raise ValueError(
                f"OCR extraction failed: {e}. "
                "Make sure Tesseract OCR is installed on your system."
            )

    def _extract_edital(self, text: str) -> str:
        """Extract edital number from text."""
        match = self.EDITAL_PATTERN.search(text)
        if match:
            return match.group(1)
        return "UNKNOWN"

    def _extract_auction_date(self, text: str) -> datetime:
        """Extract auction date from text."""
        match = self.DATE_PATTERN.search(text)
        if match:
            return datetime.strptime(match.group(1), "%d/%m/%Y")
        return datetime.now()

    def _extract_report_date(self, text: str) -> datetime:
        """Extract report generation date from text."""
        match = self.REPORT_DATE_PATTERN.search(text)
        if match:
            return datetime.strptime(match.group(1), "%d/%m/%Y %H:%M")
        return datetime.now()

    def _parse_lot_results(
        self, text: str, tables: list[list[list[str]]]
    ) -> list[LotResult]:
        """Parse lot results from extracted text and tables."""
        lot_results = []

        # Split text into sections by lot headers
        lines = text.split("\n")
        current_lot = None
        current_section = "header"  # header, proposals, bids
        pending_winner = None  # Winner info found before lot line

        proposals_data = []
        bids_data = []

        for i, line in enumerate(lines):
            line = line.strip()

            # Check for winner info BEFORE lot line (PDF layout quirk)
            # Pattern: "Vencedor:60.530.186/0001-12 - XP MONEY"
            winner_match = self.WINNER_PATTERN.search(line)
            if winner_match and "Lote:" not in line:
                winner_str = winner_match.group(1).strip()
                # Look ahead for continuation (company name may span lines)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # If next line doesn't start with Lote: or Valor:, append it
                    if (next_line and
                        not next_line.startswith("Lote:") and
                        not next_line.startswith("Valor:") and
                        not next_line.startswith("Vencedor:") and
                        "Relação" not in next_line):
                        winner_str += " " + next_line
                pending_winner = WinnerInfo.from_string(winner_str)
                continue

            # Check for lot header
            lot_match = self.LOT_HEADER_PATTERN.search(line)
            if lot_match:
                # Save previous lot if exists
                if current_lot is not None:
                    current_lot.proposals = proposals_data
                    current_lot.bid_history = bids_data
                    lot_results.append(current_lot)

                # Start new lot
                lot_number = int(lot_match.group(1))

                # Use pending winner if available, otherwise try to extract from line
                if pending_winner:
                    winner_info = pending_winner
                    pending_winner = None
                else:
                    winner_info = self._extract_winner_from_line(line, lines, i)

                winning_value = self._extract_value_from_line(line, lines, i)

                current_lot = LotResult(
                    lot_number=lot_number,
                    winner=winner_info,
                    winning_value=winning_value,
                )
                proposals_data = []
                bids_data = []
                current_section = "header"
                continue

            # Check for section markers
            if "Relação de Propostas" in line or "Relacao de Propostas" in line:
                current_section = "proposals"
                continue
            if "Histórico de Lances" in line or "Historico de Lances" in line:
                current_section = "bids"
                continue

        # Don't forget last lot
        if current_lot is not None:
            current_lot.proposals = proposals_data
            current_lot.bid_history = bids_data
            lot_results.append(current_lot)

        # Deduplicate lots by lot_number (keep the one with most data)
        lot_results = self._deduplicate_lots(lot_results)

        # Now parse tables to extract detailed proposal and bid data
        self._enrich_from_tables(lot_results, tables)

        return lot_results

    def _deduplicate_lots(self, lot_results: list[LotResult]) -> list[LotResult]:
        """Remove duplicate lots, keeping the one with winner info."""
        seen = {}
        for lot in lot_results:
            if lot.lot_number not in seen:
                seen[lot.lot_number] = lot
            else:
                # Keep the one with winner info
                existing = seen[lot.lot_number]
                if lot.winner and not existing.winner:
                    seen[lot.lot_number] = lot
                elif lot.winning_value and not existing.winning_value:
                    # Transfer winning value if missing
                    existing.winning_value = lot.winning_value
                    if lot.winner:
                        seen[lot.lot_number].winner = lot.winner
        return list(seen.values())

    def _extract_winner_from_line(
        self, line: str, lines: list[str], index: int
    ) -> WinnerInfo | None:
        """Extract winner info from lot header line or nearby lines."""
        # Check current line
        winner_match = self.WINNER_PATTERN.search(line)
        if winner_match:
            winner_str = winner_match.group(1).strip()
            return WinnerInfo.from_string(winner_str)

        # Check next few lines for winner info
        for j in range(index + 1, min(index + 3, len(lines))):
            next_line = lines[j].strip()
            winner_match = self.WINNER_PATTERN.search(next_line)
            if winner_match:
                winner_str = winner_match.group(1).strip()
                return WinnerInfo.from_string(winner_str)
            # Also check for CNPJ pattern directly
            if re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", next_line):
                return WinnerInfo.from_string(next_line)

        return None

    def _extract_value_from_line(
        self, line: str, lines: list[str], index: int
    ) -> float | None:
        """Extract winning value from lot header line or nearby lines."""
        # Check current line
        value_match = self.VALUE_PATTERN.search(line)
        if value_match:
            return self._parse_value(value_match.group(1))

        # Check next few lines
        for j in range(index + 1, min(index + 3, len(lines))):
            next_line = lines[j].strip()
            value_match = self.VALUE_PATTERN.search(next_line)
            if value_match:
                return self._parse_value(value_match.group(1))

        return None

    def _parse_value(self, value_str: str) -> float | None:
        """Parse monetary value string to float."""
        if not value_str or value_str.strip() == "-":
            return None
        # Brazilian format: 1.000.000,00
        cleaned = value_str.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _enrich_from_tables(
        self, lot_results: list[LotResult], tables: list[list[list[str]]]
    ) -> None:
        """Enrich lot results with data from extracted tables."""
        # Create a mapping of lot_number to LotResult for easy lookup
        lot_map = {lot.lot_number: lot for lot in lot_results}

        # Track current lot based on lots that have winners (only they have tables)
        lots_with_winners = [lot for lot in lot_results if lot.has_winner]
        current_lot_idx = 0

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Identify table type by checking both header row and second row
            header = [str(cell).lower() if cell else "" for cell in table[0]]
            header_str = " ".join(header)

            # Check second row too (pdfplumber sometimes puts section title in row 0)
            second_row = [str(cell).lower() if cell else "" for cell in table[1]] if len(table) > 1 else []
            second_row_str = " ".join(second_row)

            if "proponente" in header_str and "status" in header_str:
                # This is a proposals table - assign to current lot with winner
                if current_lot_idx < len(lots_with_winners):
                    self._parse_proposals_table(
                        lots_with_winners[current_lot_idx], table
                    )
            elif ("historico" in header_str or "histórico" in header_str) and "lance" in header_str:
                # This is a bid history table (header has "Histórico de Lances")
                # Skip if table has fewer than 3 rows (header + subheader + at least 1 data row)
                if len(table) >= 3 and current_lot_idx < len(lots_with_winners):
                    self._parse_bids_table(lots_with_winners[current_lot_idx], table)
                    # Move to next lot with winner after bid history
                    current_lot_idx += 1
            elif "seq" in second_row_str and "lance" in second_row_str:
                # Alternative: second row has "Seq." and "Lance" (real column headers)
                if len(table) >= 3 and current_lot_idx < len(lots_with_winners):
                    self._parse_bids_table(lots_with_winners[current_lot_idx], table)
                    # Move to next lot with winner after bid history
                    current_lot_idx += 1

    def _parse_proposals_table(
        self, lot_result: LotResult, table: list[list[str]]
    ) -> None:
        """Parse proposals table and add to lot result."""
        # Skip header row
        for row in table[1:]:
            if len(row) < 4:
                continue

            try:
                bidder_id = str(row[0]).strip() if row[0] else ""
                status_str = str(row[1]).strip() if row[1] else ""
                value_str = str(row[2]).strip() if row[2] else "0"
                datetime_str = str(row[3]).strip() if row[3] else ""

                if not bidder_id or not bidder_id.startswith("licitante"):
                    continue

                proposal = Proposal(
                    bidder_id=bidder_id,
                    status=ProposalStatus.from_string(status_str),
                    value=self._parse_value(value_str) or 0.0,
                    timestamp=self._parse_datetime(datetime_str),
                )
                lot_result.proposals.append(proposal)
            except (ValueError, IndexError):
                continue

    def _parse_bids_table(
        self, lot_result: LotResult, table: list[list[str]]
    ) -> None:
        """Parse bid history table and add to lot result."""
        # Skip header row
        for row in table[1:]:
            if len(row) < 5:
                continue

            try:
                seq_str = str(row[0]).strip() if row[0] else "0"
                datetime_str = str(row[1]).strip() if row[1] else ""
                value_str = str(row[2]).strip() if row[2] else "0"
                status_str = str(row[3]).strip() if row[3] else ""
                bidder_id = str(row[4]).strip() if row[4] else ""

                # Skip if not valid data
                if not seq_str.isdigit():
                    continue

                entry = BidHistoryEntry(
                    sequence=int(seq_str),
                    timestamp=self._parse_datetime(datetime_str),
                    value=self._parse_value(value_str) or 0.0,
                    status=BidStatus.from_string(status_str),
                    bidder_id=bidder_id,
                )
                lot_result.bid_history.append(entry)
            except (ValueError, IndexError):
                continue

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string from various formats."""
        if not datetime_str:
            return datetime.now()

        formats = [
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

        return datetime.now()
