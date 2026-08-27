-- Objetivo: crear la estructura relacional base de la practica: tenants (equipos),
--   documentos y fragmentos, con aislamiento multi-tenant desde el diseno del esquema.
-- Requiere / entradas: base de datos vacia, extension pgvector disponible en la imagen.
-- Produce / modifica: extension vector; tablas tenants, documentos, fragmentos.
-- Resultado esperado: tres tablas vacias, todas con tenant_id salvo tenants, listas
--   para cargar datos en el paso siguiente.
-- Guia: el aislamiento multi-tenant empieza en el esquema, no en la aplicacion. La
--   columna tenant_id se agrega tanto en documentos como, de forma denormalizada,
--   en fragmentos: asi las politicas de RLS y la busqueda vectorial sobre fragmentos
--   no necesitan un JOIN contra documentos para saber a que equipo pertenece cada fila.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenants (
    id     BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documentos (
    id        BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    titulo    TEXT NOT NULL,
    categoria TEXT,
    activo    BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fragmentos (
    id               BIGSERIAL PRIMARY KEY,
    tenant_id        BIGINT NOT NULL REFERENCES tenants(id),
    documento_id     BIGINT NOT NULL REFERENCES documentos(id),
    numero_fragmento INTEGER,
    contenido        TEXT NOT NULL,
    pagina           INTEGER,
    embedding        VECTOR(384),
    modelo_embedding TEXT,
    fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documentos_tenant_id ON documentos(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fragmentos_documento_id ON fragmentos(documento_id);
CREATE INDEX IF NOT EXISTS idx_fragmentos_tenant_id ON fragmentos(tenant_id);
