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
