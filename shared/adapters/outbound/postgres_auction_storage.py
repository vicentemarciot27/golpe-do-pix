import json
from dataclasses import replace
from typing import Optional
from uuid import UUID

from shared.ports.auction_storage import AuctionStorage
from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata
from shared.infrastructure.postgres import get_pool, with_postgres_connection, PostgresConnectionPool


class PostgresAuctionStorage(AuctionStorage):
    """Implementação PostgreSQL do AuctionStorage."""

    def __init__(self, pool: PostgresConnectionPool | None = None):
        self.pool = pool or get_pool()

    # === AUCTION ===
    def get_auction_by_edle(self, edle: str) -> Optional[Auction]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, edital, edle, tipo, orgao, cidade, unidade_nome,
                           codigo_situacao, permite_pf, data_inicio_propostas,
                           data_fim_propostas, data_abertura_lances, total_lotes,
                           mercadorias_apreendidas, data_classificacao, forma_contato,
                           dados_publicacao, numero_recursos, numero_avisos,
                           numero_erratas, data_hash, is_active
                    FROM auctions WHERE edle = %s
                """, (edle,))
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_auction(row)

    def get_active_auction_edles(self) -> set[str]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT edle FROM auctions WHERE is_active = TRUE")
                return {row[0] for row in cur.fetchall()}

    def create_auction(self, auction: Auction, data_hash: str) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO auctions (
                        edital, edle, tipo, orgao, cidade, unidade_nome,
                        codigo_situacao, permite_pf, data_inicio_propostas,
                        data_fim_propostas, data_abertura_lances, total_lotes,
                        mercadorias_apreendidas, data_classificacao, forma_contato,
                        dados_publicacao, numero_recursos, numero_avisos,
                        numero_erratas, data_hash, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    auction.edital, auction.edle, auction.tipo, auction.orgao,
                    auction.cidade, auction.unidade_nome, auction.codigo_situacao,
                    auction.permite_pf, auction.data_inicio_propostas,
                    auction.data_fim_propostas, auction.data_abertura_lances,
                    auction.total_lotes, auction.mercadorias_apreendidas,
                    auction.data_classificacao, auction.forma_contato,
                    auction.dados_publicacao, auction.numero_recursos,
                    auction.numero_avisos, auction.numero_erratas,
                    data_hash, auction.is_active
                ))
                return cur.fetchone()[0]

    def update_auction(self, auction: Auction, data_hash: str) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE auctions SET
                        edital = %s, tipo = %s, orgao = %s, cidade = %s,
                        unidade_nome = %s, codigo_situacao = %s, permite_pf = %s,
                        data_inicio_propostas = %s, data_fim_propostas = %s,
                        data_abertura_lances = %s, total_lotes = %s,
                        mercadorias_apreendidas = %s, data_classificacao = %s,
                        forma_contato = %s, dados_publicacao = %s,
                        numero_recursos = %s, numero_avisos = %s,
                        numero_erratas = %s, data_hash = %s, is_active = %s
                    WHERE id = %s
                """, (
                    auction.edital, auction.tipo, auction.orgao, auction.cidade,
                    auction.unidade_nome, auction.codigo_situacao, auction.permite_pf,
                    auction.data_inicio_propostas, auction.data_fim_propostas,
                    auction.data_abertura_lances, auction.total_lotes,
                    auction.mercadorias_apreendidas, auction.data_classificacao,
                    auction.forma_contato, auction.dados_publicacao,
                    auction.numero_recursos, auction.numero_avisos,
                    auction.numero_erratas, data_hash, auction.is_active,
                    auction.id
                ))

    def soft_delete_auctions(self, edles: set[str], batch_id: UUID) -> int:
        if not edles:
            return 0
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Get IDs before updating for audit
                cur.execute(
                    "SELECT id FROM auctions WHERE edle = ANY(%s) AND is_active = TRUE",
                    (list(edles),)
                )
                ids = [row[0] for row in cur.fetchall()]

                if not ids:
                    return 0

                # Soft delete
                cur.execute(
                    "UPDATE auctions SET is_active = FALSE WHERE id = ANY(%s)",
                    (ids,)
                )

                # Record audit for each
                for auction_id in ids:
                    cur.execute("""
                        INSERT INTO auction_audit (entity_type, entity_id, action, sync_batch_id)
                        VALUES ('auction', %s, 'DELETE', %s)
                    """, (auction_id, str(batch_id)))

                return len(ids)

    def update_auction_error(self, edle: str, error_status: str, error_message: str) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE auctions SET error_status = %s, error_message = %s
                    WHERE edle = %s
                """, (error_status, error_message, edle))

    # === LOT ===
    def get_lot_by_rfb_id(self, auction_id: int, rfb_id: int) -> Optional[Lot]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, auction_id, rfb_id, numero, edle, edital, tipo,
                           orgao, cidade, valor_minimo, situacao_lote, situacao_edital,
                           tipo_edital, permite_pf, possui_imagens, destaque,
                           nr_avisos, nr_erratas, data_hash, is_active
                    FROM lots WHERE auction_id = %s AND rfb_id = %s
                """, (auction_id, rfb_id))
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_lot(row)

    def get_active_lot_rfb_ids(self, auction_id: int) -> set[int]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rfb_id FROM lots WHERE auction_id = %s AND is_active = TRUE",
                    (auction_id,)
                )
                return {row[0] for row in cur.fetchall()}

    def create_lot(self, lot: Lot, auction_id: int, data_hash: str) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO lots (
                        auction_id, rfb_id, numero, edle, edital, tipo, orgao,
                        cidade, valor_minimo, situacao_lote, situacao_edital,
                        tipo_edital, permite_pf, possui_imagens, destaque,
                        nr_avisos, nr_erratas, data_hash, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    auction_id, lot.rfb_id, lot.numero, lot.edle, lot.edital,
                    lot.tipo, lot.orgao, lot.cidade, lot.valor_minimo,
                    lot.situacao_lote, lot.situacao_edital, lot.tipo_edital,
                    lot.permite_pf, lot.possui_imagens, lot.destaque,
                    lot.nr_avisos, lot.nr_erratas, data_hash, lot.is_active
                ))
                return cur.fetchone()[0]

    def update_lot(self, lot: Lot, data_hash: str) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE lots SET
                        numero = %s, edle = %s, edital = %s, tipo = %s, orgao = %s,
                        cidade = %s, valor_minimo = %s, situacao_lote = %s,
                        situacao_edital = %s, tipo_edital = %s, permite_pf = %s,
                        possui_imagens = %s, destaque = %s, nr_avisos = %s,
                        nr_erratas = %s, data_hash = %s, is_active = %s
                    WHERE id = %s
                """, (
                    lot.numero, lot.edle, lot.edital, lot.tipo, lot.orgao,
                    lot.cidade, lot.valor_minimo, lot.situacao_lote,
                    lot.situacao_edital, lot.tipo_edital, lot.permite_pf,
                    lot.possui_imagens, lot.destaque, lot.nr_avisos,
                    lot.nr_erratas, data_hash, lot.is_active, lot.id
                ))

    def soft_delete_lots(self, auction_id: int, rfb_ids: set[int], batch_id: UUID) -> int:
        if not rfb_ids:
            return 0
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Get IDs before updating for audit
                cur.execute(
                    "SELECT id FROM lots WHERE auction_id = %s AND rfb_id = ANY(%s) AND is_active = TRUE",
                    (auction_id, list(rfb_ids))
                )
                ids = [row[0] for row in cur.fetchall()]

                if not ids:
                    return 0

                # Soft delete
                cur.execute(
                    "UPDATE lots SET is_active = FALSE WHERE id = ANY(%s)",
                    (ids,)
                )

                # Record audit for each
                for lot_id in ids:
                    cur.execute("""
                        INSERT INTO auction_audit (entity_type, entity_id, action, sync_batch_id)
                        VALUES ('lot', %s, 'DELETE', %s)
                    """, (lot_id, str(batch_id)))

                return len(ids)

    # === ITEM ===
    def get_item_by_index(self, lot_id: int, item_index: int) -> Optional[Item]:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, lot_id, item_index, recinto_armazenador, quantidade,
                           unidade_medida, descricao, nr_referencia, data_hash, is_active
                    FROM items WHERE lot_id = %s AND item_index = %s
                """, (lot_id, item_index))
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_item(row)

    def create_item(self, item: Item, lot_id: int, item_index: int, data_hash: str) -> int:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO items (
                        lot_id, item_index, recinto_armazenador, quantidade,
                        unidade_medida, descricao, nr_referencia, data_hash, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    lot_id, item_index, item.recinto_armazenador, item.quantidade,
                    item.unidade_medida, item.descricao, item.nr_referencia,
                    data_hash, item.is_active
                ))
                return cur.fetchone()[0]

    def update_item(self, item: Item, data_hash: str) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE items SET
                        recinto_armazenador = %s, quantidade = %s, unidade_medida = %s,
                        descricao = %s, nr_referencia = %s, data_hash = %s, is_active = %s
                    WHERE id = %s
                """, (
                    item.recinto_armazenador, item.quantidade, item.unidade_medida,
                    item.descricao, item.nr_referencia, data_hash, item.is_active,
                    item.id
                ))

    def replace_items_for_lot(self, lot_id: int, items: list[Item], batch_id: UUID) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Delete existing items
                cur.execute("DELETE FROM items WHERE lot_id = %s", (lot_id,))

                # Insert new items
                for idx, item in enumerate(items):
                    cur.execute("""
                        INSERT INTO items (
                            lot_id, item_index, recinto_armazenador, quantidade,
                            unidade_medida, descricao, nr_referencia, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        lot_id, idx, item.recinto_armazenador, item.quantidade,
                        item.unidade_medida, item.descricao, item.nr_referencia,
                        item.is_active
                    ))

    # === LOT IMAGE ===
    def replace_images_for_lot(self, lot_id: int, images: list[LotImage]) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Delete existing images
                cur.execute("DELETE FROM lot_images WHERE lot_id = %s", (lot_id,))

                # Insert new images
                for image in images:
                    cur.execute("""
                        INSERT INTO lot_images (
                            lot_id, rfb_id, url, thumbnail_url, width, height,
                            is_featured, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        lot_id, image.rfb_id, image.url, image.thumbnail_url,
                        image.width, image.height, image.is_featured, image.is_active
                    ))

    # === AVISO/ERRATA ===
    def replace_avisos_for_auction(self, auction_id: int, avisos: list[AvisoErrata]) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Delete existing avisos for auction
                cur.execute("DELETE FROM avisos_erratas WHERE auction_id = %s", (auction_id,))

                # Insert new avisos
                for aviso in avisos:
                    cur.execute("""
                        INSERT INTO avisos_erratas (
                            auction_id, lot_id, data, codigo_tipo, tipo, texto, is_active
                        ) VALUES (%s, NULL, %s, %s, %s, %s, %s)
                    """, (
                        auction_id, aviso.data, aviso.codigo_tipo, aviso.tipo,
                        aviso.texto, aviso.is_active
                    ))

    def replace_avisos_for_lot(self, lot_id: int, avisos: list[AvisoErrata]) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                # Delete existing avisos for lot
                cur.execute("DELETE FROM avisos_erratas WHERE lot_id = %s", (lot_id,))

                # Insert new avisos
                for aviso in avisos:
                    cur.execute("""
                        INSERT INTO avisos_erratas (
                            auction_id, lot_id, data, codigo_tipo, tipo, texto, is_active
                        ) VALUES (NULL, %s, %s, %s, %s, %s, %s)
                    """, (
                        lot_id, aviso.data, aviso.codigo_tipo, aviso.tipo,
                        aviso.texto, aviso.is_active
                    ))

    # === AUDIT ===
    def record_audit(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_hash: Optional[str],
        new_hash: Optional[str],
        changed_fields: Optional[dict],
        batch_id: Optional[UUID]
    ) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO auction_audit (
                        entity_type, entity_id, action, old_hash, new_hash,
                        changed_fields, sync_batch_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    entity_type, entity_id, action, old_hash, new_hash,
                    json.dumps(changed_fields) if changed_fields else None,
                    str(batch_id) if batch_id else None
                ))

    # === SYNC ERRORS ===
    def log_sync_error(
        self,
        batch_id: UUID,
        entity_type: str,
        entity_id: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str]
    ) -> None:
        with with_postgres_connection(self.pool) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sync_errors (
                        sync_batch_id, entity_type, entity_id, error_type,
                        error_message, stack_trace
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    str(batch_id), entity_type, entity_id, error_type,
                    error_message, stack_trace
                ))

    # === CONNECTION ===
    def closeall(self) -> None:
        self.pool.closeall()

    # === PRIVATE HELPERS ===
    def _row_to_auction(self, row: tuple) -> Auction:
        """Converte row do banco para Auction."""
        return Auction(
            edital=row[1],
            edle=row[2],
            tipo=row[3],
            orgao=row[4],
            cidade=row[5],
            unidade_nome=row[6],
            codigo_situacao=row[7],
            permite_pf=row[8],
            data_inicio_propostas=row[9],
            data_fim_propostas=row[10],
            data_abertura_lances=row[11],
            total_lotes=row[12],
            mercadorias_apreendidas=row[13],
            data_classificacao=row[14],
            forma_contato=row[15],
            dados_publicacao=row[16],
            numero_recursos=row[17],
            numero_avisos=row[18],
            numero_erratas=row[19],
            id=row[0],
            is_active=row[21],
            data_hash=row[20],
        )

    def _row_to_lot(self, row: tuple) -> Lot:
        """Converte row do banco para Lot."""
        return Lot(
            rfb_id=row[2],
            numero=row[3],
            edle=row[4],
            edital=row[5],
            tipo=row[6],
            orgao=row[7],
            cidade=row[8],
            valor_minimo=row[9],
            situacao_lote=row[10],
            situacao_edital=row[11],
            tipo_edital=row[12],
            permite_pf=row[13],
            possui_imagens=row[14],
            destaque=row[15],
            nr_avisos=row[16],
            nr_erratas=row[17],
            id=row[0],
            auction_id=row[1],
            is_active=row[19],
            data_hash=row[18],
        )

    def _row_to_item(self, row: tuple) -> Item:
        """Converte row do banco para Item."""
        return Item(
            recinto_armazenador=row[3],
            quantidade=row[4],
            unidade_medida=row[5],
            descricao=row[6],
            nr_referencia=row[7],
            id=row[0],
            lot_id=row[1],
            is_active=row[9],
        )

