-- Objetivo: explorar Gold con preguntas OLAP y controles de integridad legibles.
-- Requiere / entradas: carga Gold completa; ejecutar desde Query Tool de pgAdmin.
-- Produce / modifica: sólo resultados de consulta; no modifica el Warehouse.
-- Resultado esperado: agregados de negocio, balance por lote y controles finales en cero.
-- Guía: exploración manual posterior a la carga, no forma parte del pipeline automático.

-- 1. La tabla de hechos enlaza fecha y categoría para comparar evolución temporal.
SELECT f.fecha, m.nombre AS metrica, ROUND(AVG(h.valor), 4) AS promedio, COUNT(*) AS mediciones
FROM gold.fact_metricas_experimentos h
JOIN gold.dim_fecha f ON f.fecha_key = h.fecha_key
JOIN gold.dim_metrica m ON m.metrica_key = h.metrica_key
GROUP BY f.fecha, m.nombre
ORDER BY f.fecha, m.nombre;

-- 2. El camino hecho -> experimento -> dataset -> usuario responde quién es propietario
-- del dataset evaluado; no presupone que sea propietario de los modelos participantes.
SELECT u.nombre AS propietario, d.nombre AS dataset,
       ROUND(AVG(h.valor), 4) AS accuracy_promedio
FROM gold.fact_metricas_experimentos h
JOIN gold.dim_metrica m ON m.metrica_key = h.metrica_key AND m.nombre = 'accuracy'
JOIN gold.dim_experimento e ON e.experimento_key = h.experimento_key
JOIN gold.dim_dataset d ON d.dataset_key = e.dataset_key
JOIN gold.dim_usuario u ON u.usuario_key = d.usuario_key
GROUP BY u.nombre, d.nombre
ORDER BY accuracy_promedio DESC;

-- 3. El puente responde qué modelos participaron. Las métricas no se unen por ese camino:
-- hacerlo atribuiría cada medición a todos los participantes sin evidencia de origen.
SELECT e.nombre AS experimento, COUNT(*) AS modelos_participantes,
       string_agg(m.nombre, ', ' ORDER BY m.nombre) AS modelos
FROM gold.bridge_experimento_modelo b
JOIN gold.dim_experimento e ON e.experimento_key = b.experimento_key
JOIN gold.dim_modelo m ON m.modelo_key = b.modelo_key
GROUP BY e.nombre
ORDER BY modelos_participantes DESC, e.nombre;

-- 4. El control operacional permite reconciliar aceptadas y rechazadas por lote.
SELECT lote_id, filas_aceptadas, filas_rechazadas, estado, cargado_en
FROM control.control_cargas
ORDER BY lote_id;

-- 5. Los ceros confirman ausencia de huérfanos y duplicados al grano declarado.
SELECT 'hechos_sin_experimento' AS control, COUNT(*) AS cantidad
FROM gold.fact_metricas_experimentos h
LEFT JOIN gold.dim_experimento e ON e.experimento_key = h.experimento_key
WHERE e.experimento_key IS NULL
UNION ALL
SELECT 'puentes_sin_modelo', COUNT(*)
FROM gold.bridge_experimento_modelo b
LEFT JOIN gold.dim_modelo m ON m.modelo_key = b.modelo_key
WHERE m.modelo_key IS NULL
UNION ALL
SELECT 'duplicados_hecho', COUNT(*)
FROM (
    SELECT experimento_key, metrica_key, fecha_registro
    FROM gold.fact_metricas_experimentos
    GROUP BY experimento_key, metrica_key, fecha_registro
    HAVING COUNT(*) > 1
) duplicados;
