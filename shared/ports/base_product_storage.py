from abc import ABC, abstractmethod
from typing import List

from shared.domain.base_product.entities import BaseProduct


class BaseProductStorage(ABC):
    """Port for BaseProduct persistence operations."""

    @abstractmethod
    def get_by_id(self, id: int) -> BaseProduct | None:
        """Retrieve a base product by its ID."""
        pass

    @abstractmethod
    def search(
        self,
        name: str | None = None,
        brand: str | None = None,
        model: str | None = None,
        limit: int = 10
    ) -> List[BaseProduct]:
        """
        Search for base products by attributes.
        Uses fuzzy matching on name, brand, and model.
        """
        pass

    @abstractmethod
    def find_by_signature(self, signature: str) -> BaseProduct | None:
        """
        Find a base product by its search signature.
        Returns the closest match or None.
        """
        pass

    @abstractmethod
    def create(self, base_product: BaseProduct) -> BaseProduct:
        """Create a new base product and return it with its ID."""
        pass

    @abstractmethod
    def update(self, base_product: BaseProduct) -> None:
        """Update an existing base product."""
        pass

    @abstractmethod
    def delete(self, id: int) -> None:
        """Delete a base product by ID."""
        pass

    @abstractmethod
    def closeall(self) -> None:
        """Close all connections."""
        pass
