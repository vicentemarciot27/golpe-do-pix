#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
End-to-end integration test for RFB Auction sync pipeline.

Tests the complete flow:
1. Collect test sample from RFB API (one auction per situacao, one lot per auction)
2. Insert into PostgreSQL database
3. Verify data was correctly persisted

Uses the same approach as test_collectors_quick.py for fast, representative testing.
"""

import hashlib
import json
import pytest
import psycopg2
from uuid import uuid4

from apps.rfb_auction_tools.collectors import RFBAuctionCollector
from config.rfb_auction_tools.settings import RFBAuctionSettings
from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import AvisoErrata, LotImage


def calculate_hash(data: dict) -> str:
    """Calculate SHA256 hash for change detection."""
    # Remove metadata fields
    keys_to_remove = ['id', 'auction_id', 'lot_id', 'lotes', 'itens',
                      'imagens', 'avisos_erratas', 'is_active', 'data_hash']
    clean_data = {k: v for k, v in data.items() if k not in keys_to_remove}
    json_str = json.dumps(clean_data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


class TestSyncE2E:
    """End-to-end tests for the sync pipeline."""

    @pytest.fixture
    def collector(self) -> RFBAuctionCollector:
        """Create a collector instance with default settings."""
        settings = RFBAuctionSettings()
        return RFBAuctionCollector(settings)

    def test_collect_and_persist_sample(
        self,
        collector: RFBAuctionCollector,
        auction_storage,
        db_config,
        results
    ):
        """
        Test complete flow using collect_test_sample():
        1. Collect test sample (one auction per situacao, one lot per auction)
        2. Insert data into PostgreSQL
        3. Verify data was correctly persisted
        """
        batch_id = uuid4()

        # =============================================
        # PHASE 1: COLLECT - Get test sample from RFB
        # =============================================
        print("\n" + "=" * 60)
        print("📥 PHASE 1: Collecting test sample from RFB...")
        print("=" * 60)

        data = collector.collect_test_sample()

        print(f"\n📊 Collection Summary:")
        print(f"   • Auctions: {len(data['auctions'])}")
        print(f"   • Lots: {len(data['lots'])}")
        print(f"   • Items: {len(data['items'])}")
        print(f"   • Images: {len(data['lot_images'])}")
        print(f"   • Avisos/Erratas: {len(data['avisos_erratas'])}")

        # Save raw collection result
        results.store("sync_e2e_collected_data", data)

        assert len(data["auctions"]) > 0, "Should collect at least one auction"
        assert len(data["lots"]) == len(data["auctions"]), (
            "Should have one lot per auction"
        )

        # Verify distinct situacoes
        situacoes = {a["codigo_situacao"] for a in data["auctions"]}
        print(f"   • Situações: {sorted(situacoes)}")

        # =============================================
        # PHASE 2: PERSIST - Insert data into PostgreSQL
        # =============================================
        print("\n" + "=" * 60)
        print("💾 PHASE 2: Persisting data to PostgreSQL...")
        print("=" * 60)

        stats = {"auctions": 0, "lots": 0, "items": 0, "images": 0, "avisos": 0}
        auction_id_map = {}  # edle -> auction_id
        lot_id_map = {}      # (edle, rfb_id) -> lot_id

        # Insert auctions
        for auction_data in data["auctions"]:
            auction = Auction(
                edital=auction_data["edital"],
                edle=auction_data["edle"],
                tipo=auction_data["tipo"],
                orgao=auction_data["orgao"],
                cidade=auction_data["cidade"],
                unidade_nome=auction_data["unidade_nome"],
                codigo_situacao=auction_data["codigo_situacao"],
                permite_pf=auction_data["permite_pf"],
                data_inicio_propostas=auction_data["data_inicio_propostas"],
                data_fim_propostas=auction_data["data_fim_propostas"],
                data_abertura_lances=auction_data["data_abertura_lances"],
                total_lotes=auction_data["total_lotes"],
                mercadorias_apreendidas=auction_data.get("mercadorias_apreendidas"),
                data_classificacao=auction_data.get("data_classificacao"),
                forma_contato=auction_data.get("forma_contato"),
                dados_publicacao=auction_data.get("dados_publicacao"),
                numero_recursos=auction_data.get("numero_recursos", 0),
                numero_avisos=auction_data.get("numero_avisos", 0),
                numero_erratas=auction_data.get("numero_erratas", 0),
            )
            data_hash = calculate_hash(auction_data)
            auction_id = auction_storage.create_auction(auction, data_hash)
            auction_id_map[auction.edle] = auction_id
            auction_storage.record_audit(
                "auction", auction_id, "CREATE", None, data_hash, None, batch_id
            )
            stats["auctions"] += 1

        print(f"   ✓ Inserted {stats['auctions']} auctions")

        # Insert lots
        for lot_data in data["lots"]:
            auction_edle = lot_data["_auction_edle"]
            auction_id = auction_id_map[auction_edle]

            lot = Lot(
                rfb_id=lot_data["rfb_id"],
                numero=lot_data["numero"],
                edle=lot_data["edle"],
                edital=lot_data["edital"],
                tipo=lot_data["tipo"],
                orgao=lot_data["orgao"],
                cidade=lot_data["cidade"],
                valor_minimo=lot_data["valor_minimo"],
                situacao_lote=lot_data["situacao_lote"],
                situacao_edital=lot_data["situacao_edital"],
                tipo_edital=lot_data["tipo_edital"],
                permite_pf=lot_data["permite_pf"],
                possui_imagens=lot_data["possui_imagens"],
                destaque=lot_data["destaque"],
                nr_avisos=lot_data["nr_avisos"],
                nr_erratas=lot_data["nr_erratas"],
            )
            data_hash = calculate_hash(lot_data)
            lot_id = auction_storage.create_lot(lot, auction_id, data_hash)
            lot_id_map[(auction_edle, lot_data["rfb_id"])] = lot_id
            auction_storage.record_audit(
                "lot", lot_id, "CREATE", None, data_hash, None, batch_id
            )
            stats["lots"] += 1

        print(f"   ✓ Inserted {stats['lots']} lots")

        # Insert items
        items_by_lot = {}
        for item_data in data["items"]:
            key = (item_data["_auction_edle"], item_data["_lot_rfb_id"])
            if key not in items_by_lot:
                items_by_lot[key] = []
            items_by_lot[key].append(item_data)

        for (auction_edle, rfb_id), items_list in items_by_lot.items():
            lot_id = lot_id_map[(auction_edle, rfb_id)]
            items = [
                Item(
                    recinto_armazenador=i["recinto_armazenador"],
                    quantidade=i["quantidade"],
                    unidade_medida=i["unidade_medida"],
                    descricao=i["descricao"],
                    nr_referencia=i.get("nr_referencia"),
                )
                for i in items_list
            ]
            auction_storage.replace_items_for_lot(lot_id, items, batch_id)
            stats["items"] += len(items)

        print(f"   ✓ Inserted {stats['items']} items")

        # Insert images
        images_by_lot = {}
        for img_data in data["lot_images"]:
            key = (img_data["_auction_edle"], img_data["_lot_rfb_id"])
            if key not in images_by_lot:
                images_by_lot[key] = []
            images_by_lot[key].append(img_data)

        for (auction_edle, rfb_id), images_list in images_by_lot.items():
            lot_id = lot_id_map[(auction_edle, rfb_id)]
            images = [
                LotImage(
                    rfb_id=i["rfb_id"],
                    url=i["url"],
                    thumbnail_url=i["thumbnail_url"],
                    width=i["width"],
                    height=i["height"],
                    is_featured=i.get("is_featured", False),
                )
                for i in images_list
            ]
            auction_storage.replace_images_for_lot(lot_id, images)
            stats["images"] += len(images)

        print(f"   ✓ Inserted {stats['images']} images")

        # Insert avisos/erratas
        for aviso_data in data["avisos_erratas"]:
            aviso = AvisoErrata(
                data=aviso_data["data"],
                codigo_tipo=aviso_data["codigo_tipo"],
                tipo=aviso_data["tipo"],
                texto=aviso_data["texto"],
            )

            if "_lot_rfb_id" in aviso_data:
                # Aviso for lot
                key = (aviso_data["_auction_edle"], aviso_data["_lot_rfb_id"])
                lot_id = lot_id_map[key]
                auction_storage.replace_avisos_for_lot(lot_id, [aviso])
            else:
                # Aviso for auction
                auction_id = auction_id_map[aviso_data["_auction_edle"]]
                auction_storage.replace_avisos_for_auction(auction_id, [aviso])
            stats["avisos"] += 1

        print(f"   ✓ Inserted {stats['avisos']} avisos/erratas")

        # =============================================
        # PHASE 3: VERIFY - Check data in database
        # =============================================
        print("\n" + "=" * 60)
        print("🔍 PHASE 3: Verifying data in database...")
        print("=" * 60)

        conn = psycopg2.connect(**db_config)
        try:
            with conn.cursor() as cur:
                # Count auctions
                cur.execute("SELECT COUNT(*) FROM auctions WHERE is_active = TRUE")
                db_auctions = cur.fetchone()[0]
                print(f"\n   ✓ Auctions in DB: {db_auctions}")
                assert db_auctions == stats["auctions"], (
                    f"Expected {stats['auctions']} auctions, found {db_auctions}"
                )

                # Count lots
                cur.execute("SELECT COUNT(*) FROM lots WHERE is_active = TRUE")
                db_lots = cur.fetchone()[0]
                print(f"   ✓ Lots in DB: {db_lots}")
                assert db_lots == stats["lots"], (
                    f"Expected {stats['lots']} lots, found {db_lots}"
                )

                # Count items
                cur.execute("SELECT COUNT(*) FROM items WHERE is_active = TRUE")
                db_items = cur.fetchone()[0]
                print(f"   ✓ Items in DB: {db_items}")
                assert db_items == stats["items"], (
                    f"Expected {stats['items']} items, found {db_items}"
                )

                # Count images
                cur.execute("SELECT COUNT(*) FROM lot_images WHERE is_active = TRUE")
                db_images = cur.fetchone()[0]
                print(f"   ✓ Images in DB: {db_images}")
                assert db_images == stats["images"], (
                    f"Expected {stats['images']} images, found {db_images}"
                )

                # Count audit entries
                cur.execute("SELECT COUNT(*) FROM auction_audit WHERE sync_batch_id = %s", (str(batch_id),))
                db_audits = cur.fetchone()[0]
                print(f"   ✓ Audit entries: {db_audits}")

                # =============================================
                # PHASE 4: VERIFY DATA INTEGRITY
                # =============================================
                print("\n" + "=" * 60)
                print("🔗 PHASE 4: Verifying data integrity...")
                print("=" * 60)

                # Verify auction fields
                cur.execute("""
                    SELECT id, edle, edital, cidade, codigo_situacao, data_hash
                    FROM auctions WHERE is_active = TRUE
                    ORDER BY id
                """)
                auctions = cur.fetchall()

                print("\n   📋 Auctions:")
                for auction in auctions:
                    print(f"      • edle={auction[1]}, cidade={auction[3]}, situacao={auction[4]}")
                    assert auction[1] is not None, "edle should not be null"
                    assert auction[5] is not None, "data_hash should not be null"

                # Verify lots
                cur.execute("""
                    SELECT l.id, l.rfb_id, l.auction_id, l.valor_minimo, l.data_hash,
                           a.edle AS auction_edle
                    FROM lots l
                    JOIN auctions a ON l.auction_id = a.id
                    WHERE l.is_active = TRUE
                    ORDER BY l.id
                """)
                lots = cur.fetchall()

                print("\n   📦 Lots:")
                for lot in lots:
                    print(f"      • rfb_id={lot[1]}, auction={lot[5]}, "
                          f"valor_minimo=R${lot[3]/100:.2f}")
                    assert lot[2] is not None, "lot.auction_id should not be null"
                    assert lot[4] is not None, "lot.data_hash should not be null"

                # Verify items per lot
                cur.execute("""
                    SELECT l.rfb_id, COUNT(i.id) as item_count
                    FROM lots l
                    LEFT JOIN items i ON l.id = i.lot_id
                    WHERE l.is_active = TRUE
                    GROUP BY l.id, l.rfb_id
                    ORDER BY item_count DESC
                """)
                lot_items = cur.fetchall()

                print("\n   📝 Items per lot:")
                for lot in lot_items:
                    print(f"      • Lot {lot[0]}: {lot[1]} items")

                # Sample item descriptions
                cur.execute("""
                    SELECT SUBSTRING(descricao, 1, 80)
                    FROM items
                    WHERE is_active = TRUE
                    ORDER BY id
                    LIMIT 3
                """)
                sample_items = cur.fetchall()
                if sample_items:
                    print("\n   📄 Sample item descriptions:")
                    for item in sample_items:
                        print(f"      • {item[0]}...")

        finally:
            conn.close()

        # Save final stats
        results.store("sync_e2e_stats", {
            "batch_id": str(batch_id),
            "collected": {
                "auctions": len(data["auctions"]),
                "lots": len(data["lots"]),
                "items": len(data["items"]),
                "images": len(data["lot_images"]),
                "avisos": len(data["avisos_erratas"]),
            },
            "persisted": stats,
        })

        print("\n" + "=" * 60)
        print("✅ All verifications passed!")
        print("=" * 60 + "\n")

    def test_retrieve_persisted_data(
        self,
        collector: RFBAuctionCollector,
        auction_storage,
        db_config
    ):
        """
        Test that persisted data can be correctly retrieved via storage methods.
        """
        print("\n" + "=" * 60)
        print("🔄 Testing data retrieval...")
        print("=" * 60)

        # First, collect and persist sample
        data = collector.collect_test_sample()
        batch_id = uuid4()

        # Insert first auction and lot
        auction_data = data["auctions"][0]
        auction = Auction(
            edital=auction_data["edital"],
            edle=auction_data["edle"],
            tipo=auction_data["tipo"],
            orgao=auction_data["orgao"],
            cidade=auction_data["cidade"],
            unidade_nome=auction_data["unidade_nome"],
            codigo_situacao=auction_data["codigo_situacao"],
            permite_pf=auction_data["permite_pf"],
            data_inicio_propostas=auction_data["data_inicio_propostas"],
            data_fim_propostas=auction_data["data_fim_propostas"],
            data_abertura_lances=auction_data["data_abertura_lances"],
            total_lotes=auction_data["total_lotes"],
        )
        data_hash = calculate_hash(auction_data)
        auction_id = auction_storage.create_auction(auction, data_hash)

        # Retrieve and verify
        retrieved = auction_storage.get_auction_by_edle(auction.edle)

        assert retrieved is not None, "Should retrieve auction by edle"
        assert retrieved.id == auction_id, "Retrieved auction should have correct ID"
        assert retrieved.edle == auction.edle, "Retrieved auction should have correct edle"
        assert retrieved.data_hash == data_hash, "Retrieved auction should have correct hash"

        print(f"   ✓ Retrieved auction: {retrieved.edle}")
        print(f"   ✓ Hash verified: {retrieved.data_hash[:16]}...")

        # Verify active edles
        active_edles = auction_storage.get_active_auction_edles()
        assert auction.edle in active_edles, "Auction edle should be in active edles"
        print(f"   ✓ Active edles: {len(active_edles)}")

        print("\n   ✅ Data retrieval verified!")
