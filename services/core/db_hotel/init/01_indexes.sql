-- =============================================================================
-- 7. ÍNDICES  (generados automáticamente al hacer 00_schema.sql)
-- =============================================================================

-- Clients
CREATE INDEX IF NOT EXISTS idx_clients_whatsapp      ON clients(whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_clients_doc_identidad  ON clients(doc_identidad);
CREATE INDEX IF NOT EXISTS idx_clients_tipo_documento ON clients(id_tipo_documento);

-- Rooms
CREATE INDEX IF NOT EXISTS idx_rooms_tipo_hab   ON rooms(id_tipo_hab);
CREATE INDEX IF NOT EXISTS idx_rooms_estado_hab ON rooms(id_estado_hab);

-- Reservations
CREATE INDEX IF NOT EXISTS idx_reservations_client  ON reservations(client_id);
CREATE INDEX IF NOT EXISTS idx_reservations_room    ON reservations(room_id);
CREATE INDEX IF NOT EXISTS idx_reservations_estado  ON reservations(id_estado);
CREATE INDEX IF NOT EXISTS idx_reservations_dates    ON reservations(check_in_date, check_out_date);
CREATE INDEX IF NOT EXISTS idx_reservations_por_fecha ON reservations(check_in_date);

-- Checkins
CREATE INDEX IF NOT EXISTS idx_checkins_reservation ON checkins(reservation_id);
