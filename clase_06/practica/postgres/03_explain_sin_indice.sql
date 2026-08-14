-- Objetivo: medir el plan de una consulta vectorial antes de crear cualquier índice.
-- Requiere / entradas: fragmentos cargados; ningún índice HNSW/IVFFlat todavía (correr
--   este archivo antes que 04_crear_indices.sql, no después).
-- Produce / modifica: no modifica datos; sólo lectura.
-- Resultado esperado: un plan de tipo "Seq Scan" que recorre y ordena todas las filas.
-- Guía: sin índice, PostgreSQL calcula la distancia contra todos los vectores candidatos;
--   es el punto de comparación para 05_explain_con_indice.sql.

EXPLAIN ANALYZE
SELECT id, contenido
FROM fragmentos
ORDER BY embedding <=> (SELECT embedding FROM fragmentos WHERE id = 1)
LIMIT 5;
