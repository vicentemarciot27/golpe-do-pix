#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E2E test configuration for rfb_auction_tools.

These tests make real HTTP requests to RFB API and use real PostgreSQL database.
Database configuration uses the test database (port 5436) for isolation.
"""

import os
import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from shared.adapters.outbound.postgres_auction_storage import PostgresAuctionStorage
from shared.infrastructure.postgres import PostgresConnectionPool


# =========================
# DATABASE SETUP
# =========================

def get_test_db_config():
    """
    Get database configuration for E2E tests.

    By default, uses port 5436 (db_test service from docker-compose.yml).
    This keeps test data isolated from the main application database (port 5435).
    """
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "database": os.getenv("POSTGRES_DB", "golpe_do_pix_test"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "port": int(os.getenv("POSTGRES_PORT", 5436))
    }


@pytest.fixture(scope="session")
def db_config():
    """Provide database configuration."""
    return get_test_db_config()


@pytest.fixture(scope="session")
def ensure_database_exists(db_config):
    """
    Ensure the test database exists.
    Creates it if it doesn't exist (connects to 'postgres' db first).
    """
    print("\n" + "=" * 80)
    print("🗄️  E2E DATABASE SETUP - rfb_auction_tools")
    print("=" * 80)
    print(f"📍 Connecting to: {db_config['host']}:{db_config['port']}")
    print(f"📦 Database: {db_config['database']}")

    # Connect to postgres database to create our test database if needed
    conn = psycopg2.connect(
        host=db_config["host"],
        database="postgres",
        user=db_config["user"],
        password=db_config["password"],
        port=db_config["port"]
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    try:
        with conn.cursor() as cur:
            # Check if database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_config["database"],)
            )
            if not cur.fetchone():
                print(f"📦 Creating database: {db_config['database']}")
                cur.execute(f"CREATE DATABASE {db_config['database']}")
                print(f"✅ Database created successfully")
            else:
                print(f"✅ Database already exists")
    finally:
        conn.close()

    print("=" * 80 + "\n")

    yield


@pytest.fixture(scope="session")
def db_schema(db_config, ensure_database_exists):
    """
    Setup database schema for tests.
    Creates auction tables if they don't exist.
    """
    conn = psycopg2.connect(**db_config)

    try:
        with conn.cursor() as cur:
            # Create update_updated_at_column function if not exists
            cur.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            # Create auctions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS auctions (
                    id SERIAL PRIMARY KEY,
                    edital VARCHAR(50) NOT NULL UNIQUE,
                    edle VARCHAR(50) NOT NULL UNIQUE,
                    tipo VARCHAR(20) NOT NULL,
                    orgao VARCHAR(100) NOT NULL,
                    cidade VARCHAR(100) NOT NULL,
                    unidade_nome VARCHAR(255) NOT NULL,
                    codigo_situacao INTEGER NOT NULL,
                    permite_pf BOOLEAN NOT NULL,
                    data_inicio_propostas TIMESTAMP NOT NULL,
                    data_fim_propostas TIMESTAMP NOT NULL,
                    data_abertura_lances TIMESTAMP NOT NULL,
                    total_lotes INTEGER NOT NULL DEFAULT 0,
                    mercadorias_apreendidas BOOLEAN,
                    data_classificacao TIMESTAMP,
                    forma_contato TEXT,
                    dados_publicacao TEXT,
                    numero_recursos INTEGER DEFAULT 0,
                    numero_avisos INTEGER DEFAULT 0,
                    numero_erratas INTEGER DEFAULT 0,
                    data_hash VARCHAR(64),
                    error_status VARCHAR(50),
                    error_message TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create lots table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lots (
                    id SERIAL PRIMARY KEY,
                    auction_id INTEGER NOT NULL REFERENCES auctions(id) ON DELETE CASCADE,
                    rfb_id INTEGER NOT NULL,
                    numero INTEGER NOT NULL,
                    edle VARCHAR(50) NOT NULL,
                    edital VARCHAR(50) NOT NULL,
                    tipo VARCHAR(100) NOT NULL,
                    orgao VARCHAR(100) NOT NULL,
                    cidade VARCHAR(100) NOT NULL,
                    valor_minimo BIGINT NOT NULL,
                    situacao_lote INTEGER NOT NULL,
                    situacao_edital INTEGER NOT NULL,
                    tipo_edital INTEGER NOT NULL,
                    permite_pf BOOLEAN NOT NULL,
                    possui_imagens BOOLEAN NOT NULL,
                    destaque BOOLEAN NOT NULL,
                    nr_avisos INTEGER DEFAULT 0,
                    nr_erratas INTEGER DEFAULT 0,
                    data_hash VARCHAR(64),
                    error_status VARCHAR(50),
                    error_message TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(auction_id, rfb_id)
                )
            """)

            # Create items table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
                    item_index INTEGER NOT NULL,
                    recinto_armazenador VARCHAR(255) NOT NULL,
                    quantidade INTEGER NOT NULL,
                    unidade_medida VARCHAR(20) NOT NULL,
                    descricao TEXT NOT NULL,
                    nr_referencia VARCHAR(100),
                    data_hash VARCHAR(64),
                    error_status VARCHAR(50),
                    error_message TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lot_id, item_index)
                )
            """)

            # Create lot_images table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lot_images (
                    id SERIAL PRIMARY KEY,
                    lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
                    rfb_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    thumbnail_url TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    is_featured BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lot_id, rfb_id)
                )
            """)

            # Create avisos_erratas table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS avisos_erratas (
                    id SERIAL PRIMARY KEY,
                    auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
                    lot_id INTEGER REFERENCES lots(id) ON DELETE CASCADE,
                    data TIMESTAMP NOT NULL,
                    codigo_tipo INTEGER NOT NULL,
                    tipo VARCHAR(20) NOT NULL,
                    texto TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT avisos_parent_check CHECK (
                        (auction_id IS NOT NULL AND lot_id IS NULL) OR
                        (auction_id IS NULL AND lot_id IS NOT NULL)
                    )
                )
            """)

            # Create auction_audit table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS auction_audit (
                    id SERIAL PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    action VARCHAR(20) NOT NULL,
                    old_hash VARCHAR(64),
                    new_hash VARCHAR(64),
                    changed_fields JSONB,
                    error_message TEXT,
                    sync_batch_id UUID,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create sync_errors table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_errors (
                    id SERIAL PRIMARY KEY,
                    sync_batch_id UUID NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id VARCHAR(100),
                    error_type VARCHAR(100) NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    retry_count INTEGER DEFAULT 0,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_auctions_edle ON auctions(edle)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_auctions_is_active ON auctions(is_active)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lots_is_active ON lots(is_active)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_lot_id ON items(lot_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lot_images_lot_id ON lot_images(lot_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_avisos_auction_id ON avisos_erratas(auction_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_avisos_lot_id ON avisos_erratas(lot_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON auction_audit(entity_type, entity_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_errors_batch ON sync_errors(sync_batch_id)")

            conn.commit()
            print("\n✅ Auction database schema ready")
    finally:
        conn.close()

    yield


@pytest.fixture(scope="function")
def clean_database(db_config, db_schema):
    """
    Clean the auction tables before each test.
    This ensures test isolation.
    """
    conn = psycopg2.connect(**db_config)

    try:
        with conn.cursor() as cur:
            # Delete in order due to foreign keys
            cur.execute("DELETE FROM sync_errors")
            cur.execute("DELETE FROM auction_audit")
            cur.execute("DELETE FROM avisos_erratas")
            cur.execute("DELETE FROM items")
            cur.execute("DELETE FROM lot_images")
            cur.execute("DELETE FROM lots")
            cur.execute("DELETE FROM auctions")
            conn.commit()
            print("\n🧹 Auction database cleaned")
    finally:
        conn.close()

    yield


@pytest.fixture(scope="function")
def test_db_pool(db_config, clean_database):
    """
    PostgreSQL connection pool for tests.
    """
    pool = PostgresConnectionPool(db_config, minconn=1, maxconn=3)
    yield pool
    pool.closeall()


@pytest.fixture(scope="function")
def auction_storage(test_db_pool):
    """
    PostgresAuctionStorage instance for tests.
    """
    storage = PostgresAuctionStorage(pool=test_db_pool)
    yield storage
