-- Database schema for golpe-do-pix
-- PostgreSQL 16+

-- =========================
-- ECOMMERCE DOMAIN
-- =========================

DROP TABLE IF EXISTS products;

DROP FUNCTION IF EXISTS update_updated_at_column;
DROP TRIGGER IF EXISTS update_products_updated_at ON products;

DROP INDEX IF EXISTS idx_products_url;
DROP INDEX IF EXISTS idx_products_extraction_date;
DROP INDEX IF EXISTS idx_products_price;


-- Products table (stores scraped product data from ecommerce platforms)
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
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_products_url ON products(url);
CREATE INDEX IF NOT EXISTS idx_products_extraction_date ON products(extraction_date DESC);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);

-- Comments
COMMENT ON TABLE products IS 'Stores product data scraped from ecommerce platforms like Mercado Livre';
COMMENT ON COLUMN products.id IS 'Unique identifier (UUID)';
COMMENT ON COLUMN products.url IS 'Product URL (unique per product)';
COMMENT ON COLUMN products.version IS 'Optimistic locking version number';
COMMENT ON COLUMN products.extraction_date IS 'When the product data was scraped';

-- =========================
-- TRIGGER: Update updated_at
-- =========================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

