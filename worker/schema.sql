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
-- Curaduría (aditiva): versiones LinkedIn/X, contador de «Generar post» e historial de eventos.
ALTER TABLE IF EXISTS activos ADD COLUMN IF NOT EXISTS posts_redes jsonb;
ALTER TABLE IF EXISTS activos ADD COLUMN IF NOT EXISTS generaciones_ia integer NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS activos_historial (
    id bigserial PRIMARY KEY,
    id_activo text NOT NULL,
    evento text NOT NULL CHECK (evento IN ('generado', 'edicion', 'estado', 'posts_generados')),
    estado text NOT NULL,
    version integer NOT NULL,
    actor text,
    comentario text,
    fecha timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS activos_historial_activo ON activos_historial (id_activo, fecha, id);

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

-- === Importación histórica de Discord (aditiva; reversión en docs/discord-historico.md) ===
-- Separada de `mensajes` (que tiene lectura pública): los mensajes importados solo se exponen
-- por endpoints protegidos y no se consideran procesados por IA hasta una acción explícita.
CREATE TABLE IF NOT EXISTS discord_importaciones (
    id text PRIMARY KEY,
    guild_id text NOT NULL,
    canal_id text NOT NULL,
    canal_nombre text,
    canal_tipo integer,
    desde_utc timestamptz NOT NULL,
    hasta_utc timestamptz NOT NULL,          -- exclusivo, congelado al crear
    zona text NOT NULL,
    desde_local text NOT NULL,
    hasta_local text NOT NULL,
    max_mensajes integer NOT NULL CHECK (max_mensajes > 0),
    solicitante text NOT NULL,
    estado text NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'ejecutando', 'completada', 'completada_con_limite',
                          'cancelada', 'error')),
    cancelacion_solicitada boolean NOT NULL DEFAULT false,
    cursor_before text,
    paginas integer NOT NULL DEFAULT 0,
    examinados integer NOT NULL DEFAULT 0,
    en_rango integer NOT NULL DEFAULT 0,
    insertados integer NOT NULL DEFAULT 0,
    existentes integer NOT NULL DEFAULT 0,
    existentes_en_vivo integer NOT NULL DEFAULT 0,
    editados integer NOT NULL DEFAULT 0,
    descartados jsonb NOT NULL DEFAULT '{}'::jsonb,
    hilos_detectados integer NOT NULL DEFAULT 0,
    limite_alcanzado boolean NOT NULL DEFAULT false,
    motivos_parcial jsonb NOT NULL DEFAULT '[]'::jsonb,  -- max_mensajes, hilos_excluidos
    alcance text NOT NULL DEFAULT 'canal_sin_hilos',
    error jsonb,
    token_ejecucion text,
    vence timestamptz,
    intentos integer NOT NULL DEFAULT 0,
    clave_idempotencia text UNIQUE,
    creado timestamptz NOT NULL DEFAULT clock_timestamp(),
    iniciado timestamptz,
    finalizado timestamptz,
    ultimo_avance timestamptz
);
ALTER TABLE discord_importaciones ADD COLUMN IF NOT EXISTS motivos_parcial jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Idempotencia: parámetros SOLICITADOS y su huella (el rango efectivo congelado va en desde_utc/hasta_utc).
ALTER TABLE discord_importaciones ADD COLUMN IF NOT EXISTS solicitud jsonb;
ALTER TABLE discord_importaciones ADD COLUMN IF NOT EXISTS huella_solicitud text;
-- Una sola importación activa por canal (doble clic o pestañas concurrentes).
CREATE UNIQUE INDEX IF NOT EXISTS discord_importaciones_activa
    ON discord_importaciones (canal_id) WHERE estado IN ('pendiente', 'ejecutando');
CREATE TABLE IF NOT EXISTS discord_mensajes_historicos (
    id_mensaje text PRIMARY KEY,             -- identidad canónica: 'discord-<message_id>'
    message_id text NOT NULL UNIQUE,
    guild_id text NOT NULL,
    canal_id text NOT NULL,
    autor_id text NOT NULL,
    fecha timestamptz NOT NULL,
    editado_en timestamptz,
    capturado_en timestamptz NOT NULL DEFAULT clock_timestamp(),
    texto text NOT NULL,                     -- contenido de la PRIMERA captura (fuente estable)
    contenido_disponible boolean NOT NULL,   -- false: vacío sin adjuntos (p. ej. sin MESSAGE_CONTENT)
    tipo_discord integer NOT NULL,
    adjuntos jsonb NOT NULL DEFAULT '[]'::jsonb,   -- solo id, nombre, tipo y tamaño; sin URLs
    referencia text,                         -- message_reference.message_id (respuesta a)
    origen text NOT NULL DEFAULT 'importacion_historica',
    importacion_inicial text NOT NULL REFERENCES discord_importaciones(id),
    texto_ultima_version text,               -- si una importación posterior ve una edición
    edicion_detectada_en timestamptz,
    -- Instantánea AL CAPTURAR (la API calcula el estado vigente desde trabajos_worker):
    en_ingesta_vivo boolean NOT NULL DEFAULT false,          -- ya existía en `mensajes` (solo almacenado)
    estado_ia_captura text NOT NULL DEFAULT 'sin_evidencia'
        CHECK (estado_ia_captura IN ('sin_evidencia', 'pendiente', 'fallido', 'procesado')),
    estado_ia_trabajo text,                                  -- trabajo que respalda ese estado
    procesado_ia boolean NOT NULL DEFAULT false              -- true solo si estado_ia_captura='procesado'
);
-- Migración aditiva para bases creadas con la versión anterior de esta tabla.
ALTER TABLE discord_mensajes_historicos ADD COLUMN IF NOT EXISTS en_ingesta_vivo boolean NOT NULL DEFAULT false;
ALTER TABLE discord_mensajes_historicos ADD COLUMN IF NOT EXISTS estado_ia_captura text NOT NULL DEFAULT 'sin_evidencia'
    CHECK (estado_ia_captura IN ('sin_evidencia', 'pendiente', 'fallido', 'procesado'));
ALTER TABLE discord_mensajes_historicos ADD COLUMN IF NOT EXISTS estado_ia_trabajo text;
CREATE INDEX IF NOT EXISTS discord_mensajes_historicos_canal_fecha
    ON discord_mensajes_historicos (canal_id, fecha);
CREATE TABLE IF NOT EXISTS discord_importacion_mensajes (
    importacion_id text NOT NULL REFERENCES discord_importaciones(id),
    id_mensaje text NOT NULL REFERENCES discord_mensajes_historicos(id_mensaje),
    resultado text NOT NULL CHECK (resultado IN ('insertado', 'existente', 'existente_en_vivo', 'editado')),
    PRIMARY KEY (importacion_id, id_mensaje)
);

-- Cuentas de personas y sesiones revocables (backend/app/services/auth.py, docs/politica-acceso.md).
-- Compatible con la tabla que crea SQLAlchemy (create_all) y con bases anteriores sin `rol`:
-- las cuentas existentes quedan como «usuario» (sin permisos de operador) hasta que un administrador las promueva.
CREATE TABLE IF NOT EXISTS usuarios (
    id serial PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    hashed_password varchar(255) NOT NULL,
    full_name varchar(255),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol varchar(20) NOT NULL DEFAULT 'usuario';
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_rol_valido') THEN
        ALTER TABLE usuarios ADD CONSTRAINT usuarios_rol_valido CHECK (rol IN ('usuario', 'operador', 'administrador'));
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS sesiones (
    id text PRIMARY KEY,                       -- claim jti del JWT
    usuario_id integer NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    creada timestamptz NOT NULL DEFAULT clock_timestamp(),
    expira timestamptz NOT NULL,
    revocada timestamptz
);
CREATE INDEX IF NOT EXISTS sesiones_usuario_vigentes ON sesiones (usuario_id) WHERE revocada IS NULL;
