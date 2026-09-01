-- Ejecuta esto UNA VEZ en Supabase (SQL Editor) para:
--   1) limpiar los duplicados que ya tienes en Gastos y Facturas
--   2) evitar que en el futuro se pueda volver a guardar el mismo
--      gasto/factura (mismo proveedor/cliente + importe + fecha)
--
-- Nota: si dos copias duplicadas tenían una foto adjunta distinta, se
-- conserva la más antigua (id más bajo) y se descarta el resto. Revisa
-- después en "Ver archivos adjuntos" si te falta alguna.

-- 1) Borrar duplicados de GASTOS, dejando solo el más antiguo de cada grupo
DELETE FROM gastos a USING gastos b
WHERE a.id > b.id
  AND a.proveedor = b.proveedor
  AND a.importe = b.importe
  AND a.fecha = b.fecha;

-- 2) Borrar duplicados de FACTURAS, dejando solo el más antiguo de cada grupo
DELETE FROM facturas a USING facturas b
WHERE a.id > b.id
  AND a.tercero = b.tercero
  AND a.importe = b.importe
  AND a.fecha = b.fecha;

-- 3) Añadir la protección para que no se puedan volver a duplicar
ALTER TABLE gastos ADD CONSTRAINT gastos_unico UNIQUE (proveedor, importe, fecha);
ALTER TABLE facturas ADD CONSTRAINT facturas_unico UNIQUE (tercero, importe, fecha);
