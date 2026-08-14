-- Objetivo: verificar que la carga de documentos y fragmentos sea consistente.
-- Requiere / entradas: haber corrido scripts/cargar_documentos.py.
-- Produce / modifica: no modifica datos; sólo lectura.
-- Resultado esperado: 30 documentos, 1 inactivo (DOC-012), fragmentos con embedding
--   en todas las filas y ninguna dimensión distinta de 384.

SELECT count(*) AS total_documentos FROM documentos;

SELECT count(*) AS documentos_inactivos FROM documentos WHERE activo = FALSE;

SELECT categoria, count(*) AS cantidad
FROM documentos
GROUP BY categoria
ORDER BY categoria;

SELECT count(*) AS total_fragmentos FROM fragmentos;

SELECT count(*) AS fragmentos_sin_embedding
FROM fragmentos
WHERE embedding IS NULL;

SELECT DISTINCT vector_dims(embedding) AS dimension
FROM fragmentos
WHERE embedding IS NOT NULL;

SELECT DISTINCT modelo_embedding FROM fragmentos;
