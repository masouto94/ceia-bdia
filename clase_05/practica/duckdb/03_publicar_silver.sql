-- Objetivo: publicar Silver tipado y controles de calidad como objetos analíticos.
-- Requiere / entradas: tablas Silver, rechazos y resumen creados en DuckDB persistente.
-- Produce / modifica: diez objetos bajo s3://lakehouse/{silver,calidad}.
-- Resultado esperado: diez Parquet comprimidos listos para consumo y auditoría.
-- Guía: publicación posterior al procesamiento; el pipeline la automatiza.
-- Seguridad: ejecutar limpiar_salidas.sh antes; elimina sólo derivados previos, no Bronze.

-- Parquet preserva tipos y habilita lectura columnar; ZSTD reduce tamaño con buena relación
-- entre compresión y costo. Quitar los derivados anteriores evita mezclar reprocesos.

COPY silver_usuarios TO 's3://lakehouse/silver/usuarios/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_tipos_fuente TO 's3://lakehouse/silver/tipos_fuente/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_datasets TO 's3://lakehouse/silver/datasets/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_tipos_modelo TO 's3://lakehouse/silver/tipos_modelo/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_modelos TO 's3://lakehouse/silver/modelos/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_experimentos TO 's3://lakehouse/silver/experimentos/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_experimentos_modelos TO 's3://lakehouse/silver/experimentos_modelos/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY silver_metricas TO 's3://lakehouse/silver/metricas/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY rechazos TO 's3://lakehouse/calidad/rechazos/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY resumen_calidad TO 's3://lakehouse/calidad/resumen/datos.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

SELECT 'objetos_publicados' AS control, 10 AS cantidad;
