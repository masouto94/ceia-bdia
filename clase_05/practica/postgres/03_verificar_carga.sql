-- Objetivo: validar desde PostgreSQL la publicación final de Gold y mostrar sus conteos.
-- Requiere / entradas: Warehouse cargado con los dos lotes controlados de la práctica.
-- Produce / modifica: sólo resultados; aborta psql ante cualquier error o conteo inesperado.
-- Resultado esperado: 32 hechos, 11 filas puente; lotes con balances 84/0 y 9/16.
-- Guía: verificación automática final del pipeline y diagnóstico posterior a una recarga.

\set ON_ERROR_STOP on

DO $$
DECLARE
    hechos INTEGER;
    puentes INTEGER;
    rechazos INTEGER;
BEGIN
    -- Los valores esperados son específicos del fixture; detectan regresiones del ejercicio,
    -- no constituyen reglas universales de calidad para nuevos lotes.
    SELECT COUNT(*) INTO hechos FROM gold.fact_metricas_experimentos;
    SELECT COUNT(*) INTO puentes FROM gold.bridge_experimento_modelo;
    SELECT COALESCE(SUM(filas_rechazadas), 0) INTO rechazos FROM control.control_cargas;
    IF hechos <> 32 OR puentes <> 11 OR rechazos <> 16 THEN
        RAISE EXCEPTION 'Conteos inesperados: hechos=%, puentes=%, rechazos=%', hechos, puentes, rechazos;
    END IF;
END $$;

SELECT 'dim_fecha' AS objeto, COUNT(*) AS cantidad FROM gold.dim_fecha
UNION ALL SELECT 'dim_usuario', COUNT(*) FROM gold.dim_usuario
UNION ALL SELECT 'dim_dataset', COUNT(*) FROM gold.dim_dataset
UNION ALL SELECT 'dim_experimento', COUNT(*) FROM gold.dim_experimento
UNION ALL SELECT 'dim_metrica', COUNT(*) FROM gold.dim_metrica
UNION ALL SELECT 'dim_modelo', COUNT(*) FROM gold.dim_modelo
UNION ALL SELECT 'bridge_experimento_modelo', COUNT(*) FROM gold.bridge_experimento_modelo
UNION ALL SELECT 'fact_metricas_experimentos', COUNT(*) FROM gold.fact_metricas_experimentos
ORDER BY objeto;

SELECT lote_id, filas_aceptadas, filas_rechazadas, estado
FROM control.control_cargas
ORDER BY lote_id;
