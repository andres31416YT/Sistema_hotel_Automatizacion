-- =============================================================================
-- Schema for Hotel Transactional PostgreSQL DB
-- Buenas prácticas aplicadas:
--   - Catálogos normalizados (tipo_documento, tipo_habitacion,
--     estado_habitacion, estado_reserva) en vez de VARCHAR sin control.
--   - Foreign keys con ON DELETE RESTRICT / SET NULL / CASCADE según caso.
--   - Triggers automáticos de updated_at en todas las tablas mutables.
--   - CHECK constraints en reservas (check_in < check_out).
-- =============================================================================
-- =============================================================================
-- 1. CATÁLOGOS MAESTROS
-- =============================================================================

-- Tipos de documento de identidad
CREATE TABLE IF NOT EXISTS tipo_documento (
    id          SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(10) UNIQUE NOT NULL,
    nombre      VARCHAR(60)  NOT NULL,
    descripcion TEXT,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tipos de habitación
CREATE TABLE IF NOT EXISTS tipo_habitacion (
    id          SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,
    nombre      VARCHAR(50) NOT NULL,
    descripcion TEXT,
    capacidad   SMALLINT DEFAULT 1,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Estados de habitación
CREATE TABLE IF NOT EXISTS estado_habitacion (
    id          SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,
    nombre      VARCHAR(50) NOT NULL,
    descripcion TEXT,
    orden       SMALLINT NOT NULL,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Estados de reserva
CREATE TABLE IF NOT EXISTS estado_reserva (
    id          SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,
    nombre      VARCHAR(50)  NOT NULL,
    descripcion TEXT,
    orden       SMALLINT NOT NULL,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 2. TABLA DE CLIENTES
-- =============================================================================

CREATE TABLE IF NOT EXISTS clients (
    id                SERIAL PRIMARY KEY,
    whatsapp_number   VARCHAR(20) UNIQUE NOT NULL,
    name              VARCHAR(100),
    doc_identidad     VARCHAR(20),             -- Número de documento
    id_tipo_documento SMALLINT,                -- FK: tipo de documento (DNI | CE | PASSPORT | OTRO)
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_clients_tipo_documento
        FOREIGN KEY (id_tipo_documento)
        REFERENCES tipo_documento(id)
        ON DELETE SET NULL
);

-- =============================================================================
-- 3. TABLA DE HABITACIONES
-- =============================================================================

CREATE TABLE IF NOT EXISTS rooms (
    id              SERIAL PRIMARY KEY,
    room_number     VARCHAR(10) UNIQUE NOT NULL,
    id_tipo_hab     SMALLINT                        NOT NULL,
    id_estado_hab   SMALLINT                        NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rooms_tipo   FOREIGN KEY (id_tipo_hab)   REFERENCES tipo_habitacion(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_rooms_estado FOREIGN KEY (id_estado_hab) REFERENCES estado_habitacion(id) ON DELETE RESTRICT
);

-- =============================================================================
-- 4. TABLA DE RESERVAS
-- =============================================================================

CREATE TABLE IF NOT EXISTS reservations (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER                         NOT NULL,
    room_id         INTEGER                         NOT NULL,
    id_estado       SMALLINT                        NOT NULL DEFAULT 1,  -- PENDIENTE
    check_in_date   DATE                            NOT NULL,
    check_out_date  DATE                            NOT NULL,
    total_amount    DECIMAL(10,2),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_reservas_cliente FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE RESTRICT,
    CONSTRAINT fk_reservas_room    FOREIGN KEY (room_id)   REFERENCES rooms(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_reservas_estado  FOREIGN KEY (id_estado)  REFERENCES estado_reserva(id) ON DELETE RESTRICT,
    CONSTRAINT chk_fechas         CHECK (check_in_date < check_out_date)
);

-- =============================================================================
-- 5. TABLA DE CHECK-INS / CHECK-OUTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS checkins (
    id              SERIAL PRIMARY KEY,
    reservation_id  INTEGER               NOT NULL,
    actual_check_in  TIMESTAMP,
    actual_check_out TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_checkins_reserva
        FOREIGN KEY (reservation_id)
        REFERENCES reservations(id) ON DELETE CASCADE
);

-- =============================================================================
-- 6. FUNCIÓN + TRIGGERS: autoupdate de updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_clients_updated          ON clients;
DROP TRIGGER IF EXISTS trg_rooms_updated             ON rooms;
DROP TRIGGER IF EXISTS trg_reservations_updated      ON reservations;
DROP TRIGGER IF EXISTS trg_tipo_documento_updated    ON tipo_documento;
DROP TRIGGER IF EXISTS trg_tipo_habitacion_updated   ON tipo_habitacion;
DROP TRIGGER IF EXISTS trg_estado_reserva_updated    ON estado_reserva;
DROP TRIGGER IF EXISTS trg_estado_habitacion_updated ON estado_habitacion;

CREATE TRIGGER trg_clients_updated           BEFORE UPDATE ON clients            FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_rooms_updated              BEFORE UPDATE ON rooms               FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_reservations_updated       BEFORE UPDATE ON reservations        FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_tipo_documento_updated     BEFORE UPDATE ON tipo_documento      FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_tipo_habitacion_updated    BEFORE UPDATE ON tipo_habitacion     FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_estado_reserva_updated     BEFORE UPDATE ON estado_reserva      FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_estado_habitacion_updated  BEFORE UPDATE ON estado_habitacion   FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
