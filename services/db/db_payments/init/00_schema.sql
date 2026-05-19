-- Schema for Payments Transactional PostgreSQL DB
-- Tables: transacciones, payment_links, mp_notifications

-- Transactions table (records of processed payments)
-- Column mapping:
--   status_detail  -> Campo opcional de detalle del estado del pago.
CREATE TABLE IF NOT EXISTS transacciones (
    id                 SERIAL  PRIMARY KEY,
    payment_id         VARCHAR(100) UNIQUE NOT NULL,  -- Mercado Pago payment ID
    amount             DECIMAL(10,2)    NOT NULL,
    currency           VARCHAR(10)  DEFAULT 'USD',
    status             VARCHAR(20),                 -- approved, pending, rejected, etc.
    status_detail      VARCHAR(50),                 -- detalle del estado (opcional)
    status_code        VARCHAR(20),                 -- codigo de estado adicional
    external_reference VARCHAR(200),                -- e.g., reservation ID
    payer_id           VARCHAR(100),                -- ID del pagador en MP
    payer_email        VARCHAR(255),
    payer_name         VARCHAR(255),
    transaction_amount DECIMAL(10,2),               -- monto procesado en MP
    date_approved      TIMESTAMP,
    date_created       TIMESTAMP,
    date_last_updated  TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment links table (links generated for reservations)
CREATE TABLE IF NOT EXISTS payment_links (
    id SERIAL PRIMARY KEY,
    reservation_id INTEGER,  -- FK to hotel DB reservations (if we had cross-db joins, but we'll keep it as integer for simplicity)
    external_reference VARCHAR(200) UNIQUE NOT NULL,  -- The reference we gave to Mercado Pago
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(20) DEFAULT 'pending',  -- pending, paid, expired
    link_url TEXT,
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notifications table (to store raw webhook notifications for auditing)
CREATE TABLE IF NOT EXISTS mp_notifications (
    id SERIAL PRIMARY KEY,
    notification_id VARCHAR(100) UNIQUE,  -- Mercado Pago notification ID
    payload JSONB,  -- Store the entire webhook payload
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transacciones_payment_id ON transacciones(payment_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_external_ref ON transacciones(external_reference);
CREATE INDEX IF NOT EXISTS idx_payment_links_external_ref ON payment_links(external_reference);
CREATE INDEX IF NOT EXISTS idx_mp_notifications_received ON mp_notifications(received_at);