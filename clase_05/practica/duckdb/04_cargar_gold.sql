-- Objetivo: reconstruir Gold desde Silver y publicarlo sólo si pasa controles críticos.
-- Requiere / entradas: tablas Silver/rechazos y attachment PostgreSQL disponible como pg.
-- Produce / modifica: dimensiones, puente, hechos y control de cargas en PostgreSQL.
-- Resultado esperado: 32 hechos, 11 filas puente y 16 rechazos registrados.
-- Guía: carga Gold posterior a Silver; el pipeline la ejecuta y luego verifica PostgreSQL.
-- Seguridad: full reload destructivo limitado a pg.gold y pg.control, dentro de transacción.

.bail on

BEGIN TRANSACTION;

-- El volumen didáctico permite una recarga completa reproducible. Se borra primero desde
-- los hijos hacia los padres para respetar las claves foráneas.
DELETE FROM pg.gold.fact_metricas_experimentos;
DELETE FROM pg.gold.bridge_experimento_modelo;
DELETE FROM pg.gold.dim_modelo;
DELETE FROM pg.gold.dim_metrica;
DELETE FROM pg.gold.dim_experimento;
DELETE FROM pg.gold.dim_dataset;
DELETE FROM pg.gold.dim_usuario;
DELETE FROM pg.gold.dim_fecha;
DELETE FROM pg.control.control_cargas;

-- La inserción invierte el orden: primero dimensiones padre, luego puente y tabla de hechos.
-- fecha_key YYYYMMDD y las claves iguales al ID de origen son decisiones didácticas y
-- deterministas; un warehouse evolutivo normalmente administraría claves sustitutas.
INSERT INTO pg.gold.dim_fecha
SELECT DISTINCT
    year(fecha) * 10000 + month(fecha) * 100 + day(fecha) AS fecha_key,
    fecha,
    year(fecha) AS anio,
    month(fecha) AS mes,
    day(fecha) AS dia,
    quarter(fecha) AS trimestre
FROM (
    SELECT fecha FROM silver_experimentos
    UNION
    SELECT CAST(fecha_registro AS DATE) FROM silver_metricas
) fechas;

INSERT INTO pg.gold.dim_usuario
SELECT id, id, nombre, email, activo, fecha_alta
FROM silver_usuarios
ORDER BY id;

INSERT INTO pg.gold.dim_dataset
SELECT d.id, d.id, d.usuario_id, d.nombre, tf.nombre, d.fuente_detalle,
       d.cantidad_registros, d.fecha_creacion
FROM silver_datasets d
JOIN silver_tipos_fuente tf ON tf.id = d.tipo_fuente_id
ORDER BY d.id;

INSERT INTO pg.gold.dim_experimento
SELECT id, id, dataset_id, nombre, descripcion, fecha, finalizado
FROM silver_experimentos
ORDER BY id;

INSERT INTO pg.gold.dim_metrica
-- El mapeo explícito estabiliza las claves de un catálogo conocido entre recargas.
SELECT CASE nombre
           WHEN 'accuracy' THEN 1 WHEN 'precision' THEN 2 WHEN 'recall' THEN 3
           WHEN 'f1_score' THEN 4 WHEN 'mae' THEN 5 WHEN 'loss' THEN 6
       END AS metrica_key,
       nombre
FROM (SELECT DISTINCT nombre FROM silver_metricas) categorias
ORDER BY metrica_key;

INSERT INTO pg.gold.dim_modelo
SELECT m.id, m.id, m.usuario_id, m.nombre, tm.nombre, m.version, m.fecha_creacion
FROM silver_modelos m
JOIN silver_tipos_modelo tm ON tm.id = m.tipo_modelo_id
ORDER BY m.id;

INSERT INTO pg.gold.bridge_experimento_modelo
-- El puente conserva la relación muchos-a-muchos y sus atributos sin multiplicar hechos.
SELECT experimento_id, modelo_id, parametros, resultado,
       try_cast(parametros_jsonb AS JSON), lote_id
FROM silver_experimentos_modelos
ORDER BY experimento_id, modelo_id;

INSERT INTO pg.gold.fact_metricas_experimentos
-- Grano: una métrica registrada para un experimento en un instante. No incluye modelo
-- porque el origen no atribuye esa medición a cada participante del puente.
SELECT m.id,
       m.id,
       year(m.fecha_registro) * 10000 + month(m.fecha_registro) * 100 + day(m.fecha_registro),
       m.experimento_id,
       CASE m.nombre
           WHEN 'accuracy' THEN 1 WHEN 'precision' THEN 2 WHEN 'recall' THEN 3
           WHEN 'f1_score' THEN 4 WHEN 'mae' THEN 5 WHEN 'loss' THEN 6
       END,
       m.valor,
       m.fecha_registro,
       m.lote_id,
       m.archivo_origen
FROM silver_metricas m
ORDER BY m.id;

CREATE OR REPLACE TEMP TABLE control_por_lote AS
WITH aceptadas AS (
    SELECT lote_id FROM silver_usuarios UNION ALL SELECT lote_id FROM silver_tipos_fuente
    UNION ALL SELECT lote_id FROM silver_datasets UNION ALL SELECT lote_id FROM silver_tipos_modelo
    UNION ALL SELECT lote_id FROM silver_modelos UNION ALL SELECT lote_id FROM silver_experimentos
    UNION ALL SELECT lote_id FROM silver_experimentos_modelos UNION ALL SELECT lote_id FROM silver_metricas
), a AS (
    SELECT lote_id, COUNT(*) AS cantidad FROM aceptadas GROUP BY lote_id
), r AS (
    SELECT lote_id, COUNT(*) AS cantidad FROM rechazos GROUP BY lote_id
)
SELECT coalesce(a.lote_id, r.lote_id) AS lote_id,
       coalesce(a.cantidad, 0)::INTEGER AS aceptadas,
       coalesce(r.cantidad, 0)::INTEGER AS rechazadas
FROM a FULL OUTER JOIN r ON a.lote_id = r.lote_id;

INSERT INTO pg.control.control_cargas
SELECT lote_id, aceptadas, rechazadas, 'COMPLETADO', current_timestamp
FROM control_por_lote
ORDER BY lote_id;

WITH verificacion AS (
    -- Estos conteos pertenecen al fixture de la práctica, no son umbrales generales.
    SELECT (SELECT COUNT(*) FROM pg.gold.fact_metricas_experimentos) AS hechos,
           (SELECT COUNT(*) FROM pg.gold.bridge_experimento_modelo) AS puentes,
           (SELECT coalesce(SUM(filas_rechazadas), 0) FROM pg.control.control_cargas) AS rechazos
)
SELECT CASE
           WHEN hechos = 32 AND puentes = 11 AND rechazos = 16 THEN 'Verificación crítica aprobada'
           ELSE error(printf('Conteos inesperados: hechos=%d, puentes=%d, rechazos=%d', hechos, puentes, rechazos))
       END AS resultado
FROM verificacion;

-- Verificar antes de COMMIT impide publicar una recarga incompleta o inconsistente.
COMMIT;

SELECT 'Gold cargado' AS resultado,
       (SELECT COUNT(*) FROM pg.gold.fact_metricas_experimentos) AS hechos,
       (SELECT COUNT(*) FROM pg.gold.bridge_experimento_modelo) AS participaciones;
