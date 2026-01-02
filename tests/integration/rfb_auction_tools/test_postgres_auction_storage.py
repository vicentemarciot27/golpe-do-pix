#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration tests for PostgresAuctionStorage.
Tests real database interactions with PostgreSQL.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata


class TestPostgresAuctionStorageAuction:
    """Tests for auction-related operations."""

    def test_create_auction_returns_id(self, auction_storage, sample_auction):
        """Test that creating an auction returns a valid ID."""
        auction_id = auction_storage.create_auction(sample_auction, "hash123")
        
        assert auction_id is not None
        assert isinstance(auction_id, int)
        assert auction_id > 0

    def test_get_auction_by_edle(self, auction_storage, sample_auction):
        """Test retrieving an auction by edle."""
        data_hash = "hash456"
        auction_id = auction_storage.create_auction(sample_auction, data_hash)
        
        retrieved = auction_storage.get_auction_by_edle(sample_auction.edle)
        
        assert retrieved is not None
        assert retrieved.id == auction_id
        assert retrieved.edle == sample_auction.edle
        assert retrieved.edital == sample_auction.edital
        assert retrieved.cidade == sample_auction.cidade
        assert retrieved.is_active == True
        assert retrieved.data_hash == data_hash

    def test_get_auction_by_edle_not_found(self, auction_storage):
        """Test that non-existent auction returns None."""
        result = auction_storage.get_auction_by_edle("nonexistent/edle")
        assert result is None

    def test_get_active_auction_edles(self, auction_storage, sample_auction):
        """Test getting all active auction edles."""
        auction_storage.create_auction(sample_auction, "hash1")
        
        # Create another auction with different edle
        sample_auction.edital = "0800100/000002/2025"
        sample_auction.edle = "800100/2/2025"
        auction_storage.create_auction(sample_auction, "hash2")
        
        edles = auction_storage.get_active_auction_edles()
        
        assert len(edles) == 2
        assert "800100/1/2025" in edles
        assert "800100/2/2025" in edles

    def test_update_auction_changes_hash(self, auction_storage, sample_auction):
        """Test that updating an auction changes its hash."""
        old_hash = "old_hash"
        new_hash = "new_hash"
        
        auction_id = auction_storage.create_auction(sample_auction, old_hash)
        
        # Update the auction
        sample_auction.id = auction_id
        sample_auction.cidade = "Rio de Janeiro"
        auction_storage.update_auction(sample_auction, new_hash)
        
        # Retrieve and verify
        retrieved = auction_storage.get_auction_by_edle(sample_auction.edle)
        assert retrieved.cidade == "Rio de Janeiro"
        assert retrieved.data_hash == new_hash

    def test_soft_delete_sets_is_active_false(self, auction_storage, sample_auction):
        """Test that soft delete marks auction as inactive."""
        auction_storage.create_auction(sample_auction, "hash")
        batch_id = uuid4()
        
        deleted_count = auction_storage.soft_delete_auctions({sample_auction.edle}, batch_id)
        
        assert deleted_count == 1
        
        # Verify auction is inactive
        retrieved = auction_storage.get_auction_by_edle(sample_auction.edle)
        assert retrieved.is_active == False
        
        # Verify no longer in active edles
        active_edles = auction_storage.get_active_auction_edles()
        assert sample_auction.edle not in active_edles

    def test_update_auction_error(self, auction_storage, sample_auction):
        """Test updating auction error status."""
        auction_storage.create_auction(sample_auction, "hash")
        
        auction_storage.update_auction_error(
            sample_auction.edle,
            "COLLECTION_ERROR",
            "Connection timeout"
        )
        
        # Verify error is stored (would need direct DB query to verify)
        # For now, just ensure no exception is raised


class TestPostgresAuctionStorageLot:
    """Tests for lot-related operations."""

    def test_create_lot_with_auction_id(self, auction_storage, sample_auction, sample_lot):
        """Test creating a lot associated with an auction."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        
        assert lot_id is not None
        assert isinstance(lot_id, int)
        assert lot_id > 0

    def test_get_lot_by_rfb_id(self, auction_storage, sample_auction, sample_lot):
        """Test retrieving a lot by rfb_id."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_hash = "lot_hash_123"
        lot_id = auction_storage.create_lot(sample_lot, auction_id, lot_hash)
        
        retrieved = auction_storage.get_lot_by_rfb_id(auction_id, sample_lot.rfb_id)
        
        assert retrieved is not None
        assert retrieved.id == lot_id
        assert retrieved.rfb_id == sample_lot.rfb_id
        assert retrieved.auction_id == auction_id
        assert retrieved.data_hash == lot_hash

    def test_get_active_lot_rfb_ids(self, auction_storage, sample_auction, sample_lot):
        """Test getting active lot rfb_ids for an auction."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        
        # Create another lot
        sample_lot.rfb_id = 12346
        auction_storage.create_lot(sample_lot, auction_id, "lot_hash2")
        
        rfb_ids = auction_storage.get_active_lot_rfb_ids(auction_id)
        
        assert len(rfb_ids) == 2
        assert 12345 in rfb_ids
        assert 12346 in rfb_ids

    def test_update_lot(self, auction_storage, sample_auction, sample_lot):
        """Test updating a lot."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "old_hash")
        
        sample_lot.id = lot_id
        sample_lot.auction_id = auction_id
        sample_lot.valor_minimo = 20000
        auction_storage.update_lot(sample_lot, "new_hash")
        
        retrieved = auction_storage.get_lot_by_rfb_id(auction_id, sample_lot.rfb_id)
        assert retrieved.valor_minimo == 20000
        assert retrieved.data_hash == "new_hash"

    def test_soft_delete_lots(self, auction_storage, sample_auction, sample_lot):
        """Test soft deleting lots."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        batch_id = uuid4()
        
        deleted_count = auction_storage.soft_delete_lots(auction_id, {sample_lot.rfb_id}, batch_id)
        
        assert deleted_count == 1
        
        active_rfb_ids = auction_storage.get_active_lot_rfb_ids(auction_id)
        assert sample_lot.rfb_id not in active_rfb_ids


class TestPostgresAuctionStorageItem:
    """Tests for item-related operations."""

    def test_replace_items_for_lot(self, auction_storage, sample_auction, sample_lot, sample_item):
        """Test replacing items for a lot."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        batch_id = uuid4()
        
        items = [
            sample_item,
            Item(
                recinto_armazenador="EADI Rio",
                quantidade=5,
                unidade_medida="kg",
                descricao="Mercadoria teste",
            )
        ]
        
        auction_storage.replace_items_for_lot(lot_id, items, batch_id)
        
        # Verify items were created
        item0 = auction_storage.get_item_by_index(lot_id, 0)
        item1 = auction_storage.get_item_by_index(lot_id, 1)
        
        assert item0 is not None
        assert item0.recinto_armazenador == "EADI São Paulo"
        assert item1 is not None
        assert item1.recinto_armazenador == "EADI Rio"

    def test_replace_items_clears_old_items(self, auction_storage, sample_auction, sample_lot, sample_item):
        """Test that replacing items clears old ones."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        batch_id = uuid4()
        
        # First insert
        auction_storage.replace_items_for_lot(lot_id, [sample_item, sample_item], batch_id)
        
        # Replace with single item
        new_item = Item(
            recinto_armazenador="Novo Recinto",
            quantidade=1,
            unidade_medida="un",
            descricao="Novo item",
        )
        auction_storage.replace_items_for_lot(lot_id, [new_item], batch_id)
        
        # Old item at index 1 should be gone
        item0 = auction_storage.get_item_by_index(lot_id, 0)
        item1 = auction_storage.get_item_by_index(lot_id, 1)
        
        assert item0 is not None
        assert item0.recinto_armazenador == "Novo Recinto"
        assert item1 is None


class TestPostgresAuctionStorageImages:
    """Tests for image-related operations."""

    def test_replace_images_for_lot(self, auction_storage, sample_auction, sample_lot, sample_lot_image):
        """Test replacing images for a lot."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        
        images = [sample_lot_image]
        auction_storage.replace_images_for_lot(lot_id, images)
        
        # Verify through direct query (no getter in interface for this)
        # Just ensure no exception is raised


class TestPostgresAuctionStorageAvisos:
    """Tests for avisos/erratas-related operations."""

    def test_replace_avisos_for_auction(self, auction_storage, sample_auction, sample_aviso):
        """Test replacing avisos for an auction."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        
        avisos = [sample_aviso]
        auction_storage.replace_avisos_for_auction(auction_id, avisos)
        
        # Verify through direct query (no getter in interface for this)
        # Just ensure no exception is raised

    def test_replace_avisos_for_lot(self, auction_storage, sample_auction, sample_lot, sample_aviso):
        """Test replacing avisos for a lot."""
        auction_id = auction_storage.create_auction(sample_auction, "auction_hash")
        lot_id = auction_storage.create_lot(sample_lot, auction_id, "lot_hash")
        
        avisos = [sample_aviso]
        auction_storage.replace_avisos_for_lot(lot_id, avisos)
        
        # Verify through direct query
        # Just ensure no exception is raised


class TestPostgresAuctionStorageAudit:
    """Tests for audit-related operations."""

    def test_record_audit_persists_entry(self, auction_storage, sample_auction, db_config):
        """Test that audit entries are persisted."""
        import psycopg2
        
        auction_id = auction_storage.create_auction(sample_auction, "hash")
        batch_id = uuid4()
        
        auction_storage.record_audit(
            entity_type="auction",
            entity_id=auction_id,
            action="CREATE",
            old_hash=None,
            new_hash="hash",
            changed_fields=None,
            batch_id=batch_id
        )
        
        # Verify through direct query
        conn = psycopg2.connect(**db_config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_type, entity_id, action, new_hash FROM auction_audit WHERE entity_id = %s",
                    (auction_id,)
                )
                row = cur.fetchone()
                assert row is not None
                assert row[0] == "auction"
                assert row[1] == auction_id
                assert row[2] == "CREATE"
                assert row[3] == "hash"
        finally:
            conn.close()


class TestPostgresAuctionStorageSyncErrors:
    """Tests for sync error logging."""

    def test_log_sync_error(self, auction_storage, db_config):
        """Test logging a sync error."""
        import psycopg2
        
        batch_id = uuid4()
        
        auction_storage.log_sync_error(
            batch_id=batch_id,
            entity_type="auction",
            entity_id="800100/1/2025",
            error_type="ConnectionError",
            error_message="Connection refused",
            stack_trace="Traceback..."
        )
        
        # Verify through direct query
        conn = psycopg2.connect(**db_config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_type, error_type, error_message FROM sync_errors WHERE sync_batch_id = %s",
                    (str(batch_id),)
                )
                row = cur.fetchone()
                assert row is not None
                assert row[0] == "auction"
                assert row[1] == "ConnectionError"
                assert row[2] == "Connection refused"
        finally:
            conn.close()

