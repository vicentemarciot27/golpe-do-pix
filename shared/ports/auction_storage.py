from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.entities.item import Item
from shared.domain.auction.value_objects import LotImage, AvisoErrata, NcmTaxRates, SimplesNacionalTax


class AuctionStorage(ABC):
    """Interface para persistência de dados de leilões RFB."""

    # === AUCTION ===
    @abstractmethod
    def get_auction_by_edle(self, edle: str) -> Optional[Auction]:
        """Busca auction pelo edle (ID curto RFB)."""
        pass

    @abstractmethod
    def get_active_auction_edles(self) -> set[str]:
        """Retorna set de edles de todos os auctions ativos."""
        pass

    @abstractmethod
    def create_auction(self, auction: Auction, data_hash: str) -> int:
        """Cria auction e retorna o ID gerado."""
        pass

    @abstractmethod
    def update_auction(self, auction: Auction, data_hash: str) -> None:
        """Atualiza auction existente."""
        pass

    @abstractmethod
    def soft_delete_auctions(self, edles: set[str], batch_id: UUID) -> int:
        """Marca auctions como inativos e retorna quantidade afetada."""
        pass

    @abstractmethod
    def update_auction_error(self, edle: str, error_status: str, error_message: str) -> None:
        """Atualiza status de erro de um auction."""
        pass

    # === LOT ===
    @abstractmethod
    def get_lot_by_rfb_id(self, auction_id: int, rfb_id: int) -> Optional[Lot]:
        """Busca lot pelo rfb_id dentro de um auction."""
        pass

    @abstractmethod
    def get_active_lot_rfb_ids(self, auction_id: int) -> set[int]:
        """Retorna set de rfb_ids de todos os lots ativos de um auction."""
        pass

    @abstractmethod
    def create_lot(self, lot: Lot, auction_id: int, data_hash: str) -> int:
        """Cria lot e retorna o ID gerado."""
        pass

    @abstractmethod
    def update_lot(self, lot: Lot, data_hash: str) -> None:
        """Atualiza lot existente."""
        pass

    @abstractmethod
    def soft_delete_lots(self, auction_id: int, rfb_ids: set[int], batch_id: UUID) -> int:
        """Marca lots como inativos e retorna quantidade afetada."""
        pass

    # === ITEM ===
    @abstractmethod
    def get_item_by_index(self, lot_id: int, item_index: int) -> Optional[Item]:
        """Busca item pelo índice dentro de um lot."""
        pass

    @abstractmethod
    def create_item(self, item: Item, lot_id: int, item_index: int, data_hash: str) -> int:
        """Cria item e retorna o ID gerado."""
        pass

    @abstractmethod
    def update_item(self, item: Item, data_hash: str) -> None:
        """Atualiza item existente."""
        pass

    @abstractmethod
    def replace_items_for_lot(self, lot_id: int, items: list[Item], batch_id: UUID) -> None:
        """Substitui todos os items de um lot (delete + insert)."""
        pass

    # === LOT IMAGE ===
    @abstractmethod
    def replace_images_for_lot(self, lot_id: int, images: list[LotImage]) -> None:
        """Substitui todas as imagens de um lot (delete + insert)."""
        pass

    # === AVISO/ERRATA ===
    @abstractmethod
    def replace_avisos_for_auction(self, auction_id: int, avisos: list[AvisoErrata]) -> None:
        """Substitui todos os avisos de um auction (delete + insert)."""
        pass

    @abstractmethod
    def replace_avisos_for_lot(self, lot_id: int, avisos: list[AvisoErrata]) -> None:
        """Substitui todos os avisos de um lot (delete + insert)."""
        pass

    # === AUDIT ===
    @abstractmethod
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
        """Registra entrada de auditoria."""
        pass

    # === SYNC ERRORS ===
    @abstractmethod
    def log_sync_error(
        self,
        batch_id: UUID,
        entity_type: str,
        entity_id: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str]
    ) -> None:
        """Registra erro de sincronização."""
        pass

    # === CONNECTION ===
    @abstractmethod
    def closeall(self) -> None:
        """Fecha todas as conexões."""
        pass


class NCMStorage(ABC):
    @abstractmethod
    def get_tax_rates_by_ncm(self, ncm: str) -> NcmTaxRates:
        """Retorna alíquotas IPI, II, ICMS, CBS, IBS para um NCM"""
        pass

    @abstractmethod
    def get_default_tax_rates(self) -> NcmTaxRates:
        """Retorna alíquotas default (ncm=0)"""
        pass


class RevenueStorage(ABC):
    @abstractmethod
    def get_revenue_last_12months(self) -> float:
        pass

    @abstractmethod
    def get_simples_nacional_tax(self, revenue_last_12months: float) -> SimplesNacionalTax:
        pass

    @abstractmethod
    def get_fixed_simples_nacional_tax(self) -> SimplesNacionalTax:
        pass
