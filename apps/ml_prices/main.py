import re
import uuid
from datetime import datetime

from config.ml_prices.settings import MLPricesSettings
from shared.ports.ecommerce_storage import EcommerceStorage
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper, Produto
from shared.domain.ecommerce.entities.product import Product, Currency


class MLPricesMain:
  def __init__(self, settings: MLPricesSettings, scraper: MercadoLivreScraper, storage: EcommerceStorage):
    self.settings = settings
    self.storage = storage
    self.scraper = scraper

  def run(self, search_term: str):
    products = self.scraper.scrape(search_term)
    for product in products:
      # check if product already exists in storage by url (if there's any chance that we will run many of those in parallel, an optimistic locking mechanism would be needed)
      if self.storage.get_product_by_url(product.url) is not None:
        # update product in storage
        product_for_storage = self._format_product_for_storage(product)
        self.storage.update_product(product_for_storage)
        continue
      # create product in storage
      product_for_storage = self._format_product_for_storage(product)
      self.storage.create_product(product_for_storage)

  def _format_product_for_storage(self, product: Produto) -> Product:
    # Adapting attribute names according to the Mercado Livre json example.
    def int_or_none(val):
      return int(val) if val is not None else None

    return Product(
      id=str(uuid.uuid4()),
      title=product.titulo,                          # maps to "titulo"
      url=product.url,                               # maps to "url"
      price=float(product.preco),                    # maps to "preco"
      currency=Currency.BRL,                         # maps to "moeda"
      is_installment_payment_available=bool(product.parcelamento),  # non-empty string means "available"
      max_installments=None,                         # not directly available in JSON
      is_free_shipping="grátis" in (product.frete or "").lower(),  # maps to "frete"
      rating=int_or_none(product.avaliacao),              # maps to "avaliacao"
      rating_amount=product.num_avaliacoes if product.num_avaliacoes is not None else None,          # maps to "num_avaliacoes"
      sold_amount=int_or_none(product.num_vendidos),      # maps to "num_vendidos"
      extraction_date=datetime.now()
    )


if __name__ == "__main__":
  import logging
  from shared.adapters.outbound.postgres_ecommerce_storage import PostgresEcommerceStorage
  logging.basicConfig(level=logging.INFO)
  settings = MLPricesSettings()
  scraper = MercadoLivreScraper(settings)
  storage = PostgresEcommerceStorage()
  try:
    main = MLPricesMain(settings, scraper, storage)
    logging.info("Starting MLPricesMain")
    main.run("smartphone xiaomi")
    logging.info("MLPricesMain finished")
  except Exception as e:
    logging.error(e)
  finally:
    storage.closeall()