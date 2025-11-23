from shared.ports.ecommerce_storage import EcommerceStorage
from shared.domain.ecommerce.entities.product import Product
import logging

class LocalEcommerceStorage(EcommerceStorage):
  def __init__(self):
    self.logger = logging.getLogger(__name__)
    self.products = []

  def get_product(self, id: str) -> Product:
    return next((product for product in self.products if product.id == id), None)
  
  def get_product_by_url(self, url: str) -> Product:
    return next((product for product in self.products if product.url == url), None)

  def get_products(self, limit: int = 100, offset: int = 0) -> list[Product]:
    return self.products[offset:offset+limit]

  def create_product(self, product: Product) -> None:
    self.products.append(product)

  def update_product(self, product: Product) -> None:
    self.products[self.products.index(product)] = product

  def delete_product(self, id: str) -> None:
    self.products.remove(next((product for product in self.products if product.id == id), None))

  def closeall(self) -> None:
    self.logger.info("No need to close all connections for local storage since it's in memory")
    pass