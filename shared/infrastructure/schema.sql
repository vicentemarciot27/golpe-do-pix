-- Database schema for golpe-do-pix
-- PostgreSQL 16+
-- This file is idempotent - safe to run multiple times

-- =========================
-- HELPER FUNCTIONS
-- =========================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================
-- BASE PRODUCT DOMAIN
-- =========================

-- Base Products table (canonical products for price comparison)
CREATE TABLE IF NOT EXISTS base_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    brand VARCHAR(255),
    model VARCHAR(255),
    color VARCHAR(100),
    other JSONB DEFAULT '{}',
    search_signature VARCHAR(1000),  -- Normalized signature for matching
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_base_products_name ON base_products USING gin(to_tsvector('portuguese', name));
CREATE INDEX IF NOT EXISTS idx_base_products_brand ON base_products(brand);
CREATE INDEX IF NOT EXISTS idx_base_products_model ON base_products(model);
CREATE INDEX IF NOT EXISTS idx_base_products_signature ON base_products(search_signature);
CREATE INDEX IF NOT EXISTS idx_base_products_other ON base_products USING gin(other);

COMMENT ON TABLE base_products IS 'Canonical products for cross-platform price comparison';
COMMENT ON COLUMN base_products.search_signature IS 'Normalized signature: "brand name model" for matching';
COMMENT ON COLUMN base_products.other IS 'Product-specific attributes (storage, connectivity, etc.)';

-- =========================
-- ECOMMERCE DOMAIN
-- =========================

-- Products table (stores scraped product data from ecommerce platforms)
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(255) PRIMARY KEY,
    base_product_id INTEGER REFERENCES base_products(id) ON DELETE SET NULL,
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
    search_key VARCHAR(500),  -- ML search key used to find this product
    is_relevant BOOLEAN,  -- Whether this product is relevant to the base product
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_url ON products(url);
CREATE INDEX IF NOT EXISTS idx_products_extraction_date ON products(extraction_date DESC);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_products_base_product_id ON products(base_product_id);
CREATE INDEX IF NOT EXISTS idx_products_search_key ON products(search_key);
CREATE INDEX IF NOT EXISTS idx_products_is_relevant ON products(is_relevant);

COMMENT ON TABLE products IS 'Stores product data scraped from ecommerce platforms like Mercado Livre';
COMMENT ON COLUMN products.id IS 'Unique identifier (UUID)';
COMMENT ON COLUMN products.url IS 'Product URL (unique per product)';
COMMENT ON COLUMN products.version IS 'Optimistic locking version number';
COMMENT ON COLUMN products.extraction_date IS 'When the product data was scraped';

-- =========================
-- AUCTION DOMAIN
-- =========================

-- Auctions table (editais/leilões da RFB)
CREATE TABLE IF NOT EXISTS auctions (
    id SERIAL PRIMARY KEY,
    -- Identificação RFB
    edital VARCHAR(50) NOT NULL UNIQUE,
    edle VARCHAR(50) NOT NULL UNIQUE,
    -- Campos da entidade (shared/domain/auction/entities/auction.py)
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
    -- Hash e controle
    data_hash VARCHAR(64),
    error_status VARCHAR(50),  -- NULL, 'COLLECTION_ERROR', 'PARSING_ERROR'
    error_message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auctions_edle ON auctions(edle);
CREATE INDEX IF NOT EXISTS idx_auctions_is_active ON auctions(is_active);
CREATE INDEX IF NOT EXISTS idx_auctions_error_status ON auctions(error_status);

COMMENT ON TABLE auctions IS 'Editais/leilões da Receita Federal do Brasil';
COMMENT ON COLUMN auctions.edle IS 'ID curto para API RFB: "800100/10/2025"';
COMMENT ON COLUMN auctions.edital IS 'ID completo: "0800100/000010/2025"';
COMMENT ON COLUMN auctions.data_hash IS 'SHA256 hash para detecção de mudanças';
COMMENT ON COLUMN auctions.is_active IS 'Soft delete flag';

-- Lots table (lotes dentro de um leilão)
CREATE TABLE IF NOT EXISTS lots (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER NOT NULL REFERENCES auctions(id) ON DELETE CASCADE,
    -- Identificação RFB
    rfb_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    edle VARCHAR(50) NOT NULL,
    edital VARCHAR(50) NOT NULL,
    -- Campos da entidade (shared/domain/auction/entities/lot.py)
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
    -- Hash e controle
    data_hash VARCHAR(64),
    error_status VARCHAR(50),
    error_message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(auction_id, rfb_id)
);

CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id);
CREATE INDEX IF NOT EXISTS idx_lots_rfb_id_edle ON lots(rfb_id, edle);
CREATE INDEX IF NOT EXISTS idx_lots_is_active ON lots(is_active);
CREATE INDEX IF NOT EXISTS idx_lots_error_status ON lots(error_status);

COMMENT ON TABLE lots IS 'Lotes dentro de um leilão da RFB';
COMMENT ON COLUMN lots.rfb_id IS 'loleNrSq - ID sequencial único do lote na RFB';
COMMENT ON COLUMN lots.valor_minimo IS 'Valor em centavos (1000 = R$ 10,00)';

-- Items table (mercadorias dentro de um lote)
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    base_product_id INTEGER REFERENCES base_products(id) ON DELETE SET NULL,
    -- Posição na lista (para identificação)
    item_index INTEGER NOT NULL,
    -- Campos da entidade (shared/domain/auction/entities/item.py)
    recinto_armazenador VARCHAR(255) NOT NULL,
    quantidade INTEGER NOT NULL,
    unidade_medida VARCHAR(20) NOT NULL,
    descricao TEXT NOT NULL,
    nr_referencia VARCHAR(100),
    -- Hash e controle
    data_hash VARCHAR(64),
    error_status VARCHAR(50),
    error_message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lot_id, item_index)
);

CREATE INDEX IF NOT EXISTS idx_items_lot_id ON items(lot_id);
CREATE INDEX IF NOT EXISTS idx_items_is_active ON items(is_active);
CREATE INDEX IF NOT EXISTS idx_items_base_product_id ON items(base_product_id);

COMMENT ON TABLE items IS 'Mercadorias/produtos dentro de um lote';

-- Lot Images table
CREATE TABLE IF NOT EXISTS lot_images (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    -- Campos do value object (shared/domain/auction/value_objects.py)
    rfb_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    thumbnail_url TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    is_featured BOOLEAN DEFAULT FALSE,
    -- Controle
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lot_id, rfb_id)
);

CREATE INDEX IF NOT EXISTS idx_lot_images_lot_id ON lot_images(lot_id);

COMMENT ON TABLE lot_images IS 'Imagens associadas a lotes';
COMMENT ON COLUMN lot_images.rfb_id IS 'imllNrSq - ID da imagem na RFB';

-- Avisos e Erratas table
CREATE TABLE IF NOT EXISTS avisos_erratas (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
    lot_id INTEGER REFERENCES lots(id) ON DELETE CASCADE,
    -- Campos do value object
    data TIMESTAMP NOT NULL,
    codigo_tipo INTEGER NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    texto TEXT NOT NULL,
    -- Controle
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT avisos_parent_check CHECK (
        (auction_id IS NOT NULL AND lot_id IS NULL) OR
        (auction_id IS NULL AND lot_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_avisos_auction_id ON avisos_erratas(auction_id);
CREATE INDEX IF NOT EXISTS idx_avisos_lot_id ON avisos_erratas(lot_id);

COMMENT ON TABLE avisos_erratas IS 'Avisos e erratas publicados para auctions ou lots';
COMMENT ON COLUMN avisos_erratas.codigo_tipo IS '1=Aviso, 2=Errata';

-- =========================
-- AUCTION END DOMAIN
-- =========================

-- Auction End Results (main aggregate)
CREATE TABLE IF NOT EXISTS auction_end_results (
    id SERIAL PRIMARY KEY,
    edital VARCHAR(50) NOT NULL UNIQUE,  -- "0800100/000008/2025"
    auction_id INTEGER,  -- Optional FK to auctions table
    auction_date TIMESTAMP NOT NULL,  -- Date when auction was held
    report_date TIMESTAMP NOT NULL,   -- Date when report was generated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auction_end_edital ON auction_end_results(edital);
CREATE INDEX IF NOT EXISTS idx_auction_end_auction_id ON auction_end_results(auction_id);

-- Lot Results (results per lot)
CREATE TABLE IF NOT EXISTS auction_end_lot_results (
    id SERIAL PRIMARY KEY,
    auction_end_result_id INTEGER NOT NULL REFERENCES auction_end_results(id) ON DELETE CASCADE,
    lot_number INTEGER NOT NULL,  -- Lote:X
    winner_cnpj_cpf VARCHAR(20),  -- "60.530.186/0001-12" or NULL if no winner
    winner_name VARCHAR(255),      -- Company/person name
    winning_value DECIMAL(15, 2),  -- Final winning value in BRL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(auction_end_result_id, lot_number)
);

CREATE INDEX IF NOT EXISTS idx_lot_results_auction_end ON auction_end_lot_results(auction_end_result_id);
CREATE INDEX IF NOT EXISTS idx_lot_results_winner ON auction_end_lot_results(winner_cnpj_cpf);

-- Proposals (Relação de Propostas)
CREATE TABLE IF NOT EXISTS auction_end_proposals (
    id SERIAL PRIMARY KEY,
    lot_result_id INTEGER NOT NULL REFERENCES auction_end_lot_results(id) ON DELETE CASCADE,
    bidder_id VARCHAR(50) NOT NULL,  -- "licitante12607"
    status VARCHAR(100) NOT NULL,     -- "Classificada", "Recusada - Valor Insuficiente", etc.
    value DECIMAL(15, 2) NOT NULL,    -- Proposal value in BRL
    timestamp TIMESTAMP NOT NULL,     -- Date/time of proposal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proposals_lot_result ON auction_end_proposals(lot_result_id);
CREATE INDEX IF NOT EXISTS idx_proposals_bidder ON auction_end_proposals(bidder_id);

-- Bid History (Histórico de Lances)
CREATE TABLE IF NOT EXISTS auction_end_bid_history (
    id SERIAL PRIMARY KEY,
    lot_result_id INTEGER NOT NULL REFERENCES auction_end_lot_results(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,        -- Seq. column
    timestamp TIMESTAMP NOT NULL,     -- Data/Hora Lance
    value DECIMAL(15, 2) NOT NULL,    -- Valor Lance (R$)
    status VARCHAR(100) NOT NULL,     -- "Vencedor", "Perdedor", "Empatado", etc.
    bidder_id VARCHAR(50) NOT NULL,   -- "licitante12607"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bid_history_lot_result ON auction_end_bid_history(lot_result_id);
CREATE INDEX IF NOT EXISTS idx_bid_history_bidder ON auction_end_bid_history(bidder_id);
CREATE INDEX IF NOT EXISTS idx_bid_history_status ON auction_end_bid_history(status);

-- =========================
-- AUDIT & ERROR TRACKING
-- =========================

-- Auction Audit table (histórico de mudanças)
CREATE TABLE IF NOT EXISTS auction_audit (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- 'auction', 'lot', 'item'
    entity_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL,        -- 'CREATE', 'UPDATE', 'DELETE', 'ERROR'
    old_hash VARCHAR(64),
    new_hash VARCHAR(64),
    changed_fields JSONB,
    error_message TEXT,
    sync_batch_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON auction_audit(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON auction_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_batch ON auction_audit(sync_batch_id);

COMMENT ON TABLE auction_audit IS 'Histórico de mudanças em entidades de leilão';
COMMENT ON COLUMN auction_audit.sync_batch_id IS 'UUID do batch de sincronização';

-- Sync Errors table (erros de sincronização)
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
);

CREATE INDEX IF NOT EXISTS idx_sync_errors_batch ON sync_errors(sync_batch_id);
CREATE INDEX IF NOT EXISTS idx_sync_errors_unresolved ON sync_errors(resolved_at) WHERE resolved_at IS NULL;

COMMENT ON TABLE sync_errors IS 'Erros ocorridos durante sincronização';

-- =========================
-- TRIGGERS
-- =========================

-- Drop existing triggers to ensure idempotency
DROP TRIGGER IF EXISTS update_base_products_updated_at ON base_products;
DROP TRIGGER IF EXISTS update_products_updated_at ON products;
DROP TRIGGER IF EXISTS update_auctions_updated_at ON auctions;
DROP TRIGGER IF EXISTS update_lots_updated_at ON lots;
DROP TRIGGER IF EXISTS update_items_updated_at ON items;
DROP TRIGGER IF EXISTS update_lot_images_updated_at ON lot_images;
DROP TRIGGER IF EXISTS update_avisos_updated_at ON avisos_erratas;
DROP TRIGGER IF EXISTS update_auction_end_results_updated_at ON auction_end_results;
DROP TRIGGER IF EXISTS update_auction_end_lot_results_updated_at ON auction_end_lot_results;

-- Create triggers to automatically update updated_at column
CREATE TRIGGER update_base_products_updated_at
    BEFORE UPDATE ON base_products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auctions_updated_at
    BEFORE UPDATE ON auctions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lots_updated_at
    BEFORE UPDATE ON lots
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_items_updated_at
    BEFORE UPDATE ON items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lot_images_updated_at
    BEFORE UPDATE ON lot_images
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_avisos_updated_at
    BEFORE UPDATE ON avisos_erratas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auction_end_results_updated_at
    BEFORE UPDATE ON auction_end_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auction_end_lot_results_updated_at
    BEFORE UPDATE ON auction_end_lot_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================
-- VIEWS
-- =========================

-- View for lot results with winner summary
CREATE OR REPLACE VIEW v_auction_end_summary AS
SELECT
    aer.id AS auction_end_id,
    aer.edital,
    aer.auction_date,
    aer.report_date,
    COUNT(aelr.id) AS total_lots,
    COUNT(aelr.id) FILTER (WHERE aelr.winner_cnpj_cpf IS NOT NULL) AS lots_with_winner,
    COUNT(aelr.id) FILTER (WHERE aelr.winner_cnpj_cpf IS NULL) AS lots_without_winner,
    COALESCE(SUM(aelr.winning_value), 0) AS total_value
FROM auction_end_results aer
LEFT JOIN auction_end_lot_results aelr ON aer.id = aelr.auction_end_result_id
GROUP BY aer.id, aer.edital, aer.auction_date, aer.report_date;

-- View for winner ranking by total value
CREATE OR REPLACE VIEW v_winner_ranking AS
SELECT
    winner_cnpj_cpf,
    winner_name,
    COUNT(*) AS lots_won,
    SUM(winning_value) AS total_value,
    AVG(winning_value) AS avg_value_per_lot
FROM auction_end_lot_results
WHERE winner_cnpj_cpf IS NOT NULL
GROUP BY winner_cnpj_cpf, winner_name
ORDER BY total_value DESC;