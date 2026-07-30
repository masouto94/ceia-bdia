-- Objetivo: crear la estructura relacional del Warehouse visible desde pgAdmin.
-- Requiere / entradas: PostgreSQL inicializando un volumen de datos vacío.
-- Produce / modifica: schemas gold/control, tablas, restricciones e índices; no carga filas.
-- Resultado esperado: DDL disponible para recibir la recarga Gold desde DuckDB.
-- Guía: infraestructura automática; Docker ejecuta este init sólo al crear el volumen.
-- Observación: reiniciar contenedores no reejecuta el DDL; recrear el volumen sí lo hace.

CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS gold.dim_fecha (
    fecha_key INTEGER PRIMARY KEY,
    fecha DATE UNIQUE NOT NULL,
    anio SMALLINT NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    mes SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    dia SMALLINT NOT NULL CHECK (dia BETWEEN 1 AND 31),
    trimestre SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS gold.dim_usuario (
    usuario_key BIGINT PRIMARY KEY,
    usuario_id_origen BIGINT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    activo BOOLEAN NOT NULL,
    fecha_alta TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_dataset (
    dataset_key BIGINT PRIMARY KEY,
    dataset_id_origen BIGINT UNIQUE NOT NULL,
    usuario_key BIGINT NOT NULL REFERENCES gold.dim_usuario(usuario_key),
    nombre TEXT NOT NULL,
    tipo_fuente TEXT NOT NULL,
    fuente_detalle TEXT,
    cantidad_registros BIGINT NOT NULL CHECK (cantidad_registros >= 0),
    fecha_creacion TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_experimento (
    experimento_key BIGINT PRIMARY KEY,
    experimento_id_origen BIGINT UNIQUE NOT NULL,
    dataset_key BIGINT NOT NULL REFERENCES gold.dim_dataset(dataset_key),
    nombre TEXT NOT NULL,
    descripcion TEXT,
    fecha DATE NOT NULL,
    finalizado BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_metrica (
    metrica_key SMALLINT PRIMARY KEY,
    nombre TEXT UNIQUE NOT NULL CHECK (nombre IN ('accuracy', 'precision', 'recall', 'f1_score', 'mae', 'loss'))
);

CREATE TABLE IF NOT EXISTS gold.dim_modelo (
    modelo_key BIGINT PRIMARY KEY,
    modelo_id_origen BIGINT UNIQUE NOT NULL,
    usuario_key BIGINT NOT NULL REFERENCES gold.dim_usuario(usuario_key),
    nombre TEXT NOT NULL,
    tipo_modelo TEXT NOT NULL,
    version TEXT,
    fecha_creacion TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.bridge_experimento_modelo (
    experimento_key BIGINT NOT NULL REFERENCES gold.dim_experimento(experimento_key),
    modelo_key BIGINT NOT NULL REFERENCES gold.dim_modelo(modelo_key),
    parametros TEXT,
    resultado TEXT,
    parametros_jsonb JSONB,
    lote_id TEXT NOT NULL,
    PRIMARY KEY (experimento_key, modelo_key)
);

-- Grano: una métrica registrada para un experimento en una fecha/hora.
-- El puente modela participantes muchos-a-muchos, pero el origen no atribuye cada métrica
-- a un modelo; agregar modelo_key inventaría una relación y duplicaría mediciones.
CREATE TABLE IF NOT EXISTS gold.fact_metricas_experimentos (
    metrica_experimento_key BIGINT PRIMARY KEY,
    metrica_id_origen BIGINT UNIQUE NOT NULL,
    fecha_key INTEGER NOT NULL REFERENCES gold.dim_fecha(fecha_key),
    experimento_key BIGINT NOT NULL REFERENCES gold.dim_experimento(experimento_key),
    metrica_key SMALLINT NOT NULL REFERENCES gold.dim_metrica(metrica_key),
    valor NUMERIC(18,6) NOT NULL CHECK (valor >= 0),
    fecha_registro TIMESTAMP NOT NULL,
    lote_id TEXT NOT NULL,
    archivo_origen TEXT NOT NULL,
    UNIQUE (experimento_key, metrica_key, fecha_registro)
);

CREATE TABLE IF NOT EXISTS control.control_cargas (
    lote_id TEXT PRIMARY KEY,
    filas_aceptadas INTEGER NOT NULL CHECK (filas_aceptadas >= 0),
    filas_rechazadas INTEGER NOT NULL CHECK (filas_rechazadas >= 0),
    estado TEXT NOT NULL CHECK (estado IN ('COMPLETADO', 'FALLIDO')),
    cargado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_dataset_usuario ON gold.dim_dataset(usuario_key);
CREATE INDEX IF NOT EXISTS idx_dim_experimento_dataset ON gold.dim_experimento(dataset_key);
CREATE INDEX IF NOT EXISTS idx_dim_modelo_usuario ON gold.dim_modelo(usuario_key);
CREATE INDEX IF NOT EXISTS idx_bridge_modelo ON gold.bridge_experimento_modelo(modelo_key);
CREATE INDEX IF NOT EXISTS idx_fact_fecha ON gold.fact_metricas_experimentos(fecha_key);
CREATE INDEX IF NOT EXISTS idx_fact_experimento ON gold.fact_metricas_experimentos(experimento_key);
CREATE INDEX IF NOT EXISTS idx_fact_metrica ON gold.fact_metricas_experimentos(metrica_key);
