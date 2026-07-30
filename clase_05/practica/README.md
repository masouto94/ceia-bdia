# BDIA - Práctica Clase 5

Práctica de infraestructura de datos sobre el caso de experimentos de IA de las clases 2 a 4. El recorrido lleva dos lotes CSV por Bronze, Silver y Gold sin ocultar las filas inválidas.

## Ruta rápida

Requisitos: Docker Engine o Docker Desktop con Docker Compose, puertos locales `5433`, `8085`, `9000` y `9001` disponibles, y el CLI de [DuckDB](https://duckdb.org/install) instalado (para el paso de inspección gráfica, puerto `4213` local).

Desde `clase_05/practica`:

```bash
cp .env.example .env
sh scripts/ejecutar_pipeline.sh
```

Resultado esperado:

```text
fact_metricas_experimentos  32
bridge_experimento_modelo   11
lote_01_inicial             84 aceptadas / 0 rechazadas
lote_02_nuevos               9 aceptadas / 16 rechazadas
```

El comando se puede repetir: Bronze no se sobrescribe, Silver se vuelve a generar y Gold se recarga dentro de una transacción sin duplicar filas.

## Servicios

| Servicio | Responsabilidad | Acceso local |
| --- | --- | --- |
| MinIO (`minio-storage`) | Bronze CSV inmutable, Silver Parquet y evidencia de calidad | API `localhost:9000`; consola <http://localhost:9001> |
| MinIO Client (`minio-admin`) | Administración de objetos y ejecución de cargas | Sólo dentro de la red Compose |
| DuckDB (`duckdb-transformer`) | Perfilado, staging text-first, reglas, Parquet y transferencia | Base en `./duckdb_data/clase_05.duckdb` (bind mount), `/workspace` dentro del contenedor |
| PostgreSQL (`postgres-warehouse`) | Warehouse dimensional Gold y control de cargas | `localhost:5433` |
| pgAdmin (`pgadmin-warehouse`) | Inspección visual y consultas OLAP | <http://localhost:8085> |

Todos los puertos publicados se vinculan solamente a `127.0.0.1`. Las credenciales de `.env.example` son didácticas y exclusivamente locales.

## Flujo y archivos

```text
data/lote_01_inicial/       snapshot canónico de Clase 4
data/lote_02_nuevos/        altas válidas y errores controlados
duckdb/01..05               perfilado, Silver, publicación, Gold y controles
duckdb_data/                bind mount con clase_05.duckdb (generado, no versionado)
postgres/01..03             DDL, consultas OLAP y verificación
scripts/                    carga, ejecución y reinicio determinista
docs/guia-practica.md       recorrido paso a paso
```

El lote inicial reproduce los conteos `7, 6, 9, 4, 9, 9, 10, 30` de `usuarios`, `tipos_fuente`, `datasets`, `tipos_modelo`, `modelos`, `experimentos`, `experimentos_modelos` y `metricas`.

## Modelo Gold

El grano de `gold.fact_metricas_experimentos` es **una métrica registrada para un experimento en una fecha/hora**. Las métricas de origen no identifican un modelo concreto; por eso la participación N:M se conserva en `gold.bridge_experimento_modelo` y el hecho no contiene `modelo_key`.

## Inspección

Después de ejecutar `02_procesar_silver.sql` y `05_verificar_calidad.sql`, abrí la UI oficial de DuckDB **desde tu máquina**, no desde el contenedor: la UI sólo escucha en loopback y exponerla vía proxy dispara un bug conocido de `duckdb-ui` (`Failed to resolve app state`), sin importar el sistema operativo. Requiere el CLI de [DuckDB](https://duckdb.org/install) instalado localmente.

```bash
duckdb duckdb_data/clase_05.duckdb
```

Dentro del prompt:

```sql
LOAD ui;
CALL start_ui_server();
```

Abrí <http://localhost:4213> y recorré las tablas `raw_*`, `evaluados_*`, `silver_*`, `rechazos` y `resumen_calidad`. Por ejemplo:

```sql
SELECT * FROM resumen_calidad ORDER BY entidad;
SELECT codigo_error, count(*) AS cantidad FROM rechazos GROUP BY codigo_error ORDER BY codigo_error;
SUMMARIZE silver_metricas;
```

La UI demuestra que el staging textual, la evaluación, los datos aceptados y la evidencia rechazada conviven en la misma instancia local. Tu proceso `duckdb` mantiene abierta la base: hay que cerrarlo (`Ctrl+C` o `.exit` en esa terminal) antes de publicar Silver o ejecutar cualquier otro SQL desde el contenedor, que de lo contrario falla por el lock del archivo.

MinIO usa el bucket `lakehouse`:

```text
bronze/lote=lote_01_inicial/*.csv
bronze/lote=lote_02_nuevos/*.csv
silver/<entidad>/datos.parquet
calidad/rechazos/datos.parquet
calidad/resumen/datos.parquet
```

En pgAdmin registrá un servidor con host `postgres-warehouse`, puerto `5432`, base `bdia_dw`, usuario `bdia_user` y la contraseña definida en `.env`. Compose monta `./postgres` en el home del usuario de pgAdmin: en Query Tool, `File → Open File...` abre ahí directamente y `02_consultas_olap_y_calidad.sql` está a la vista.

## Detener o reiniciar

Conservar datos:

```bash
docker compose down
```

Reinicio completo y exclusivo de esta práctica:

```bash
sh scripts/reiniciar_practica.sh
```

Ese script elimina solamente los recursos del proyecto Compose `bdia_clase_05`; no afecta stacks de otras clases.

La guía operacional completa está en [`docs/guia-practica.md`](docs/guia-practica.md).
