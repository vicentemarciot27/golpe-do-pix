from typing import List
from abc import ABC, abstractmethod
from shared.domain.ecommerce.entities.product import Product


class EcommerceStorage(ABC):
  "Storage interface for ecommerce data (products, our offers, etc)"

  @abstractmethod
  def get_product(self, id: str) -> Product:
    pass

  @abstractmethod
  def get_product_by_url(self, url: str) -> Product | None:
    pass

  @abstractmethod
  def get_products(self, limit: int = 100, offset: int = 0, where_clause: str = "") -> List[Product]:
    pass

  @abstractmethod
  def create_product(self, product: Product) -> None:
    pass

  @abstractmethod
  def update_product(self, product: Product) -> None:
    pass

  @abstractmethod
  def delete_product(self, id: str) -> None:
    pass

  @abstractmethod
  def closeall(self) -> None:
    pass