-- Objetivo: inspeccionar el balance Silver y fallar si el fixture quedó inconsistente.
-- Requiere / entradas: resumen_calidad, rechazos y tablas Silver en DuckDB persistente.
-- Produce / modifica: sólo resultados de consulta; no modifica datos.
-- Resultado esperado: detalle de rechazos y estado final CONTROLES_OK.
-- Guía: verificación manual posterior al procesamiento o diagnóstico de una recuperación.

SELECT * FROM resumen_calidad ORDER BY entidad;

SELECT codigo_error, COUNT(*) AS cantidad
FROM rechazos
GROUP BY codigo_error
ORDER BY codigo_error;

SELECT entidad, codigo_error, lote_id, numero_fila, evidencia_original
FROM rechazos
ORDER BY entidad, numero_fila;

SELECT CASE
    -- 16, 32 y 11 describen exclusivamente los dos lotes controlados de esta práctica.
    WHEN (SELECT COUNT(*) FROM rechazos) = 16
     AND (SELECT COUNT(*) FROM silver_metricas) = 32
     AND (SELECT COUNT(*) FROM silver_experimentos_modelos) = 11
    THEN 'CONTROLES_OK'
    ELSE error('Los conteos de calidad no coinciden con el caso esperado')
END AS resultado;
