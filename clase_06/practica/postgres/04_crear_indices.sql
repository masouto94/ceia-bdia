-- Objetivo: crear los índices vectoriales HNSW e IVFFlat sobre fragmentos.embedding (Paso 4).
-- Requiere / entradas: fragmentos cargados (para IVFFlat conviene tener volumen real
--   cargado con scripts/cargar_volumen.py antes de fijar "lists", no un puñado de filas).
-- Produce / modifica: dos índices nuevos sobre fragmentos(embedding).
-- Resultado esperado: dos índices creados; el optimizador puede (no siempre debe) usarlos.
-- Guía: la clase de operador (vector_cosine_ops) tiene que coincidir con el operador <=>
--   usado en las consultas y en 02_consultas_similitud.sql. Crear un índice no garantiza
--   que el optimizador lo use en todas las consultas: verificar con 05_explain_con_indice.sql.

CREATE INDEX IF NOT EXISTS idx_fragmentos_embedding_hnsw
    ON fragmentos USING hnsw (embedding vector_cosine_ops);

-- "lists" depende del volumen real de filas: como referencia de partida, aproximar
-- lists ≈ sqrt(cantidad_de_filas) y ajustar según lo medido con EXPLAIN ANALYZE.
-- Con sólo los 30 documentos base (unos pocos cientos de fragmentos) usar un valor bajo;
-- con el volumen sintético de ~10.000 filas (scripts/cargar_volumen.py) usar lists = 100.
CREATE INDEX IF NOT EXISTS idx_fragmentos_embedding_ivfflat
    ON fragmentos USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Al recrear el índice después de cargar el volumen sintético:
-- DROP INDEX idx_fragmentos_embedding_ivfflat;
-- CREATE INDEX idx_fragmentos_embedding_ivfflat
--     ON fragmentos USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
