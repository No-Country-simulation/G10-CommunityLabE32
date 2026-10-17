-- Propuesta local de contrato con Fredy. Tabla nueva; no altera tablas existentes.
CREATE TABLE IF NOT EXISTS trabajos_worker (
    id text PRIMARY KEY,
    entrada jsonb NOT NULL,
    estado text NOT NULL DEFAULT 'recibido'
        CHECK (estado IN ('recibido', 'procesando', 'terminado', 'error')),
    intentos integer NOT NULL DEFAULT 0,
    token text,
    vence timestamptz,
    resultado jsonb,
    error_codigo text,
    historial jsonb NOT NULL DEFAULT '["recibido"]'::jsonb,
    creado timestamptz NOT NULL DEFAULT clock_timestamp(),
    actualizado timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS trabajos_worker_pendientes ON trabajos_worker (estado, creado);
-- Migración aditiva: conserva trabajos y resultados anteriores.
ALTER TABLE trabajos_worker ADD COLUMN IF NOT EXISTS clave_idempotencia text;
CREATE UNIQUE INDEX IF NOT EXISTS trabajos_worker_idempotencia
    ON trabajos_worker (clave_idempotencia);
-- Advertencias de fidelidad editorial por activo (aditiva; NULL en activos anteriores).
ALTER TABLE IF EXISTS activos ADD COLUMN IF NOT EXISTS advertencias_fidelidad jsonb;

-- === Flujo híbrido, sentimiento y banners (aditiva; reversión en docs/flujo-hibrido-banners.md) ===
-- Sentimiento por mensaje: NULL = sin analizar. Procedencia y versión del análisis.
ALTER TABLE IF EXISTS mensajes ADD COLUMN IF NOT EXISTS sentimiento_origen text;
ALTER TABLE IF EXISTS mensajes ADD COLUMN IF NOT EXISTS sentimiento_version text;
ALTER TABLE IF EXISTS mensajes ADD COLUMN IF NOT EXISTS sentimiento_trabajo text;
ALTER TABLE IF EXISTS mensajes ADD COLUMN IF NOT EXISTS sentimiento_fecha timestamptz;

-- "Procesar pendientes": una sola solicitud abierta por origen (doble clic devuelve la misma).
CREATE TABLE IF NOT EXISTS solicitudes_procesamiento (
    id text PRIMARY KEY,
    origen text NOT NULL,
    estado text NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'tomada', 'en_curso', 'sin_pendientes', 'completada',
                          'completada_con_errores', 'cancelada')),
    vence timestamptz,
    lotes jsonb NOT NULL DEFAULT '[]'::jsonb,
    pendientes jsonb,
    historial jsonb NOT NULL DEFAULT '["pendiente"]'::jsonb,
    creado timestamptz NOT NULL DEFAULT clock_timestamp(),
    actualizado timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX IF NOT EXISTS solicitudes_procesamiento_abierta
    ON solicitudes_procesamiento (origen) WHERE estado IN ('pendiente', 'tomada', 'en_curso');
-- Último estado informado por el puente (una fila por origen).
CREATE TABLE IF NOT EXISTS estado_puente (
    origen text PRIMARY KEY,
    pendientes jsonb NOT NULL DEFAULT '{}'::jsonb,
    visto timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Banners: uno por versión aprobada del texto; generación y revisión separadas.
CREATE TABLE IF NOT EXISTS banners (
    id text PRIMARY KEY,
    id_activo text NOT NULL,
    version_texto integer NOT NULL,
    huella_texto text NOT NULL,
    estado text NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'generando', 'generado', 'error')),
    revision text NOT NULL DEFAULT 'pendiente'
        CHECK (revision IN ('pendiente', 'aprobado', 'rechazado')),
    proveedor text NOT NULL,
    plantilla text NOT NULL,
    svg text,
    error_codigo text,
    intentos integer NOT NULL DEFAULT 0,
    comentario text,
    creado timestamptz NOT NULL DEFAULT clock_timestamp(),
    actualizado timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (id_activo, version_texto)
);
CREATE INDEX IF NOT EXISTS banners_activo ON banners (id_activo);
