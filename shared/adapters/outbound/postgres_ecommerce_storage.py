"""PostgreSQL storage adapter for ecommerce products."""

from typing import List

from shared.domain.ecommerce.entities.product import Product, Currency
from shared.infrastructure.postgres import PostgresConnectionPool, get_pool, with_postgres_connection
from shared.ports.ecommerce_storage import EcommerceStorage


class PostgresEcommerceStorage(EcommerceStorage):
    """PostgreSQL implementation of EcommerceStorage."""

    COLUMNS = [
        "id", "base_product_id", "title", "url", "price", "currency",
        "is_installment_payment_available", "max_installments", "is_free_shipping",
        "rating", "rating_amount", "sold_amount", "extraction_date",
        "search_key", "is_relevant", "version"
    ]

    def __init__(self, pool: PostgresConnectionPool | None = None):
        self._pool = pool or get_pool()

    @property
    def pool(self):
        """Backwards compatibility for tests."""
        return self._pool

    def get_product(self, id: str) -> Product:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(self.COLUMNS)} FROM products WHERE id = %s",
                    (id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Product not found: {id}")
                return self._row_to_product(row)

    def get_product_by_url(self, url: str) -> Product | None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(self.COLUMNS)} FROM products WHERE url = %s",
                    (url,)
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_product(row)

    def get_products(
        self,
        limit: int = 100,
        offset: int = 0,
        where_clause: str = ""
    ) -> List[Product]:
        where = f"WHERE {where_clause}" if where_clause else ""
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(self.COLUMNS)} FROM products {where} "
                    f"ORDER BY extraction_date DESC LIMIT %s OFFSET %s",
                    (limit, offset)
                )
                return [self._row_to_product(row) for row in cur.fetchall()]

    def get_products_by_base_product(
        self,
        base_product_id: int,
        only_relevant: bool = True,
        limit: int = 100
    ) -> List[Product]:
        """Get all products linked to a base product."""
        where = "WHERE base_product_id = %s"
        params: list = [base_product_id]

        if only_relevant:
            where += " AND is_relevant = TRUE"

        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(self.COLUMNS)} FROM products {where} "
                    f"ORDER BY price ASC LIMIT %s",
                    (*params, limit)
                )
                return [self._row_to_product(row) for row in cur.fetchall()]

    def create_product(self, product: Product) -> None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO products (
                        id, base_product_id, title, url, price, currency,
                        is_installment_payment_available, max_installments,
                        is_free_shipping, rating, rating_amount, sold_amount,
                        extraction_date, search_key, is_relevant, version
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        product.id,
                        getattr(product, 'base_product_id', None),
                        product.title,
                        product.url,
                        product.price,
                        product.currency.value,
                        product.is_installment_payment_available,
                        product.max_installments,
                        product.is_free_shipping,
                        product.rating,
                        product.rating_amount,
                        product.sold_amount,
                        product.extraction_date,
                        getattr(product, 'search_key', None),
                        getattr(product, 'is_relevant', None),
                        product.version
                    )
                )
                conn.commit()

    def update_product(self, product: Product) -> None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE products SET
                        base_product_id = %s, title = %s, url = %s, price = %s,
                        currency = %s, is_installment_payment_available = %s,
                        max_installments = %s, is_free_shipping = %s, rating = %s,
                        rating_amount = %s, sold_amount = %s, extraction_date = %s,
                        search_key = %s, is_relevant = %s, version = %s
                    WHERE id = %s
                    """,
                    (
                        getattr(product, 'base_product_id', None),
                        product.title,
                        product.url,
                        product.price,
                        product.currency.value,
                        product.is_installment_payment_available,
                        product.max_installments,
                        product.is_free_shipping,
                        product.rating,
                        product.rating_amount,
                        product.sold_amount,
                        product.extraction_date,
                        getattr(product, 'search_key', None),
                        getattr(product, 'is_relevant', None),
                        product.version,
                        product.id
                    )
                )
                conn.commit()

    def update_relevance(self, product_id: str, is_relevant: bool) -> None:
        """Update only the relevance flag for a product."""
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE products SET is_relevant = %s WHERE id = %s",
                    (is_relevant, product_id)
                )
                conn.commit()

    def delete_product(self, id: str) -> None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM products WHERE id = %s", (id,))
                conn.commit()

    def closeall(self) -> None:
        self._pool.closeall()

    def _row_to_product(self, row: tuple) -> Product:
        """Convert database row to Product entity."""
        return Product(
            id=row[0],
            base_product_id=row[1],
            title=row[2],
            url=row[3],
            price=float(row[4]),
            currency=Currency(row[5]),
            is_installment_payment_available=row[6],
            max_installments=row[7],
            is_free_shipping=row[8],
            rating=row[9],
            rating_amount=row[10],
            sold_amount=row[11],
            extraction_date=row[12],
            search_key=row[13],
            is_relevant=row[14],
            version=row[15]
        )
