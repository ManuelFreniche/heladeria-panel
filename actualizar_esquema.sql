-- Ejecuta esto UNA VEZ en Supabase (SQL Editor) para añadir la posibilidad
-- de adjuntar fotos/archivos a tus tablas YA EXISTENTES, sin borrar nada.

ALTER TABLE inventario ADD COLUMN IF NOT EXISTS adjunto BYTEA;
ALTER TABLE inventario ADD COLUMN IF NOT EXISTS adjunto_nombre TEXT;
ALTER TABLE inventario ADD COLUMN IF NOT EXISTS adjunto_tipo TEXT;

ALTER TABLE gastos ADD COLUMN IF NOT EXISTS adjunto BYTEA;
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS adjunto_nombre TEXT;
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS adjunto_tipo TEXT;

ALTER TABLE precios ADD COLUMN IF NOT EXISTS adjunto BYTEA;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS adjunto_nombre TEXT;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS adjunto_tipo TEXT;

ALTER TABLE facturas ADD COLUMN IF NOT EXISTS adjunto BYTEA;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS adjunto_nombre TEXT;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS adjunto_tipo TEXT;

ALTER TABLE ventas ADD COLUMN IF NOT EXISTS adjunto BYTEA;
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS adjunto_nombre TEXT;
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS adjunto_tipo TEXT;
