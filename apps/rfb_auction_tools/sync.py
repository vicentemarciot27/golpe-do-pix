import hashlib
import json
import logging
import traceback
from dataclasses import asdict
from uuid import UUID, uuid4

from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.ports.auction_storage import AuctionStorage
from apps.rfb_auction_tools.collectors import RFBAuctionCollector, LotUnavailableError


logger = logging.getLogger(__name__)


class SyncResult:
    """Resultado de uma operação de sincronização."""

    def __init__(self, batch_id: UUID):
        self.batch_id = batch_id
        self.auctions = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}
        self.lots = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}
        self.items = {"synced": 0}

    def __repr__(self) -> str:
        return (
            f"SyncResult(batch_id={self.batch_id}, "
            f"auctions={self.auctions}, lots={self.lots}, items={self.items})"
        )

    def to_dict(self) -> dict:
        """Converte resultado para dicionário."""
        return {
            "batch_id": str(self.batch_id),
            "auctions": self.auctions.copy(),
            "lots": self.lots.copy(),
            "items": self.items.copy(),
        }


class RFBAuctionSync:
    """Sincronizador de dados RFB com banco de dados."""

    def __init__(self, collector: RFBAuctionCollector, storage: AuctionStorage):
        self.collector = collector
        self.storage = storage

    def sync_all(self, fetch_lot_details: bool = True) -> SyncResult:
        """
        Sincronização completa de todos os auctions disponíveis.

        Args:
            fetch_lot_details: Se True, busca detalhes de cada lot (items, imagens, avisos).
                               Se False, usa apenas dados do auction_details.

        Returns:
            SyncResult com contadores de operações realizadas.
        """
        batch_id = uuid4()
        result = SyncResult(batch_id)

        logger.info(f"Iniciando sincronização batch={batch_id}")

        # 1. Coletar auctions da RFB
        try:
            rfb_auctions = self.collector.fetch_available_auctions()
        except Exception as e:
            logger.error(f"Erro ao coletar auctions disponíveis: {e}")
            self.storage.log_sync_error(
                batch_id, "system", "fetch_available_auctions",
                type(e).__name__, str(e), traceback.format_exc()
            )
            return result

        rfb_edles = {a.edle for a in rfb_auctions}
        logger.info(f"Coletados {len(rfb_edles)} auctions da RFB")

        # 2. Comparar com storage
        stored_edles = self.storage.get_active_auction_edles()

        new_edles = rfb_edles - stored_edles
        existing_edles = rfb_edles & stored_edles
        removed_edles = stored_edles - rfb_edles

        logger.info(
            f"Comparação: {len(new_edles)} novos, "
            f"{len(existing_edles)} existentes, {len(removed_edles)} removidos"
        )

        # 3. Processar novos
        for auction in rfb_auctions:
            if auction.edle in new_edles:
                self._sync_new_auction(auction, batch_id, result, fetch_lot_details)

        # 4. Processar existentes (SEMPRE verifica lots)
        for auction in rfb_auctions:
            if auction.edle in existing_edles:
                self._sync_existing_auction(auction, batch_id, result, fetch_lot_details)

        # 5. Soft delete removidos
        if removed_edles:
            deleted_count = self.storage.soft_delete_auctions(removed_edles, batch_id)
            result.auctions["deleted"] = deleted_count
            logger.info(f"Soft delete de {deleted_count} auctions")

        logger.info(f"Sincronização concluída: {result}")
        return result

    def _calculate_hash(self, entity: Auction | Lot) -> str:
        """
        Calcula hash SHA256 de uma entidade.

        Remove campos de metadados/relacionamentos para garantir que
        apenas dados de negócio sejam comparados.
        """
        data = asdict(entity)

        # Remove campos de metadados/relacionamentos
        keys_to_remove = [
            'id', 'auction_id', 'lot_id',
            'lotes', 'itens', 'imagens', 'avisos_erratas',
            'is_active'
        ]
        for key in keys_to_remove:
            data.pop(key, None)

        # Serializa ordenado e calcula hash
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _sync_new_auction(
        self,
        auction: Auction,
        batch_id: UUID,
        result: SyncResult,
        fetch_lot_details: bool
    ) -> None:
        """Cria auction novo com seus lots."""
        try:
            # Busca detalhes do auction (inclui lista de lotes)
            auction_details = self.collector.fetch_auction_details(auction.edle)
            data_hash = self._calculate_hash(auction_details)

            # Cria auction no storage
            auction_id = self.storage.create_auction(auction_details, data_hash)
            self.storage.record_audit(
                'auction', auction_id, 'CREATE', None, data_hash, None, batch_id
            )
            result.auctions["created"] += 1
            logger.debug(f"Auction criado: {auction.edle} (id={auction_id})")

            # Sync avisos do auction
            if auction_details.avisos_erratas:
                self.storage.replace_avisos_for_auction(
                    auction_id, auction_details.avisos_erratas
                )

            # Sync lots
            for lot in auction_details.lotes:
                self._sync_new_lot(lot, auction_id, batch_id, result, fetch_lot_details)

        except Exception as e:
            self._handle_error('auction', auction.edle, e, batch_id, result)

    def _sync_existing_auction(
        self,
        auction: Auction,
        batch_id: UUID,
        result: SyncResult,
        fetch_lot_details: bool
    ) -> None:
        """Atualiza auction existente e SEMPRE verifica lots."""
        try:
            stored = self.storage.get_auction_by_edle(auction.edle)
            if stored is None:
                logger.warning(f"Auction {auction.edle} não encontrado no storage")
                return

            rfb_details = self.collector.fetch_auction_details(auction.edle)
            new_hash = self._calculate_hash(rfb_details)

            # Atualiza auction se hash diferente
            old_hash = getattr(stored, 'data_hash', None)
            if old_hash != new_hash:
                rfb_details.id = stored.id
                self.storage.update_auction(rfb_details, new_hash)
                self.storage.record_audit(
                    'auction', stored.id, 'UPDATE', old_hash, new_hash, None, batch_id
                )
                result.auctions["updated"] += 1
                logger.debug(f"Auction atualizado: {auction.edle}")

                # Atualiza avisos do auction
                if rfb_details.avisos_erratas:
                    self.storage.replace_avisos_for_auction(
                        stored.id, rfb_details.avisos_erratas
                    )

            # SEMPRE verifica lots (independente do hash do auction)
            self._sync_lots(
                stored.id, auction.edle, rfb_details.lotes,
                batch_id, result, fetch_lot_details
            )

        except Exception as e:
            self._handle_error('auction', auction.edle, e, batch_id, result)

    def _sync_lots(
        self,
        auction_id: int,
        edle: str,
        rfb_lots: list[Lot],
        batch_id: UUID,
        result: SyncResult,
        fetch_lot_details: bool
    ) -> None:
        """Sincroniza lots de um auction."""
        rfb_rfb_ids = {lot.rfb_id for lot in rfb_lots}
        stored_rfb_ids = self.storage.get_active_lot_rfb_ids(auction_id)

        new_ids = rfb_rfb_ids - stored_rfb_ids
        existing_ids = rfb_rfb_ids & stored_rfb_ids
        removed_ids = stored_rfb_ids - rfb_rfb_ids

        # Processar lots novos e existentes
        for lot in rfb_lots:
            if lot.rfb_id in new_ids:
                self._sync_new_lot(lot, auction_id, batch_id, result, fetch_lot_details)
            elif lot.rfb_id in existing_ids:
                self._sync_existing_lot(
                    lot, auction_id, edle, batch_id, result, fetch_lot_details
                )

        # Soft delete lots removidos
        if removed_ids:
            deleted_count = self.storage.soft_delete_lots(auction_id, removed_ids, batch_id)
            result.lots["deleted"] += deleted_count

    def _sync_new_lot(
        self,
        lot: Lot,
        auction_id: int,
        batch_id: UUID,
        result: SyncResult,
        fetch_lot_details: bool
    ) -> None:
        """Cria lot novo com seus items."""
        try:
            # Busca detalhes do lot se solicitado
            if fetch_lot_details:
                lot_details = self.collector.fetch_lot_details(lot.edle, lot.rfb_id)
            else:
                lot_details = lot

            data_hash = self._calculate_hash(lot_details)
            lot_id = self.storage.create_lot(lot_details, auction_id, data_hash)
            self.storage.record_audit(
                'lot', lot_id, 'CREATE', None, data_hash, None, batch_id
            )
            result.lots["created"] += 1
            logger.debug(f"Lot criado: {lot.edle}/{lot.rfb_id} (id={lot_id})")

            # Sync items, images, avisos
            self._sync_items_for_lot(lot_id, lot_details.itens, batch_id, result)
            self._sync_images_for_lot(lot_id, lot_details.imagens)
            self._sync_avisos_for_lot(lot_id, lot_details.avisos_erratas)

        except LotUnavailableError as e:
            self._handle_lot_error(lot, auction_id, e, batch_id, result)
        except Exception as e:
            self._handle_error('lot', f"{lot.edle}/{lot.rfb_id}", e, batch_id, result)

    def _sync_existing_lot(
        self,
        lot: Lot,
        auction_id: int,
        edle: str,
        batch_id: UUID,
        result: SyncResult,
        fetch_lot_details: bool
    ) -> None:
        """Atualiza lot existente e SEMPRE verifica items."""
        try:
            stored = self.storage.get_lot_by_rfb_id(auction_id, lot.rfb_id)
            if stored is None:
                logger.warning(f"Lot {edle}/{lot.rfb_id} não encontrado no storage")
                return

            # Busca detalhes do lot se solicitado
            if fetch_lot_details:
                rfb_details = self.collector.fetch_lot_details(edle, lot.rfb_id)
            else:
                rfb_details = lot

            new_hash = self._calculate_hash(rfb_details)

            # Atualiza lot se hash diferente
            old_hash = getattr(stored, 'data_hash', None)
            if old_hash != new_hash:
                rfb_details.id = stored.id
                rfb_details.auction_id = stored.auction_id
                self.storage.update_lot(rfb_details, new_hash)
                self.storage.record_audit(
                    'lot', stored.id, 'UPDATE', old_hash, new_hash, None, batch_id
                )
                result.lots["updated"] += 1
                logger.debug(f"Lot atualizado: {edle}/{lot.rfb_id}")

            # SEMPRE verifica items (independente do hash do lot)
            self._sync_items_for_lot(stored.id, rfb_details.itens, batch_id, result)
            self._sync_images_for_lot(stored.id, rfb_details.imagens)
            self._sync_avisos_for_lot(stored.id, rfb_details.avisos_erratas)

        except LotUnavailableError as e:
            self._handle_lot_error(lot, auction_id, e, batch_id, result)
        except Exception as e:
            self._handle_error('lot', f"{edle}/{lot.rfb_id}", e, batch_id, result)

    def _sync_items_for_lot(
        self,
        lot_id: int,
        items: list,
        batch_id: UUID,
        result: SyncResult
    ) -> None:
        """Substitui items de um lot (replace strategy)."""
        self.storage.replace_items_for_lot(lot_id, items, batch_id)
        result.items["synced"] += len(items)

    def _sync_images_for_lot(self, lot_id: int, images: list) -> None:
        """Substitui imagens de um lot."""
        self.storage.replace_images_for_lot(lot_id, images)

    def _sync_avisos_for_lot(self, lot_id: int, avisos: list) -> None:
        """Substitui avisos de um lot."""
        self.storage.replace_avisos_for_lot(lot_id, avisos)

    def _handle_error(
        self,
        entity_type: str,
        entity_id: str,
        error: Exception,
        batch_id: UUID,
        result: SyncResult
    ) -> None:
        """Trata erros genéricos."""
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = traceback.format_exc()

        logger.error(f"Erro em {entity_type} {entity_id}: {error_message}")

        self.storage.log_sync_error(
            batch_id, entity_type, str(entity_id),
            error_type, error_message, stack_trace
        )

        if entity_type == 'auction':
            self.storage.update_auction_error(entity_id, 'COLLECTION_ERROR', error_message)
            result.auctions["errors"] += 1
        elif entity_type == 'lot':
            result.lots["errors"] += 1

    def _handle_lot_error(
        self,
        lot: Lot,
        auction_id: int,
        error: Exception,
        batch_id: UUID,
        result: SyncResult
    ) -> None:
        """Trata erros específicos de lot (LotUnavailableError)."""
        # Lot existe mas não pode ser coletado - marca como erro mas não cria
        self._handle_error('lot', f"{lot.edle}/{lot.rfb_id}", error, batch_id, result)

