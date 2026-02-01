import json
import logging
from typing import List

from shared.domain.base_product.entities import BaseProduct
from shared.infrastructure.postgres import PostgresConnectionPool, with_postgres_connection
from shared.ports.base_product_storage import BaseProductStorage

logger = logging.getLogger(__name__)


class PostgresBaseProductStorage(BaseProductStorage):
    """PostgreSQL implementation of BaseProductStorage."""

    def __init__(self, pool: PostgresConnectionPool | None = None):
        self._pool = pool or PostgresConnectionPool()

    def get_by_id(self, id: int) -> BaseProduct | None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, brand, model, color, other,
                           search_signature, created_at, updated_at
                    FROM base_products
                    WHERE id = %s
                    """,
                    (id,)
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_entity(row)

    def search(
        self,
        name: str | None = None,
        brand: str | None = None,
        model: str | None = None,
        limit: int = 10
    ) -> List[BaseProduct]:
        conditions = []
        params: list = []

        if name:
            conditions.append(
                "to_tsvector('portuguese', name) @@ plainto_tsquery('portuguese', %s)"
            )
            params.append(name)

        if brand:
            conditions.append("LOWER(brand) = LOWER(%s)")
            params.append(brand)

        if model:
            conditions.append("LOWER(model) LIKE LOWER(%s)")
            params.append(f"%{model}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id, name, brand, model, color, other,
                           search_signature, created_at, updated_at
                    FROM base_products
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params
                )
                rows = cursor.fetchall()
                return [self._row_to_entity(row) for row in rows]

    def find_by_signature(self, signature: str) -> BaseProduct | None:
        normalized = signature.lower().strip()
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, brand, model, color, other,
                           search_signature, created_at, updated_at
                    FROM base_products
                    WHERE LOWER(search_signature) = %s
                    """,
                    (normalized,)
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_entity(row)

    def create(self, base_product: BaseProduct) -> BaseProduct:
        signature = base_product.to_search_signature()
        other_json = json.dumps(base_product.other) if base_product.other else "{}"

        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO base_products (name, brand, model, color, other, search_signature)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING id, created_at, updated_at
                    """,
                    (
                        base_product.name,
                        base_product.brand,
                        base_product.model,
                        base_product.color,
                        other_json,
                        signature
                    )
                )
                row = cursor.fetchone()
                conn.commit()

                base_product.id = row[0]
                base_product.created_at = row[1]
                base_product.updated_at = row[2]
                return base_product

    def update(self, base_product: BaseProduct) -> None:
        if base_product.id is None:
            raise ValueError("Cannot update base product without ID")

        signature = base_product.to_search_signature()
        other_json = json.dumps(base_product.other) if base_product.other else "{}"

        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE base_products
                    SET name = %s, brand = %s, model = %s, color = %s,
                        other = %s::jsonb, search_signature = %s
                    WHERE id = %s
                    """,
                    (
                        base_product.name,
                        base_product.brand,
                        base_product.model,
                        base_product.color,
                        other_json,
                        signature,
                        base_product.id
                    )
                )
                conn.commit()

    def delete(self, id: int) -> None:
        with with_postgres_connection(self._pool) as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM base_products WHERE id = %s", (id,))
                conn.commit()

    def closeall(self) -> None:
        self._pool.closeall()

    def _row_to_entity(self, row: tuple) -> BaseProduct:
        """Convert database row to BaseProduct entity."""
        return BaseProduct(
            id=row[0],
            name=row[1],
            brand=row[2],
            model=row[3],
            color=row[4],
            other=row[5] if isinstance(row[5], dict) else {},
            created_at=row[7],
            updated_at=row[8]
        )
