-- Objetivo: actualizar contenido y embedding de un fragmento como una única unidad lógica.
-- Requiere / entradas: fragmentos cargados; un nuevo embedding calculado externamente
--   con el mismo modelo (:nuevo_embedding) para el contenido corregido (:nuevo_contenido).
-- Produce / modifica: la fila de fragmentos indicada por :fragmento_id.
-- Resultado esperado: contenido, embedding, modelo_embedding y fecha_indexacion
--   quedan actualizados juntos; si algo falla, ROLLBACK evita que contenido y vector
--   queden desincronizados (uno reflejando la versión nueva y el otro la vieja).
-- Guía: cambiar sólo el texto sin recalcular el vector (o viceversa) es el error más
--   común de este paso: el ciclo de vida del embedding se protege con una transacción.

BEGIN;

UPDATE fragmentos
SET
    contenido = :'nuevo_contenido',
    embedding = :'nuevo_embedding',
    modelo_embedding = :'modelo_embedding',
    fecha_indexacion = CURRENT_TIMESTAMP
WHERE id = :fragmento_id;

COMMIT;

-- Ejemplo de uso desde psql, fijando las variables antes de \i este archivo:
-- \set fragmento_id 1
-- \set nuevo_contenido 'Texto corregido del fragmento...'
-- \set nuevo_embedding '[0.01, -0.02, 0.03, ...]'
-- \set modelo_embedding 'intfloat/multilingual-e5-small'

-- Reindexación: HNSW e IVFFlat se actualizan de forma incremental con cada UPDATE/INSERT,
-- pero si se reprocesan muchas filas de una vez (por ejemplo, un cambio de modelo) conviene
-- reconstruir el índice explícitamente en lugar de esperar el mantenimiento incremental:
-- REINDEX INDEX idx_fragmentos_embedding_hnsw;
-- REINDEX INDEX idx_fragmentos_embedding_ivfflat;
