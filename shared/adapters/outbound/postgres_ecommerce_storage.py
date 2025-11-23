from shared.ports.ecommerce_storage import EcommerceStorage
from shared.domain.ecommerce.entities.product import Product
from shared.infrastructure.postgres import get_pool, with_postgres_connection

class PostgresEcommerceStorage(EcommerceStorage):
  def __init__(self):
    self.pool = get_pool()

  def get_product(self, id: str) -> Product:
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT * FROM products WHERE id = %s", (id,))
        return Product(**cur.fetchone())

  def get_product_by_url(self, url: str) -> Product | None:
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT * FROM products WHERE url = %s", (url,))
        row = cur.fetchone()
        if row is None:
          return None
        return Product(**row)

  def get_products(self, limit: int = 100, offset: int = 0, where_clause: str = "") -> list[Product]:
    if where_clause:
      where_clause = f"WHERE {where_clause}"
    else:
      where_clause = ""
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM products {where_clause} LIMIT %s OFFSET %s", (limit, offset))
        return [Product(**row) for row in cur.fetchall()]

  def create_product(self, product: Product) -> None:
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute("INSERT INTO products (id, title, url, price, currency, is_installment_payment_available, max_installments, is_free_shipping, rating, rating_amount, sold_amount, extraction_date, version) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (product.id, product.title, product.url, product.price, product.currency.value, product.is_installment_payment_available, product.max_installments, product.is_free_shipping, product.rating, product.rating_amount, product.sold_amount, product.extraction_date, product.version))
        conn.commit()

  def update_product(self, product: Product) -> None:
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute("UPDATE products SET title = %s, url = %s, price = %s, currency = %s, is_installment_payment_available = %s, max_installments = %s, is_free_shipping = %s, rating = %s, rating_amount = %s, sold_amount = %s, extraction_date = %s, version = %s WHERE id = %s", (product.title, product.url, product.price, product.currency.value, product.is_installment_payment_available, product.max_installments, product.is_free_shipping, product.rating, product.rating_amount, product.sold_amount, product.extraction_date, product.version, product.id))
        conn.commit()

  def delete_product(self, id: str) -> None:
    with with_postgres_connection(self.pool) as conn:
      with conn.cursor() as cur:
        cur.execute("DELETE FROM products WHERE id = %s", (id,))
        conn.commit()


  def closeall(self):
    self.pool.closeall()