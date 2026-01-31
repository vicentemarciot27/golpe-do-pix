-- Database schema for Auction End Results
-- Stores parsed data from 'Relatório Relação de Vencedores' PDFs
-- PostgreSQL 16+
-- This file is idempotent - safe to run multiple times

-- =========================
-- HELPER FUNCTION
-- =========================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

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
-- TRIGGERS (drop and recreate to be idempotent)
-- =========================
DROP TRIGGER IF EXISTS update_auction_end_results_updated_at ON auction_end_results;
CREATE TRIGGER update_auction_end_results_updated_at
    BEFORE UPDATE ON auction_end_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_auction_end_lot_results_updated_at ON auction_end_lot_results;
CREATE TRIGGER update_auction_end_lot_results_updated_at
    BEFORE UPDATE ON auction_end_lot_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================
-- USEFUL VIEWS
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
