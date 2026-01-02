from typing import Optional
from uuid import UUID

from shared.ports.auction_storage import AuctionStorage
from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata


class LocalAuctionStorage(AuctionStorage):
    """Implementação em memória do AuctionStorage para testes."""

    def __init__(self):
        self._auctions: dict[int, Auction] = {}
        self._lots: dict[int, Lot] = {}
        self._items: dict[int, Item] = {}
        self._images: dict[int, LotImage] = {}
        self._avisos: dict[int, AvisoErrata] = {}
        self._audit: list[dict] = []
        self._sync_errors: list[dict] = []
        self._next_auction_id = 1
        self._next_lot_id = 1
        self._next_item_id = 1
        self._next_image_id = 1
        self._next_aviso_id = 1
        # Hash storage (simula coluna data_hash do banco)
        self._auction_hashes: dict[int, str] = {}
        self._lot_hashes: dict[int, str] = {}
        self._item_hashes: dict[int, str] = {}

    # === AUCTION ===
    def get_auction_by_edle(self, edle: str) -> Optional[Auction]:
        for auction in self._auctions.values():
            if auction.edle == edle:
                # Adiciona data_hash como atributo para compatibilidade
                auction.data_hash = self._auction_hashes.get(auction.id)
                return auction
        return None

    def get_active_auction_edles(self) -> set[str]:
        return {a.edle for a in self._auctions.values() if a.is_active}

    def create_auction(self, auction: Auction, data_hash: str) -> int:
        auction_id = self._next_auction_id
        self._next_auction_id += 1
        auction.id = auction_id
        self._auctions[auction_id] = auction
        self._auction_hashes[auction_id] = data_hash
        return auction_id

    def update_auction(self, auction: Auction, data_hash: str) -> None:
        if auction.id in self._auctions:
            self._auctions[auction.id] = auction
            self._auction_hashes[auction.id] = data_hash

    def soft_delete_auctions(self, edles: set[str], batch_id: UUID) -> int:
        count = 0
        for auction in self._auctions.values():
            if auction.edle in edles and auction.is_active:
                auction.is_active = False
                self._audit.append({
                    "entity_type": "auction",
                    "entity_id": auction.id,
                    "action": "DELETE",
                    "sync_batch_id": str(batch_id)
                })
                count += 1
        return count

    def update_auction_error(self, edle: str, error_status: str, error_message: str) -> None:
        for auction in self._auctions.values():
            if auction.edle == edle:
                # Armazena erro em atributos dinâmicos (para testes)
                auction.error_status = error_status
                auction.error_message = error_message
                break

    # === LOT ===
    def get_lot_by_rfb_id(self, auction_id: int, rfb_id: int) -> Optional[Lot]:
        for lot in self._lots.values():
            if lot.auction_id == auction_id and lot.rfb_id == rfb_id:
                lot.data_hash = self._lot_hashes.get(lot.id)
                return lot
        return None

    def get_active_lot_rfb_ids(self, auction_id: int) -> set[int]:
        return {
            lot.rfb_id for lot in self._lots.values()
            if lot.auction_id == auction_id and lot.is_active
        }

    def create_lot(self, lot: Lot, auction_id: int, data_hash: str) -> int:
        lot_id = self._next_lot_id
        self._next_lot_id += 1
        lot.id = lot_id
        lot.auction_id = auction_id
        self._lots[lot_id] = lot
        self._lot_hashes[lot_id] = data_hash
        return lot_id

    def update_lot(self, lot: Lot, data_hash: str) -> None:
        if lot.id in self._lots:
            self._lots[lot.id] = lot
            self._lot_hashes[lot.id] = data_hash

    def soft_delete_lots(self, auction_id: int, rfb_ids: set[int], batch_id: UUID) -> int:
        count = 0
        for lot in self._lots.values():
            if lot.auction_id == auction_id and lot.rfb_id in rfb_ids and lot.is_active:
                lot.is_active = False
                self._audit.append({
                    "entity_type": "lot",
                    "entity_id": lot.id,
                    "action": "DELETE",
                    "sync_batch_id": str(batch_id)
                })
                count += 1
        return count

    # === ITEM ===
    def get_item_by_index(self, lot_id: int, item_index: int) -> Optional[Item]:
        for item in self._items.values():
            if item.lot_id == lot_id and getattr(item, 'item_index', None) == item_index:
                item.data_hash = self._item_hashes.get(item.id)
                return item
        return None

    def create_item(self, item: Item, lot_id: int, item_index: int, data_hash: str) -> int:
        item_id = self._next_item_id
        self._next_item_id += 1
        item.id = item_id
        item.lot_id = lot_id
        item.item_index = item_index
        self._items[item_id] = item
        self._item_hashes[item_id] = data_hash
        return item_id

    def update_item(self, item: Item, data_hash: str) -> None:
        if item.id in self._items:
            self._items[item.id] = item
            self._item_hashes[item.id] = data_hash

    def replace_items_for_lot(self, lot_id: int, items: list[Item], batch_id: UUID) -> None:
        # Remove existing items for lot
        to_remove = [k for k, v in self._items.items() if v.lot_id == lot_id]
        for k in to_remove:
            del self._items[k]
            if k in self._item_hashes:
                del self._item_hashes[k]

        # Add new items
        for idx, item in enumerate(items):
            item_id = self._next_item_id
            self._next_item_id += 1
            item.id = item_id
            item.lot_id = lot_id
            item.item_index = idx
            self._items[item_id] = item

    # === LOT IMAGE ===
    def replace_images_for_lot(self, lot_id: int, images: list[LotImage]) -> None:
        # Remove existing images for lot
        to_remove = [k for k, v in self._images.items() if v.lot_id == lot_id]
        for k in to_remove:
            del self._images[k]

        # Add new images (usando replace para frozen dataclass)
        from dataclasses import replace
        for image in images:
            image_id = self._next_image_id
            self._next_image_id += 1
            new_image = replace(image, id=image_id, lot_id=lot_id)
            self._images[image_id] = new_image

    # === AVISO/ERRATA ===
    def replace_avisos_for_auction(self, auction_id: int, avisos: list[AvisoErrata]) -> None:
        # Remove existing avisos for auction
        to_remove = [k for k, v in self._avisos.items() if v.auction_id == auction_id]
        for k in to_remove:
            del self._avisos[k]

        # Add new avisos
        from dataclasses import replace
        for aviso in avisos:
            aviso_id = self._next_aviso_id
            self._next_aviso_id += 1
            new_aviso = replace(aviso, id=aviso_id, auction_id=auction_id, lot_id=None)
            self._avisos[aviso_id] = new_aviso

    def replace_avisos_for_lot(self, lot_id: int, avisos: list[AvisoErrata]) -> None:
        # Remove existing avisos for lot
        to_remove = [k for k, v in self._avisos.items() if v.lot_id == lot_id]
        for k in to_remove:
            del self._avisos[k]

        # Add new avisos
        from dataclasses import replace
        for aviso in avisos:
            aviso_id = self._next_aviso_id
            self._next_aviso_id += 1
            new_aviso = replace(aviso, id=aviso_id, auction_id=None, lot_id=lot_id)
            self._avisos[aviso_id] = new_aviso

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
        self._audit.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "changed_fields": changed_fields,
            "sync_batch_id": str(batch_id) if batch_id else None
        })

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
        self._sync_errors.append({
            "sync_batch_id": str(batch_id),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace
        })

    # === CONNECTION ===
    def closeall(self) -> None:
        pass  # Noop para storage em memória

    # === TEST HELPERS ===
    def get_audit_entries(self) -> list[dict]:
        """Retorna todas as entradas de auditoria (para testes)."""
        return self._audit.copy()

    def get_sync_errors(self) -> list[dict]:
        """Retorna todos os erros de sincronização (para testes)."""
        return self._sync_errors.copy()

    def clear(self) -> None:
        """Limpa todos os dados (para testes)."""
        self._auctions.clear()
        self._lots.clear()
        self._items.clear()
        self._images.clear()
        self._avisos.clear()
        self._audit.clear()
        self._sync_errors.clear()
        self._auction_hashes.clear()
        self._lot_hashes.clear()
        self._item_hashes.clear()
        self._next_auction_id = 1
        self._next_lot_id = 1
        self._next_item_id = 1
        self._next_image_id = 1
        self._next_aviso_id = 1

