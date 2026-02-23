import os
from pathlib import Path
from psycopg2 import pool


def run_schema_file(pool_instance, schema_file: str | Path) -> None:
    """
    Run a SQL schema file against the database.

    Args:
        pool_instance: PostgresConnectionPool instance
        schema_file: Path to the SQL file
    """
    schema_path = Path(schema_file)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    sql_content = schema_path.read_text(encoding="utf-8")

    with with_postgres_connection(pool_instance) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_content)


def ensure_schema(pool_instance, schema_name: str) -> None:
    """
    Ensure a schema is applied to the database.
    Looks for schema file in shared/infrastructure/schema_{name}.sql

    Args:
        pool_instance: PostgresConnectionPool instance
        schema_name: Name of the schema (e.g., "auction_end")
    """
    infrastructure_dir = Path(__file__).parent
    schema_file = infrastructure_dir / f"schema_{schema_name}.sql"

    if schema_file.exists():
        try:
            run_schema_file(pool_instance, schema_file)
        except Exception as e:
            # Schema might already exist, that's OK
            if "already exists" not in str(e).lower():
                raise


class PostgresConnectionPool:
    """
    Simple PostgreSQL connection pool using psycopg2.
    Pass db_config as a dict: {
        "host": "...",
        "database": "...",
        "user": "...",
        "password": "...",
        "port": 5432
    }
    """
    def __init__(self, db_config = None, minconn=1, maxconn=5):
        if not db_config:
            db_config = { # TODO: Passar isso aqui para a pasta config
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "database": os.getenv("POSTGRES_DB", "golpe_do_pix"),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
                "port": os.getenv("POSTGRES_PORT", 5435)
            }
        self._pool = pool.SimpleConnectionPool(
            minconn,
            maxconn,
            **db_config
        )

    def get_conn(self):
        return self._pool.getconn()

    def put_conn(self, conn):
        self._pool.putconn(conn)

    def closeall(self):
        """Close all connections in the pool."""
        if self._pool and not self._pool.closed:
            self._pool.closeall()


def with_postgres_connection(pool: PostgresConnectionPool):
    """
    Context manager to yield a postgres connection and commit automatically.
    Usage:
        with with_postgres_connection(pool) as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    from contextlib import contextmanager

    @contextmanager
    def _connection():
        conn = pool.get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.put_conn(conn)
    return _connection()

# utility singleton for the connection pool
_pool = None
def get_pool(db_config=None, minconn=1, maxconn=5):
    global _pool
    if _pool is None:
        _pool = PostgresConnectionPool(db_config, minconn, maxconn)
    return _pool