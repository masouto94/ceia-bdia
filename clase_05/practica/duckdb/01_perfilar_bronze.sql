-- Objetivo: perfilar volúmenes y anomalías visibles de los CSV de Bronze.
-- Requiere / entradas: ambos lotes en s3://lakehouse/bronze y acceso S3 configurado.
-- Produce / modifica: vistas temporales y resultados de consulta; no modifica Bronze.
-- Resultado esperado: conteos por entidad/lote y muestras del segundo lote para inspección.
-- Guía: primer diagnóstico manual, antes de transformar; el pipeline lo ejecuta como control.

CREATE OR REPLACE TEMP VIEW perfil_archivos AS
-- all_varchar conserva cada campo como texto: una representación defectuosa se puede
-- observar y clasificar después, en lugar de abortar prematuramente toda la ingesta.
SELECT 'usuarios' AS entidad, filename AS archivo, COUNT(*) AS filas
FROM read_csv('s3://lakehouse/bronze/lote=*/usuarios.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'tipos_fuente', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/tipos_fuente.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'datasets', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/datasets.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'tipos_modelo', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/tipos_modelo.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'modelos', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/modelos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'experimentos', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/experimentos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'experimentos_modelos', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/experimentos_modelos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename
UNION ALL
SELECT 'metricas', filename, COUNT(*)
FROM read_csv('s3://lakehouse/bronze/lote=*/metricas.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
GROUP BY filename;

SELECT entidad, regexp_extract(archivo, 'lote=([^/]+)', 1) AS lote_id, filas
FROM perfil_archivos
ORDER BY entidad, lote_id;

-- Los corchetes hacen visibles espacios y nulos sin corregir ni completar el dato.
SELECT
    filename AS archivo,
    id,
    '[' || nombre || ']' AS nombre_visible,
    '[' || coalesce(email, 'NULL') || ']' AS email_visible,
    activo,
    fecha_alta
FROM read_csv('s3://lakehouse/bronze/lote=*/usuarios.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
WHERE filename LIKE '%lote_02_nuevos%';

SELECT
    filename AS archivo,
    id,
    nombre,
    valor,
    fecha_registro
FROM read_csv('s3://lakehouse/bronze/lote=*/metricas.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true)
WHERE filename LIKE '%lote_02_nuevos%';
