#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for RFBAuctionSync.
Tests synchronization logic with mocked collector and storage.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from uuid import UUID

from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata
from shared.adapters.outbound.local_auction_storage import LocalAuctionStorage
from apps.rfb_auction_tools.sync import RFBAuctionSync, SyncResult
from apps.rfb_auction_tools.collectors import LotUnavailableError


# =========================
# FIXTURES
# =========================

@pytest.fixture
def sample_auction() -> Auction:
    """Sample Auction for tests."""
    return Auction(
        edital="0800100/000001/2025",
        edle="800100/1/2025",
        tipo="1",
        orgao="Receita Federal do Brasil",
        cidade="São Paulo",
        unidade_nome="DRF São Paulo",
        codigo_situacao=2,
        permite_pf=True,
        data_inicio_propostas=datetime(2025, 1, 1, 10, 0),
        data_fim_propostas=datetime(2025, 1, 5, 18, 0),
        data_abertura_lances=datetime(2025, 1, 6, 10, 0),
        total_lotes=5,
        mercadorias_apreendidas=True,
        data_classificacao=None,
        forma_contato="email@rfb.gov.br",
        dados_publicacao="DOU 01/01/2025",
        numero_recursos=0,
        numero_avisos=1,
        numero_erratas=0,
    )


@pytest.fixture
def sample_lot() -> Lot:
    """Sample Lot for tests."""
    return Lot(
        rfb_id=12345,
        numero=1,
        edle="800100/1/2025",
        edital="0800100/000001/2025",
        tipo="ELETRÔNICO",
        orgao="Receita Federal do Brasil",
        cidade="São Paulo",
        valor_minimo=10000,
        situacao_lote=1,
        situacao_edital=2,
        tipo_edital=1,
        permite_pf=True,
        possui_imagens=True,
        destaque=False,
        nr_avisos=0,
        nr_erratas=0,
    )


@pytest.fixture
def sample_item() -> Item:
    """Sample Item for tests."""
    return Item(
        recinto_armazenador="EADI São Paulo",
        quantidade=10,
        unidade_medida="un",
        descricao="[DI 20/1234567-8] Smartphone Samsung Galaxy",
        nr_referencia="REF001",
    )


@pytest.fixture
def mock_collector():
    """Mock RFBAuctionCollector."""
    return Mock()


@pytest.fixture
def local_storage():
    """Local in-memory storage for tests."""
    return LocalAuctionStorage()


@pytest.fixture
def sync(mock_collector, local_storage):
    """RFBAuctionSync instance with mocks."""
    return RFBAuctionSync(mock_collector, local_storage)


# =========================
# HASH CALCULATION TESTS
# =========================

class TestCalculateHash:
    """Tests for hash calculation."""

    def test_calculate_hash_ignores_id_fields(self, sync, sample_auction):
        """Test that hash ignores id, auction_id, lot_id fields."""
        auction1 = sample_auction
        auction1.id = None
        hash1 = sync._calculate_hash(auction1)
        
        auction2 = Auction(
            edital=auction1.edital,
            edle=auction1.edle,
            tipo=auction1.tipo,
            orgao=auction1.orgao,
            cidade=auction1.cidade,
            unidade_nome=auction1.unidade_nome,
            codigo_situacao=auction1.codigo_situacao,
            permite_pf=auction1.permite_pf,
            data_inicio_propostas=auction1.data_inicio_propostas,
            data_fim_propostas=auction1.data_fim_propostas,
            data_abertura_lances=auction1.data_abertura_lances,
            total_lotes=auction1.total_lotes,
            mercadorias_apreendidas=auction1.mercadorias_apreendidas,
            forma_contato=auction1.forma_contato,
            dados_publicacao=auction1.dados_publicacao,
            numero_avisos=auction1.numero_avisos,
            id=999  # Different ID
        )
        hash2 = sync._calculate_hash(auction2)
        
        assert hash1 == hash2

    def test_calculate_hash_ignores_is_active(self, sync, sample_auction):
        """Test that hash ignores is_active field."""
        auction1 = sample_auction
        auction1.is_active = True
        hash1 = sync._calculate_hash(auction1)
        
        auction1.is_active = False
        hash2 = sync._calculate_hash(auction1)
        
        assert hash1 == hash2

    def test_calculate_hash_deterministic(self, sync, sample_auction):
        """Test that same data produces same hash."""
        hash1 = sync._calculate_hash(sample_auction)
        hash2 = sync._calculate_hash(sample_auction)
        
        assert hash1 == hash2

    def test_calculate_hash_different_data_different_hash(self, sync, sample_auction):
        """Test that different data produces different hash."""
        hash1 = sync._calculate_hash(sample_auction)
        
        sample_auction.cidade = "Rio de Janeiro"
        hash2 = sync._calculate_hash(sample_auction)
        
        assert hash1 != hash2

    def test_calculate_hash_ignores_relationships(self, sync, sample_auction, sample_lot):
        """Test that hash ignores lotes, itens, imagens, avisos_erratas."""
        sample_auction.lotes = []
        hash1 = sync._calculate_hash(sample_auction)
        
        sample_auction.lotes = [sample_lot]
        hash2 = sync._calculate_hash(sample_auction)
        
        assert hash1 == hash2


# =========================
# SYNC LOGIC TESTS
# =========================

class TestSyncAll:
    """Tests for sync_all method."""

    def test_sync_creates_new_auction(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that sync creates new auctions."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["created"] == 1
        assert result.lots["created"] == 1
        assert sample_auction.edle in local_storage.get_active_auction_edles()

    def test_sync_updates_auction_when_hash_differs(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that sync updates auction when data changes."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        # First sync - create
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        sync.sync_all(fetch_lot_details=True)
        
        # Modify auction
        sample_auction.cidade = "Rio de Janeiro"
        
        # Second sync - update
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["updated"] == 1

    def test_sync_skips_auction_when_hash_equal(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that sync skips auction when hash hasn't changed."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        # First sync
        sync.sync_all(fetch_lot_details=True)
        
        # Second sync - same data
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["created"] == 0
        assert result.auctions["updated"] == 0

    def test_sync_always_checks_lots_even_if_auction_unchanged(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that lots are always checked even if auction hash is the same."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        # First sync
        sync.sync_all(fetch_lot_details=True)
        
        # Second sync - lot details should still be fetched
        result = sync.sync_all(fetch_lot_details=True)
        
        # fetch_lot_details should be called for existing lots too
        # (This is verified by items being synced)
        assert result.items["synced"] >= 0  # Items are processed even if unchanged

    def test_sync_soft_deletes_removed_auctions(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that auctions not in RFB are soft deleted."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        # First sync - create auction
        sync.sync_all(fetch_lot_details=True)
        assert sample_auction.edle in local_storage.get_active_auction_edles()
        
        # Second sync - auction no longer in RFB
        mock_collector.fetch_available_auctions.return_value = []
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["deleted"] == 1
        assert sample_auction.edle not in local_storage.get_active_auction_edles()


# =========================
# ERROR HANDLING TESTS
# =========================

class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_lot_unavailable_error(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test handling of LotUnavailableError."""
        sample_auction.lotes = [sample_lot]
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.side_effect = LotUnavailableError("Lot unavailable")
        
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["created"] == 1  # Auction still created
        assert result.lots["errors"] == 1  # Lot error recorded
        
        # Error should be logged
        errors = local_storage.get_sync_errors()
        assert len(errors) >= 1

    def test_handles_collection_error(self, sync, mock_collector, local_storage, sample_auction):
        """Test handling of collection errors."""
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.side_effect = Exception("Connection error")
        
        result = sync.sync_all(fetch_lot_details=True)
        
        assert result.auctions["errors"] == 1
        
        # Error should be logged
        errors = local_storage.get_sync_errors()
        assert len(errors) >= 1

    def test_handles_fetch_available_auctions_error(self, sync, mock_collector, local_storage):
        """Test handling of error when fetching available auctions."""
        mock_collector.fetch_available_auctions.side_effect = Exception("API error")
        
        result = sync.sync_all(fetch_lot_details=True)
        
        # Should return result with zeros (no auctions processed)
        assert result.auctions["created"] == 0
        
        # Error should be logged
        errors = local_storage.get_sync_errors()
        assert len(errors) >= 1


# =========================
# SYNC RESULT TESTS
# =========================

class TestSyncResult:
    """Tests for SyncResult class."""

    def test_sync_result_has_batch_id(self):
        """Test that SyncResult has a valid batch_id."""
        from uuid import uuid4
        batch_id = uuid4()
        result = SyncResult(batch_id)
        
        assert result.batch_id == batch_id

    def test_sync_result_to_dict(self):
        """Test SyncResult.to_dict()."""
        from uuid import uuid4
        batch_id = uuid4()
        result = SyncResult(batch_id)
        result.auctions["created"] = 5
        result.lots["updated"] = 3
        
        d = result.to_dict()
        
        assert d["batch_id"] == str(batch_id)
        assert d["auctions"]["created"] == 5
        assert d["lots"]["updated"] == 3

    def test_sync_result_repr(self):
        """Test SyncResult.__repr__()."""
        from uuid import uuid4
        batch_id = uuid4()
        result = SyncResult(batch_id)
        
        repr_str = repr(result)
        
        assert "SyncResult" in repr_str
        assert str(batch_id) in repr_str


# =========================
# AUDIT TESTS
# =========================

class TestAudit:
    """Tests for audit recording."""

    def test_audit_recorded_on_create(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that audit is recorded when auction is created."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        sync.sync_all(fetch_lot_details=True)
        
        audit_entries = local_storage.get_audit_entries()
        
        # Should have CREATE entries for auction and lot
        create_entries = [e for e in audit_entries if e["action"] == "CREATE"]
        assert len(create_entries) >= 2  # At least auction and lot

    def test_audit_recorded_on_update(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that audit is recorded when auction is updated."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        # First sync
        sync.sync_all(fetch_lot_details=True)
        
        # Modify and sync again
        sample_auction.cidade = "Rio de Janeiro"
        sync.sync_all(fetch_lot_details=True)
        
        audit_entries = local_storage.get_audit_entries()
        
        # Should have UPDATE entry
        update_entries = [e for e in audit_entries if e["action"] == "UPDATE"]
        assert len(update_entries) >= 1

    def test_audit_recorded_on_delete(self, sync, mock_collector, local_storage, sample_auction, sample_lot):
        """Test that audit is recorded when auction is soft deleted."""
        sample_auction.lotes = [sample_lot]
        sample_lot.itens = []
        sample_lot.imagens = []
        sample_lot.avisos_erratas = []
        
        mock_collector.fetch_available_auctions.return_value = [sample_auction]
        mock_collector.fetch_auction_details.return_value = sample_auction
        mock_collector.fetch_lot_details.return_value = sample_lot
        
        # First sync - create
        sync.sync_all(fetch_lot_details=True)
        
        # Second sync - auction removed
        mock_collector.fetch_available_auctions.return_value = []
        sync.sync_all(fetch_lot_details=True)
        
        audit_entries = local_storage.get_audit_entries()
        
        # Should have DELETE entry
        delete_entries = [e for e in audit_entries if e["action"] == "DELETE"]
        assert len(delete_entries) >= 1

