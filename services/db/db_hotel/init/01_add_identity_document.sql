-- Migration: agregar columna identity_document a tabla clients
-- Ejecutar DESPUES de 00_schema.sql
-- Agrega el campo de documento de identidad (DNI, carnet extranjeria, pasaporte)
-- requerido para registrar o confirmar reservas.

ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS identity_document VARCHAR(20);

COMMENT ON COLUMN clients.identity_document IS
    'Documento de identidad del huesped: DNI, carnet de extranjeria, pasaporte, etc.';
