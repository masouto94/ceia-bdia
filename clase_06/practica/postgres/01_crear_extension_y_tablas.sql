-- Objetivo: habilitar pgvector y crear la estructura relacional de la práctica (Paso 1).
-- Requiere / entradas: PostgreSQL sin la extensión vector ni las tablas de este esquema.
-- Produce / modifica: extensión vector, tablas documentos y fragmentos.
-- Resultado esperado: dos tablas vacías listas para recibir documentos y fragmentos.
-- Guía: primero se define la estructura relacional; los datos y los vectores llegan en el Paso 2.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documentos (
    id        BIGSERIAL PRIMARY KEY,
    titulo    TEXT NOT NULL,
    categoria TEXT,
    activo    BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fragmentos (
    id               BIGSERIAL PRIMARY KEY,
    documento_id     BIGINT NOT NULL REFERENCES documentos(id),
    numero_fragmento INTEGER,
    contenido        TEXT NOT NULL,
    pagina           INTEGER,
    embedding        VECTOR(384),
    modelo_embedding TEXT,
    fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fragmentos_documento_id ON fragmentos(documento_id);
