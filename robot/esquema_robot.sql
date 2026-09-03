-- Ejecuta esto UNA VEZ en Supabase (SQL Editor) para crear el buzón de
-- entrada del robot. El robot SOLO escribe aquí — nunca toca la tabla
-- "gastos" directamente. Tú apruebas o descartas cada detección desde la app.

CREATE TABLE IF NOT EXISTS gastos_pendientes (
    id SERIAL PRIMARY KEY,
    proveedor TEXT,
    concepto TEXT,
    categoria TEXT NOT NULL DEFAULT 'Otros',
    importe REAL,
    fecha DATE,
    origen_asunto TEXT,
    origen_remitente TEXT,
    archivo_nombre TEXT,
    adjunto BYTEA,
    adjunto_tipo TEXT,
    detectado_en TIMESTAMP NOT NULL DEFAULT now(),
    estado TEXT NOT NULL DEFAULT 'Pendiente'
);
