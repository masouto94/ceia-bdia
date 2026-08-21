-- Objetivo: medir el plan de la misma consulta vectorial ya con índices creados.
-- Requiere / entradas: haber corrido 04_crear_indices.sql antes que este archivo.
-- Produce / modifica: no modifica datos; sólo lectura.
-- Resultado esperado: comparar filas procesadas, costo y tiempo real contra
--   03_explain_sin_indice.sql; con pocas filas el optimizador puede seguir eligiendo
--   Seq Scan, porque el índice no siempre resulta más barato en tablas chicas.
-- Guía: EXPLAIN ANALYZE permite ver qué índice usó el optimizador (o si no usó ninguno).

EXPLAIN ANALYZE
SELECT id, contenido
FROM fragmentos
ORDER BY embedding <=> (SELECT embedding FROM fragmentos WHERE id = 1)
LIMIT 5;

-- Para forzar la comparación entre HNSW e IVFFlat en la misma sesión, deshabilitar
-- uno a la vez (sólo dentro de esta sesión, no cambia la configuración global):
-- SET LOCAL enable_indexscan = off;   -- fuerza a no usar IVFFlat en este plan
-- SET LOCAL hnsw.ef_search = 40;      -- ajusta cuánto explora HNSW al consultar
