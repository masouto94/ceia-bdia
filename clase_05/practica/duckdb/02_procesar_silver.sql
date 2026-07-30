-- Objetivo: convertir Bronze textual en tablas Silver tipadas y evidencia de rechazos.
-- Requiere / entradas: ambos lotes Bronze y acceso S3 configurado en DuckDB persistente.
-- Produce / modifica: tablas raw_*, evaluados_*, silver_*, rechazos y resumen_calidad.
-- Resultado esperado: datos aceptados trazables y una causa estable por fila rechazada.
-- Guía: transformación y calidad posterior al perfilado; el pipeline automatiza este paso.
-- Seguridad: reemplaza las tablas derivadas locales, pero nunca modifica Bronze.

-- Estas conversiones tolerantes devuelven NULL para poder clasificar el defecto por fila.
-- Sólo normalizan representaciones equivalentes: espacios, mayúsculas, acentos, formatos
-- de fecha/booleano, coma decimal y porcentaje; no imputan ni inventan valores de negocio.
CREATE OR REPLACE MACRO texto_limpio(valor) AS nullif(regexp_replace(trim(valor), '\\s+', ' ', 'g'), '');
CREATE OR REPLACE MACRO entero_seguro(valor) AS try_cast(trim(valor) AS BIGINT);
CREATE OR REPLACE MACRO fecha_hora_segura(valor) AS coalesce(
    try_cast(trim(valor) AS TIMESTAMP),
    try_strptime(trim(valor), '%d/%m/%Y %H:%M:%S'),
    try_strptime(trim(valor), '%Y/%m/%d %H:%M:%S')
);
CREATE OR REPLACE MACRO fecha_segura(valor) AS coalesce(
    try_cast(trim(valor) AS DATE),
    try_strptime(trim(valor), '%d/%m/%Y')::DATE,
    try_strptime(trim(valor), '%Y/%m/%d')::DATE
);
CREATE OR REPLACE MACRO booleano_seguro(valor) AS CASE
    WHEN strip_accents(lower(trim(valor))) IN ('true', 't', '1', 'si', 's') THEN true
    WHEN strip_accents(lower(trim(valor))) IN ('false', 'f', '0', 'no', 'n') THEN false
END;
CREATE OR REPLACE MACRO decimal_seguro(valor) AS CASE
    WHEN ends_with(trim(valor), '%') THEN try_cast(replace(replace(trim(valor), '%', ''), ',', '.') AS DECIMAL(18,6)) / 100
    ELSE try_cast(replace(trim(valor), ',', '.') AS DECIMAL(18,6))
END;

-- all_varchar implementa staging text-first: una celda inválida no derriba la ingesta
-- completa y la evidencia original queda disponible antes de intentar tiparla.
CREATE OR REPLACE TABLE raw_usuarios AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, nombre := nombre, email := email, activo := activo, fecha_alta := fecha_alta)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/usuarios.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_tipos_fuente AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, nombre := nombre)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/tipos_fuente.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_datasets AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, usuario_id := usuario_id, nombre := nombre, tipo_fuente_id := tipo_fuente_id,
           fuente_detalle := fuente_detalle, cantidad_registros := cantidad_registros, fecha_creacion := fecha_creacion)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/datasets.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_tipos_modelo AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, nombre := nombre)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/tipos_modelo.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_modelos AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, usuario_id := usuario_id, nombre := nombre, tipo_modelo_id := tipo_modelo_id,
           version := version, fecha_creacion := fecha_creacion)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/modelos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_experimentos AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, dataset_id := dataset_id, nombre := nombre, descripcion := descripcion,
           fecha := fecha, finalizado := finalizado)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/experimentos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_experimentos_modelos AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(experimento_id := experimento_id, modelo_id := modelo_id, parametros := parametros,
           resultado := resultado, parametros_jsonb := parametros_jsonb)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/experimentos_modelos.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

CREATE OR REPLACE TABLE raw_metricas AS
SELECT *, regexp_extract(filename, 'lote=([^/]+)', 1) AS lote_id,
       filename AS archivo_origen, row_number() OVER (PARTITION BY filename) + 1 AS numero_fila,
       current_timestamp AS ingerido_en,
       to_json(struct_pack(id := id, experimento_id := experimento_id, nombre := nombre, valor := valor,
           fecha_registro := fecha_registro)) AS evidencia_original
FROM read_csv('s3://lakehouse/bronze/lote=*/metricas.csv', all_varchar = true, filename = true, delim = ',', quote = '"', escape = '"', header = true);

-- La primera regla verdadera del CASE prevalece: requisitos, duplicados, formato/rango
-- y referencias se evalúan en ese orden para asignar un único código reproducible.
-- ORDER BY lote_id, numero_fila retiene determinísticamente la primera aparición de la clave.
-- Usuarios.
CREATE OR REPLACE TABLE evaluados_usuarios AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, texto_limpio(nombre) AS nombre, lower(texto_limpio(email)) AS email,
           booleano_seguro(activo) AS activo, fecha_hora_segura(fecha_alta) AS fecha_alta,
           lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_usuarios
)
SELECT *, CASE
    WHEN id IS NULL OR nombre IS NULL OR email IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN activo IS NULL THEN 'INVALID_BOOLEAN'
    WHEN fecha_alta IS NULL THEN 'INVALID_DATE'
END AS codigo_error
FROM normalizados;

CREATE OR REPLACE TABLE silver_usuarios AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_usuarios WHERE codigo_error IS NULL;

-- Catálogos raíz: se aceptan antes que las entidades que los referencian.
CREATE OR REPLACE TABLE evaluados_tipos_fuente AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, texto_limpio(nombre) AS nombre, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_tipos_fuente
)
SELECT *, CASE WHEN id IS NULL OR nombre IS NULL THEN 'MISSING_REQUIRED' WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY' END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_tipos_fuente AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_tipos_fuente WHERE codigo_error IS NULL;

CREATE OR REPLACE TABLE evaluados_tipos_modelo AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, texto_limpio(nombre) AS nombre, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_tipos_modelo
)
SELECT *, CASE WHEN id IS NULL OR nombre IS NULL THEN 'MISSING_REQUIRED' WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY' END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_tipos_modelo AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_tipos_modelo WHERE codigo_error IS NULL;

-- Orden padre-hijo: las referencias se validan sólo contra usuarios y tipos ya aceptados;
-- así un padre rechazado no permite publicar descendientes huérfanos.
CREATE OR REPLACE TABLE evaluados_datasets AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, entero_seguro(usuario_id) AS usuario_id, texto_limpio(nombre) AS nombre,
           entero_seguro(tipo_fuente_id) AS tipo_fuente_id, texto_limpio(fuente_detalle) AS fuente_detalle,
           entero_seguro(cantidad_registros) AS cantidad_registros, fecha_hora_segura(fecha_creacion) AS fecha_creacion,
           lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_datasets
)
SELECT *, CASE
    WHEN id IS NULL OR usuario_id IS NULL OR nombre IS NULL OR tipo_fuente_id IS NULL OR cantidad_registros IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN cantidad_registros < 0 THEN 'NEGATIVE_QUANTITY'
    WHEN fecha_creacion IS NULL THEN 'INVALID_DATE'
    WHEN NOT EXISTS (SELECT 1 FROM silver_usuarios u WHERE u.id = normalizados.usuario_id) THEN 'UNKNOWN_USER'
    WHEN NOT EXISTS (SELECT 1 FROM silver_tipos_fuente t WHERE t.id = normalizados.tipo_fuente_id) THEN 'UNKNOWN_SOURCE_TYPE'
END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_datasets AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_datasets WHERE codigo_error IS NULL;

-- Modelos dependen de los dos catálogos raíz ya validados.
CREATE OR REPLACE TABLE evaluados_modelos AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, entero_seguro(usuario_id) AS usuario_id, texto_limpio(nombre) AS nombre,
           entero_seguro(tipo_modelo_id) AS tipo_modelo_id, lower(texto_limpio(version)) AS version,
           fecha_hora_segura(fecha_creacion) AS fecha_creacion, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_modelos
)
SELECT *, CASE
    WHEN id IS NULL OR usuario_id IS NULL OR nombre IS NULL OR tipo_modelo_id IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN fecha_creacion IS NULL THEN 'INVALID_DATE'
    WHEN NOT EXISTS (SELECT 1 FROM silver_usuarios u WHERE u.id = normalizados.usuario_id) THEN 'UNKNOWN_USER'
    WHEN NOT EXISTS (SELECT 1 FROM silver_tipos_modelo t WHERE t.id = normalizados.tipo_modelo_id) THEN 'UNKNOWN_MODEL_TYPE'
END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_modelos AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_modelos WHERE codigo_error IS NULL;

-- Experimentos se validan después de datasets para respetar la misma cadena padre-hijo.
CREATE OR REPLACE TABLE evaluados_experimentos AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, entero_seguro(dataset_id) AS dataset_id, texto_limpio(nombre) AS nombre,
           texto_limpio(descripcion) AS descripcion, fecha_segura(fecha) AS fecha, booleano_seguro(finalizado) AS finalizado,
           lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_experimentos
)
SELECT *, CASE
    WHEN id IS NULL OR dataset_id IS NULL OR nombre IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN fecha IS NULL THEN 'INVALID_DATE'
    WHEN finalizado IS NULL THEN 'INVALID_BOOLEAN'
    WHEN NOT EXISTS (SELECT 1 FROM silver_datasets d WHERE d.id = normalizados.dataset_id) THEN 'UNKNOWN_DATASET'
END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_experimentos AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_experimentos WHERE codigo_error IS NULL;

-- La relación muchos-a-muchos registra participación; permanece separada porque el origen
-- no afirma que una métrica del experimento pertenezca a un modelo participante concreto.
CREATE OR REPLACE TABLE evaluados_experimentos_modelos AS
WITH normalizados AS (
    SELECT entero_seguro(experimento_id) AS experimento_id, entero_seguro(modelo_id) AS modelo_id,
           texto_limpio(parametros) AS parametros, texto_limpio(resultado) AS resultado, texto_limpio(parametros_jsonb) AS parametros_jsonb,
           lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(experimento_id), entero_seguro(modelo_id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_experimentos_modelos
)
SELECT *, CASE
    WHEN experimento_id IS NULL OR modelo_id IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN NOT EXISTS (SELECT 1 FROM silver_experimentos e WHERE e.id = normalizados.experimento_id) THEN 'UNKNOWN_EXPERIMENT'
    WHEN NOT EXISTS (SELECT 1 FROM silver_modelos m WHERE m.id = normalizados.modelo_id) THEN 'UNKNOWN_MODEL'
END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_experimentos_modelos AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_experimentos_modelos WHERE codigo_error IS NULL;

-- Porcentajes y coma decimal se interpretan como representaciones del valor recibido;
-- no se completa ninguna métrica ausente ni se corrige un valor fuera de rango.
CREATE OR REPLACE TABLE evaluados_metricas AS
WITH normalizados AS (
    SELECT entero_seguro(id) AS id, entero_seguro(experimento_id) AS experimento_id,
           strip_accents(lower(texto_limpio(nombre))) AS nombre, decimal_seguro(valor) AS valor,
           fecha_hora_segura(fecha_registro) AS fecha_registro, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original,
           row_number() OVER (PARTITION BY entero_seguro(id) ORDER BY lote_id, numero_fila) AS ocurrencia
    FROM raw_metricas
)
SELECT *, CASE
    WHEN id IS NULL OR experimento_id IS NULL OR nombre IS NULL OR valor IS NULL THEN 'MISSING_REQUIRED'
    WHEN ocurrencia > 1 THEN 'DUPLICATE_KEY'
    WHEN fecha_registro IS NULL THEN 'INVALID_DATE'
    WHEN nombre NOT IN ('accuracy', 'precision', 'recall', 'f1_score', 'mae', 'loss') THEN 'UNKNOWN_METRIC_CATEGORY'
    WHEN valor < 0 OR (nombre IN ('accuracy', 'precision', 'recall', 'f1_score') AND valor > 1) THEN 'INVALID_RANGE'
    WHEN NOT EXISTS (SELECT 1 FROM silver_experimentos e WHERE e.id = normalizados.experimento_id) THEN 'UNKNOWN_EXPERIMENT'
END AS codigo_error
FROM normalizados;
CREATE OR REPLACE TABLE silver_metricas AS SELECT * EXCLUDE (ocurrencia, codigo_error, evidencia_original) FROM evaluados_metricas WHERE codigo_error IS NULL;

-- La precedencia anterior garantiza exactamente un código estable por fila, aunque una
-- misma fila incumpla varias reglas; la evidencia permite auditar las demás causas.
CREATE OR REPLACE TABLE rechazos AS
SELECT 'usuarios' AS entidad, codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_usuarios WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'tipos_fuente', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_tipos_fuente WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'datasets', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_datasets WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'tipos_modelo', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_tipos_modelo WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'modelos', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_modelos WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'experimentos', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_experimentos WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'experimentos_modelos', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_experimentos_modelos WHERE codigo_error IS NOT NULL
UNION ALL SELECT 'metricas', codigo_error, lote_id, archivo_origen, numero_fila, ingerido_en, evidencia_original FROM evaluados_metricas WHERE codigo_error IS NOT NULL;

CREATE OR REPLACE TABLE resumen_calidad AS
WITH resultados AS (
    SELECT 'usuarios' AS entidad, COUNT(*) AS recibidas, count_if(codigo_error IS NULL) AS aceptadas, count_if(codigo_error IS NOT NULL) AS rechazadas FROM evaluados_usuarios
    UNION ALL SELECT 'tipos_fuente', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_tipos_fuente
    UNION ALL SELECT 'datasets', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_datasets
    UNION ALL SELECT 'tipos_modelo', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_tipos_modelo
    UNION ALL SELECT 'modelos', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_modelos
    UNION ALL SELECT 'experimentos', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_experimentos
    UNION ALL SELECT 'experimentos_modelos', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_experimentos_modelos
    UNION ALL SELECT 'metricas', COUNT(*), count_if(codigo_error IS NULL), count_if(codigo_error IS NOT NULL) FROM evaluados_metricas
)
SELECT *, current_timestamp AS procesado_en FROM resultados;

SELECT * FROM resumen_calidad ORDER BY entidad;
SELECT codigo_error, COUNT(*) AS cantidad FROM rechazos GROUP BY codigo_error ORDER BY codigo_error;
