#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E2E test configuration for ml_prices.
Tests real database interactions with PostgreSQL.
"""

import os
import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config.ml_prices.settings import MLPricesSettings
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper
from shared.adapters.outbound.postgres_ecommerce_storage import PostgresEcommerceStorage
from shared.infrastructure.postgres import PostgresConnectionPool, get_pool


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
    print("🗄️  E2E DATABASE SETUP - ml_prices")
    print("=" * 80)
    print(f"📍 Connecting to: {db_config['host']}:{db_config['port']}")
    print(f"📦 Database: {db_config['database']}")
    print(f"👤 User: {db_config['user']}")
    
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
    # We don't drop the database after tests to allow inspection


@pytest.fixture(scope="session")
def db_schema(db_config, ensure_database_exists):
    """
    Setup database schema for tests.
    Creates the products table if it doesn't exist.
    """
    conn = psycopg2.connect(**db_config)
    
    try:
        with conn.cursor() as cur:
            # Create products table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR(255) PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    price DECIMAL(10, 2) NOT NULL,
                    currency VARCHAR(10) NOT NULL,
                    is_installment_payment_available BOOLEAN NOT NULL,
                    max_installments INTEGER,
                    is_free_shipping BOOLEAN NOT NULL,
                    rating INTEGER CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
                    rating_amount INTEGER CHECK (rating_amount IS NULL OR rating_amount >= 0),
                    sold_amount INTEGER CHECK (sold_amount IS NULL OR sold_amount >= 0),
                    extraction_date TIMESTAMP NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on url for faster lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_url 
                ON products(url)
            """)
            
            conn.commit()
            print("\n✅ Database schema ready")
    finally:
        conn.close()
    
    yield
    # Schema persists after tests


@pytest.fixture(scope="function")
def clean_database(db_config, db_schema):
    """
    Clean the products table before each test.
    This ensures test isolation.
    """
    conn = psycopg2.connect(**db_config)
    
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products")
            conn.commit()
            print("\n🧹 Database cleaned")
    finally:
        conn.close()
    
    yield
    
    # Optionally clean after test as well
    conn = psycopg2.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products")
            conn.commit()
    finally:
        conn.close()


# =========================
# APP FIXTURES
# =========================

@pytest.fixture(scope="function")
def ml_settings():
    """
    MLPrices settings for E2E tests.
    Uses smaller page count for faster tests.
    """
    return MLPricesSettings(
        pages_to_scrape=1,  # Only scrape 1 page for E2E tests
        headless=True,
        page_load_timeout=40,
        explicit_wait=20
    )


@pytest.fixture(scope="function")
def ml_scraper(ml_settings):
    """Mercado Livre scraper instance."""
    return MercadoLivreScraper(ml_settings)


@pytest.fixture(scope="function")
def pg_storage(clean_database, db_config):
    """
    PostgreSQL storage instance.
    Automatically cleaned before each test.
    
    Sets environment variables to ensure the storage connects to the test database.
    """
    # Reset global pool to ensure fresh connections
    import shared.infrastructure.postgres as pg_module
    pg_module._pool = None
    
    # Configure environment variables to point to test database
    # This ensures PostgresEcommerceStorage connects to the correct database
    original_env = {}
    test_env = {
        "POSTGRES_HOST": db_config["host"],
        "POSTGRES_DB": db_config["database"],
        "POSTGRES_USER": db_config["user"],
        "POSTGRES_PASSWORD": db_config["password"],
        "POSTGRES_PORT": str(db_config["port"])
    }
    
    # Save original values and set test values
    for key, value in test_env.items():
        original_env[key] = os.getenv(key)
        os.environ[key] = value
    
    try:
        storage = PostgresEcommerceStorage()
        
        yield storage
        
        # Cleanup
        storage.closeall()
    finally:
        # Restore original environment variables
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


@pytest.fixture(scope="function")
def db_inspector(db_config, clean_database):
    """
    Helper fixture to inspect database contents during tests.
    """
    class DatabaseInspector:
        def __init__(self, db_config):
            self.db_config = db_config
        
        def count_products(self):
            """Count total products in database."""
            conn = psycopg2.connect(**self.db_config)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM products")
                    return cur.fetchone()[0]
            finally:
                conn.close()
        
        def get_products(self):
            """Get all products from database."""
            conn = psycopg2.connect(**self.db_config)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, title, url, price, currency, 
                               is_installment_payment_available, max_installments,
                               is_free_shipping, rating, rating_amount, sold_amount,
                               extraction_date, version
                        FROM products
                        ORDER BY created_at DESC
                    """)
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
            finally:
                conn.close()
        
        def get_product_by_url(self, url: str):
            """Get a specific product by URL."""
            conn = psycopg2.connect(**self.db_config)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, title, url, price, currency, 
                               is_installment_payment_available, max_installments,
                               is_free_shipping, rating, rating_amount, sold_amount,
                               extraction_date, version
                        FROM products
                        WHERE url = %s
                    """, (url,))
                    row = cur.fetchone()
                    if row:
                        columns = [desc[0] for desc in cur.description]
                        return dict(zip(columns, row))
                    return None
            finally:
                conn.close()
    
    return DatabaseInspector(db_config)


# =========================
# NOTES
# =========================
# pytest_sessionstart is not defined here because pytest only executes one per session.
# The root conftest.py already defines it and shows test configuration.
# E2E-specific information is displayed by fixture prints (e.g., ensure_database_exists)
# and is documented in tests/e2e/ml_prices/README.md

