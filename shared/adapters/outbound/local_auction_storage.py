from typing import Optional
from uuid import UUID
import logging

from shared.ports.auction_storage import AuctionStorage, NCMStorage, RevenueStorage
from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata, NcmTaxRates, SimplesNacionalTax


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


class LocalNCMStorage(NCMStorage):
    """Adapter local para armazenamento de taxas NCM em memória"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Taxas padrão (NCM=0) - valores default
        self.default_rates = NcmTaxRates(
            ipi=0.20,
            ii=0.20,
            icms=0.18,
            cbs=0.092,
            ibs=0.088
        )
        # Dicionário para armazenar taxas específicas por NCM
        self.ncm_rates: dict[str, NcmTaxRates] = {}

    def get_tax_rates_by_ncm(self, ncm: str) -> NcmTaxRates:
        """Retorna taxas para NCM específico ou default se não encontrado"""
        return self.ncm_rates.get(ncm, self.default_rates)

    def get_default_tax_rates(self) -> NcmTaxRates:
        """Retorna taxas default"""
        return self.default_rates

    def add_ncm_tax_rates(self, ncm: str, rates: NcmTaxRates) -> None:
        """Adiciona taxas para um NCM específico"""
        self.ncm_rates[ncm] = rates


class LocalRevenueStorage(RevenueStorage):
    """Adapter local para armazenamento de receita em memória"""

    def __init__(self, revenue_last_12months: float = 0.0):
        self.logger = logging.getLogger(__name__)
        self._revenue_last_12months = revenue_last_12months

        # Tabela de faixas progressivas do Simples Nacional (Comércio - Anexo I)
        # Baseado na Lei Complementar 123/2006
        self.simples_brackets = [
            # (limite_superior, aliquota, deducao)
            (180_000.00, 0.04, 0.0),           # Até 180k: 4%
            (360_000.00, 0.073, 5_940.00),     # 180k - 360k
            (720_000.00, 0.095, 13_860.00),    # 360k - 720k
            (1_800_000.00, 0.107, 22_500.00),  # 720k - 1.8M
            (3_600_000.00, 0.143, 87_300.00),  # 1.8M - 3.6M
            (4_800_000.00, 0.19, 378_000.00),  # 3.6M - 4.8M
        ]

        self.default_simples_nacional_tax = SimplesNacionalTax(rate=0.04, deducao=0.0)

    def get_revenue_last_12months(self) -> float:
        """Retorna receita dos últimos 12 meses"""
        return self._revenue_last_12months

    def set_revenue_last_12months(self, revenue: float) -> None:
        """Define receita dos últimos 12 meses"""
        if revenue < 0:
            raise ValueError("Revenue cannot be negative")
        self._revenue_last_12months = revenue

    def get_simples_nacional_tax(self, revenue_last_12months: float) -> SimplesNacionalTax:
        """Retorna taxa do Simples Nacional baseada na receita"""
        # Se receita é 0, retorna taxa default (modo fixed)
        if revenue_last_12months == 0.0:
            return self.default_simples_nacional_tax

        # Busca faixa apropriada
        for limite, aliquota, deducao in self.simples_brackets:
            if revenue_last_12months <= limite:
                return SimplesNacionalTax(rate=aliquota, deducao=deducao)

        # Acima do limite do Simples Nacional
        raise ValueError(f"Revenue {revenue_last_12months} exceeds Simples Nacional limit")

    def get_fixed_simples_nacional_tax(self) -> SimplesNacionalTax:
        """Retorna taxa fixa default"""
        return self.default_simples_nacional_tax
