-- Ejecuta esto UNA VEZ en Supabase: panel del proyecto -> SQL Editor -> New query -> pega y "Run".

CREATE TABLE IF NOT EXISTS inventario (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    stock REAL NOT NULL DEFAULT 0,
    unidad TEXT NOT NULL DEFAULT 'ud',
    minimo REAL NOT NULL DEFAULT 0,
    coste REAL,
    adjunto BYTEA,
    adjunto_nombre TEXT,
    adjunto_tipo TEXT
);

CREATE TABLE IF NOT EXISTS gastos (
    id SERIAL PRIMARY KEY,
    proveedor TEXT NOT NULL,
    concepto TEXT,
    categoria TEXT NOT NULL DEFAULT 'Otros',
    importe REAL NOT NULL,
    fecha DATE NOT NULL,
    adjunto BYTEA,
    adjunto_nombre TEXT,
    adjunto_tipo TEXT
);

CREATE TABLE IF NOT EXISTS precios (
    id SERIAL PRIMARY KEY,
    producto TEXT NOT NULL UNIQUE,
    coste REAL,
    precio REAL NOT NULL,
    adjunto BYTEA,
    adjunto_nombre TEXT,
    adjunto_tipo TEXT
);

CREATE TABLE IF NOT EXISTS facturas (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL DEFAULT 'Recibida',
    tercero TEXT NOT NULL,
    numero TEXT,
    importe REAL NOT NULL,
    fecha DATE NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Pendiente',
    adjunto BYTEA,
    adjunto_nombre TEXT,
    adjunto_tipo TEXT
);

CREATE TABLE IF NOT EXISTS ventas (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL UNIQUE,
    importe REAL NOT NULL,
    adjunto BYTEA,
    adjunto_nombre TEXT,
    adjunto_tipo TEXT
);
