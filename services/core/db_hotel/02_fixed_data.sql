-- =============================================================================
-- 8. DATOS FIJOS  (catálogos) — sin esto el sistema no funciona correctamente
-- =============================================================================

-- Tipos de documento
INSERT INTO tipo_documento (codigo, nombre, descripcion)
    VALUES
        ('DNI',       'DNI / Registro Nacional de Identificación', 'Documento Nacional de Identificación'),
        ('CE',        'Carnet de Extranjería',                   'Documento de identidad para extranjeros en Perú'),
        ('PASSPORT',  'Pasaporte',                                'Pasaporte válido internacionalmente'),
        ('DNI_EXT',   'OTRO',                                     'Otro documento de identidad válido')
    ON CONFLICT (codigo) DO NOTHING;

-- Tipos de habitación
INSERT INTO tipo_habitacion (codigo, nombre, descripcion, capacidad)
    VALUES
        ('SIMPLE',   'Simple',    'Habitación para 1 persona',             1),
        ('DOBLE',    'Doble',     'Habitación para 2 personas',           2),
        ('TWIN',     'Twin',      'Habitación con 2 camas individuales',   2),
        ('SUITE',    'Suite',     'Suite con servicios adicionales',        4),
        ('FAMILIAR', 'Familiar',  'Habitación para hasta 4 personas',       4)
    ON CONFLICT (codigo) DO NOTHING;

-- Estados de habitación
INSERT INTO estado_habitacion (codigo, nombre, descripcion, orden)
    VALUES
        ('DISPONIBLE',    'Disponible',    'Libre y lista para reservar',            5),
        ('OCUPADA',       'Ocupada',       'Ocupada por un huésped actual',          3),
        ('MANTENIMIENTO', 'Mantenimiento', 'En mantenimiento, no disponible',        1),
        ('LIMPIEZA',      'Limpieza',      'Siendo limpiada, pendiente de liberar',  4)
    ON CONFLICT (codigo) DO NOTHING;

-- Estados de reserva
INSERT INTO estado_reserva (codigo, nombre, descripcion, orden)
    VALUES
        ('PENDIENTE',  'Pendiente',  'Reserva registrada, pendiente de confirmar pago',  1),
        ('CONFIRMADA', 'Confirmada', 'Pago aprobado, reserva confirmada',                 2),
        ('CHECK_IN',   'Check-in',   'Huésped ya ingresó al hotel',                       3),
        ('CHECK_OUT',  'Check-out',  'Huésped egresó, habitación liberada',               4),
        ('CANCELADA',  'Cancelada',  'Reserva anulada por cliente o staff',               0),
        ('NO_SHOW',    'No Show',    'Huésped no se presentó en la fecha acordada',       0)
    ON CONFLICT (codigo) DO NOTHING;
