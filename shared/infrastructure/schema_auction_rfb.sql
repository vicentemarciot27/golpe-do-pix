-- Database schema for RFB Auction data
-- PostgreSQL 16+

-- =========================
-- FUNCTIONS
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

-- Triggers to automatically update updated_at column
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

