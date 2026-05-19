-- Schema for Payments Transactional PostgreSQL DB
-- Version: 2025-05-19
-- Tables: transacciones, payment_links, mp_notifications
-- - added payment_method, payer_phone, mp_preference_id, fecha_registro
-- - added trigger touch_updated_at on transacciones
-- - SET NULL for external_reference on delete (graceful cleanup)

-- ── Function: touch_updated_at ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Table: transacciones ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transacciones (
    id                  SERIAL  PRIMARY KEY,
    payment_id          VARCHAR(100) UNIQUE NOT NULL,  -- Mercado Pago payment ID
    amount              DECIMAL(10,2)    NOT NULL,    -- monto esperado
    currency            VARCHAR(10)  DEFAULT 'PEN',
    status              VARCHAR(20),                   -- approved / pending / rejected
    status_detail       VARCHAR(100),                  -- detalle del estado
    status_code         VARCHAR(20),                   -- codigo adicional de MP
    external_reference  VARCHAR(200),                  -- WA_<telefono> o reserva_id
    payer_id            VARCHAR(100),                  -- payer.id de MP
    payer_email         VARCHAR(255),                  -- email del pagador
    payer_name          VARCHAR(255),                  -- nombre completo
    payer_phone         VARCHAR(50),                   -- telefono del pagador
    payment_method      VARCHAR(50),                   -- credit_card / debit_card / etc
    transaction_amount  DECIMAL(10,2),                 -- monto efectivamente procesado
    mp_preference_id    VARCHAR(100),                  -- preference_id de Mercado Pago
    date_approved       TIMESTAMP,                     -- fecha de aprobacion por MP
    date_created        TIMESTAMP,                     -- fecha de creacion en MP
    date_last_updated   TIMESTAMP,                     -- ultima modificacion por MP
    fecha_registro      TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- registro en DB
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_amount_nonneg    CHECK (amount             >= 0),
    CONSTRAINT chk_trans_amount_nonneg CHECK (transaction_amount IS NULL OR transaction_amount >= 0)
);

-- Auto-update updated_at en cada UPDATE
DROP TRIGGER IF EXISTS touch_transacciones_updated_at ON transacciones;
CREATE TRIGGER touch_transacciones_updated_at
    BEFORE UPDATE ON transacciones
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── Table: payment_links ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payment_links (
    id                 SERIAL PRIMARY KEY,
    reservation_id     INTEGER,
    external_reference VARCHAR(200) UNIQUE NOT NULL,
    amount             DECIMAL(10,2) NOT NULL,
    currency           VARCHAR(10) DEFAULT 'PEN',
    status             VARCHAR(20) DEFAULT 'pending',
    link_url           TEXT,
    preference_id      VARCHAR(100),
    date_created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_expires       TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS touch_payment_links_updated_at ON payment_links;
CREATE TRIGGER touch_payment_links_updated_at
    BEFORE UPDATE ON payment_links
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── Table: mp_notifications ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mp_notifications (
    id               SERIAL PRIMARY KEY,
    notification_id  VARCHAR(100) UNIQUE,
    payload          JSONB,
    received_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Indexes ─────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_transacciones_payment_id   ON transacciones(payment_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_external_ref ON transacciones(external_reference);
CREATE INDEX IF NOT EXISTS idx_payment_links_external_ref ON payment_links(external_reference);
CREATE INDEX IF NOT EXISTS idx_mp_notifications_received  ON mp_notifications(received_at);
