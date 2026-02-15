"""
PostgreSQL implementation of AuctionEndStorage.
"""

from typing import Optional

from shared.domain.auction_end.entities import (
    AuctionEndResult,
    BidHistoryEntry,
    LotResult,
    Proposal,
)
from shared.domain.auction_end.value_objects import (
    BidStatus,
    ProposalStatus,
    WinnerInfo,
)
from shared.infrastructure.postgres import (
    PostgresConnectionPool,
    ensure_schema,
    get_pool,
    with_postgres_connection,
)
from shared.ports.auction_end_storage import AuctionEndStorage


class PostgresAuctionEndStorage(AuctionEndStorage):
    """PostgreSQL implementation for auction end results storage."""

    def __init__(
        self, pool: PostgresConnectionPool | None = None, auto_schema: bool = True
    ):
        self.pool = pool or get_pool()
        if auto_schema:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure the auction_end schema is applied."""
        try:
            ensure_schema(self.pool, "")
        except Exception:
            # Ignore errors - schema might already exist or have permission issues
            pass

    # === AUCTION END RESULT ===
    def get_by_edital(self, edital: str) -> Optional[AuctionEndResult]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, edital, auction_id, auction_date, report_date, created_at
                    FROM auction_end_results
                    WHERE edital = %s
                    """,
                    (edital,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_auction_end_result(row)

    def get_by_auction_id(self, auction_id: int) -> Optional[AuctionEndResult]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, edital, auction_id, auction_date, report_date, created_at
                    FROM auction_end_results
                    WHERE auction_id = %s
                    """,
                    (auction_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_auction_end_result(row)

    def create(self, result: AuctionEndResult) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auction_end_results (edital, auction_id, auction_date, report_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        result.edital,
                        result.auction_id,
                        result.auction_date,
                        result.report_date,
                    ),
                )
                return cur.fetchone()[0]

    def update(self, result: AuctionEndResult) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE auction_end_results
                    SET edital = %s, auction_id = %s, auction_date = %s, report_date = %s
                    WHERE id = %s
                    """,
                    (
                        result.edital,
                        result.auction_id,
                        result.auction_date,
                        result.report_date,
                        result.id,
                    ),
                )

    def delete(self, result_id: int) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Delete in order: bid_history -> proposals -> lot_results -> auction_end
                cur.execute(
                    """
                    DELETE FROM auction_end_bid_history
                    WHERE lot_result_id IN (
                        SELECT id FROM auction_end_lot_results
                        WHERE auction_end_result_id = %s
                    )
                    """,
                    (result_id,),
                )
                cur.execute(
                    """
                    DELETE FROM auction_end_proposals
                    WHERE lot_result_id IN (
                        SELECT id FROM auction_end_lot_results
                        WHERE auction_end_result_id = %s
                    )
                    """,
                    (result_id,),
                )
                cur.execute(
                    "DELETE FROM auction_end_lot_results WHERE auction_end_result_id = %s",
                    (result_id,),
                )
                cur.execute(
                    "DELETE FROM auction_end_results WHERE id = %s", (result_id,)
                )

    # === LOT RESULT ===
    def get_lot_results(self, auction_end_id: int) -> list[LotResult]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, auction_end_result_id, lot_number,
                           winner_cnpj_cpf, winner_name, winning_value
                    FROM auction_end_lot_results
                    WHERE auction_end_result_id = %s
                    ORDER BY lot_number
                    """,
                    (auction_end_id,),
                )
                return [self._row_to_lot_result(row) for row in cur.fetchall()]

    def get_lot_result_by_number(
        self, auction_end_id: int, lot_number: int
    ) -> Optional[LotResult]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, auction_end_result_id, lot_number,
                           winner_cnpj_cpf, winner_name, winning_value
                    FROM auction_end_lot_results
                    WHERE auction_end_result_id = %s AND lot_number = %s
                    """,
                    (auction_end_id, lot_number),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_lot_result(row)

    def create_lot_result(self, lot: LotResult, auction_end_id: int) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auction_end_lot_results (
                        auction_end_result_id, lot_number,
                        winner_cnpj_cpf, winner_name, winning_value
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        auction_end_id,
                        lot.lot_number,
                        lot.winner.cnpj_cpf if lot.winner else None,
                        lot.winner.name if lot.winner else None,
                        lot.winning_value,
                    ),
                )
                return cur.fetchone()[0]

    # === PROPOSAL ===
    def get_proposals(self, lot_result_id: int) -> list[Proposal]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, lot_result_id, bidder_id, status, value, timestamp
                    FROM auction_end_proposals
                    WHERE lot_result_id = %s
                    ORDER BY timestamp
                    """,
                    (lot_result_id,),
                )
                return [self._row_to_proposal(row) for row in cur.fetchall()]

    def create_proposal(self, proposal: Proposal, lot_result_id: int) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auction_end_proposals (
                        lot_result_id, bidder_id, status, value, timestamp
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        lot_result_id,
                        proposal.bidder_id,
                        proposal.status.value,
                        proposal.value,
                        proposal.timestamp,
                    ),
                )
                return cur.fetchone()[0]

    # === BID HISTORY ===
    def get_bid_history(self, lot_result_id: int) -> list[BidHistoryEntry]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, lot_result_id, sequence, timestamp, value, status, bidder_id
                    FROM auction_end_bid_history
                    WHERE lot_result_id = %s
                    ORDER BY sequence
                    """,
                    (lot_result_id,),
                )
                return [self._row_to_bid_history(row) for row in cur.fetchall()]

    def create_bid_history_entry(
        self, entry: BidHistoryEntry, lot_result_id: int
    ) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auction_end_bid_history (
                        lot_result_id, sequence, timestamp, value, status, bidder_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        lot_result_id,
                        entry.sequence,
                        entry.timestamp,
                        entry.value,
                        entry.status.value,
                        entry.bidder_id,
                    ),
                )
                return cur.fetchone()[0]

    # === BULK OPERATIONS ===
    def list_all(self) -> list[AuctionEndResult]:
        """List all saved auction end results."""
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT aer.id, aer.edital, aer.auction_id, aer.auction_date,
                           aer.report_date, aer.created_at,
                           COUNT(aelr.id) as total_lots,
                           COUNT(aelr.id) FILTER (WHERE aelr.winner_cnpj_cpf IS NOT NULL) as lots_with_winner,
                           COALESCE(SUM(aelr.winning_value), 0) as total_value
                    FROM auction_end_results aer
                    LEFT JOIN auction_end_lot_results aelr ON aer.id = aelr.auction_end_result_id
                    GROUP BY aer.id, aer.edital, aer.auction_id, aer.auction_date,
                             aer.report_date, aer.created_at
                    ORDER BY aer.created_at DESC
                    """
                )
                results = []
                for row in cur.fetchall():
                    result = AuctionEndResult(
                        id=row[0],
                        edital=row[1],
                        auction_id=row[2],
                        auction_date=row[3],
                        report_date=row[4],
                        created_at=row[5],
                    )
                    # Store summary info as attributes for display
                    result._total_lots = row[6]
                    result._lots_with_winner = row[7]
                    result._total_value = float(row[8]) if row[8] else 0.0
                    results.append(result)
                return results

    def save_full_result(self, result: AuctionEndResult) -> int:
        """Save complete auction end result in a single transaction."""
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Check if exists and delete if so
                cur.execute(
                    "SELECT id FROM auction_end_results WHERE edital = %s",
                    (result.edital,),
                )
                existing = cur.fetchone()
                if existing:
                    self._delete_cascade(cur, existing[0])

                # Insert auction end result
                cur.execute(
                    """
                    INSERT INTO auction_end_results (edital, auction_id, auction_date, report_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        result.edital,
                        result.auction_id,
                        result.auction_date,
                        result.report_date,
                    ),
                )
                result_id = cur.fetchone()[0]

                # Insert lot results
                for lot in result.lot_results:
                    cur.execute(
                        """
                        INSERT INTO auction_end_lot_results (
                            auction_end_result_id, lot_number,
                            winner_cnpj_cpf, winner_name, winning_value
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            result_id,
                            lot.lot_number,
                            lot.winner.cnpj_cpf if lot.winner else None,
                            lot.winner.name if lot.winner else None,
                            lot.winning_value,
                        ),
                    )
                    lot_id = cur.fetchone()[0]

                    # Insert proposals
                    for proposal in lot.proposals:
                        cur.execute(
                            """
                            INSERT INTO auction_end_proposals (
                                lot_result_id, bidder_id, status, value, timestamp
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                lot_id,
                                proposal.bidder_id,
                                proposal.status.value,
                                proposal.value,
                                proposal.timestamp,
                            ),
                        )

                    # Insert bid history
                    for entry in lot.bid_history:
                        cur.execute(
                            """
                            INSERT INTO auction_end_bid_history (
                                lot_result_id, sequence, timestamp, value, status, bidder_id
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                lot_id,
                                entry.sequence,
                                entry.timestamp,
                                entry.value,
                                entry.status.value,
                                entry.bidder_id,
                            ),
                        )

                return result_id

    def _delete_cascade(self, cur, result_id: int) -> None:
        """Delete all related data for an auction end result."""
        cur.execute(
            """
            DELETE FROM auction_end_bid_history
            WHERE lot_result_id IN (
                SELECT id FROM auction_end_lot_results
                WHERE auction_end_result_id = %s
            )
            """,
            (result_id,),
        )
        cur.execute(
            """
            DELETE FROM auction_end_proposals
            WHERE lot_result_id IN (
                SELECT id FROM auction_end_lot_results
                WHERE auction_end_result_id = %s
            )
            """,
            (result_id,),
        )
        cur.execute(
            "DELETE FROM auction_end_lot_results WHERE auction_end_result_id = %s",
            (result_id,),
        )
        cur.execute("DELETE FROM auction_end_results WHERE id = %s", (result_id,))

    # === CONNECTION ===
    def closeall(self) -> None:
        self.pool.closeall()

    # === PRIVATE HELPERS ===
    def _row_to_auction_end_result(self, row: tuple) -> AuctionEndResult:
        return AuctionEndResult(
            id=row[0],
            edital=row[1],
            auction_id=row[2],
            auction_date=row[3],
            report_date=row[4],
            created_at=row[5],
        )

    def _row_to_lot_result(self, row: tuple) -> LotResult:
        winner = None
        if row[3] and row[4]:
            winner = WinnerInfo(cnpj_cpf=row[3], name=row[4])
        elif row[3]:
            winner = WinnerInfo(cnpj_cpf=row[3], name="")

        return LotResult(
            id=row[0],
            auction_end_result_id=row[1],
            lot_number=row[2],
            winner=winner,
            winning_value=float(row[5]) if row[5] else None,
        )

    def _row_to_proposal(self, row: tuple) -> Proposal:
        return Proposal(
            id=row[0],
            lot_result_id=row[1],
            bidder_id=row[2],
            status=ProposalStatus.from_string(row[3]),
            value=float(row[4]),
            timestamp=row[5],
        )

    def _row_to_bid_history(self, row: tuple) -> BidHistoryEntry:
        return BidHistoryEntry(
            id=row[0],
            lot_result_id=row[1],
            sequence=row[2],
            timestamp=row[3],
            value=float(row[4]),
            status=BidStatus.from_string(row[5]),
            bidder_id=row[6],
        )
