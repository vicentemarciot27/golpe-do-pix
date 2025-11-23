import os
from psycopg2 import pool


class PostgresConnectionPool: # TODO: Implementar um sistema de migrations para o banco de dados
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