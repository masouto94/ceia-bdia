# Guía práctica: de CSV operacionales a un Data Warehouse

El objetivo es ejecutar y observar un pipeline local completo. Seguir los pasos en orden: primero cargar el snapshot válido, después el lote incremental, revisar la calidad y recién entonces publicar Gold. El ritmo de trabajo es `Ejecutar → observar salida → explicación docente → continuar`.

## Resultado esperado

| Capa | Evidencia final |
| --- | --- |
| Bronze | 16 CSV: 8 por lote, sin modificación |
| Silver | 93 filas aceptadas en 8 Parquet |
| Calidad | 16 rechazos con código, lote, archivo, fila y evidencia original |
| Gold | 8 usuarios, 10 datasets, 10 experimentos, 10 modelos, 11 participaciones y 32 hechos |

## 1. Preparar y levantar el entorno

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose ps
```

Los servicios `minio-storage`, `minio-admin`, `postgres-warehouse`, `duckdb-transformer` y `pgadmin-warehouse` deben figurar en ejecución; MinIO y PostgreSQL deben estar saludables. Las imágenes están fijadas y DuckDB se construye a partir del binario `1.4.3`. El paso 6 requiere además instalar ese mismo binario en tu máquina para inspeccionar gráficamente.

> Este despliegue es local y usa contenedores para reproducir servicios con semánticas similares a las disponibles en la nube. MinIO ofrece una API compatible con S3, pero ejecutar este stack no constituye un despliegue en una nube real.

## 2. Cargar el lote inicial en Bronze

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T minio-admin sh /scripts/cargar_bronze.sh lote_01_inicial
```

Debe informar `8 objetos`. Abrir <http://localhost:9001>, ingresar con las credenciales MinIO de `.env` y recorrer `lakehouse/bronze/lote=lote_01_inicial`.

Este lote es una copia autocontenida del snapshot de los datos de la Clase 4. Sus conteos son:

| Entidad | Filas |
| --- | ---: |
| usuarios | 7 |
| tipos_fuente | 6 |
| datasets | 9 |
| tipos_modelo | 4 |
| modelos | 9 |
| experimentos | 9 |
| experimentos_modelos | 10 |
| metricas | 30 |

Volver a ejecutar el comando. Debe indicar que Bronze ya contiene el lote y que no lo modifica.

> Cargar primero y transformar después es un flujo similar a **ELT**. `Bronze` conserva evidencia inmutable del origen: los datos se almacenan con su forma original y su esquema se interpreta al leerlos, es decir, se aplica ***schema-on-read***.

## 3. Incorporar el lote incremental

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T minio-admin sh /scripts/cargar_bronze.sh lote_02_nuevos
```

También debe cargar 8 objetos. Este lote no tiene CSV malformados: todas las filas son legibles, pero algunas representaciones necesitan normalización y otras violan reglas de negocio.

Casos normalizables:

- Espacios sobrantes y diferencias de mayúsculas/minúsculas.
- Booleanos `Sí` y `SI`.
- Fechas `DD/MM/YYYY` y timestamps `DD/MM/YYYY HH:MM:SS`.
- Coma decimal (`0,87`) y porcentaje (`87%`).

Casos rechazables:

- Claves duplicadas y campos obligatorios ausentes.
- Referencias a usuario, tipo, dataset, experimento o modelo desconocido.
- Fecha y booleano inválidos.
- Cantidad negativa, métrica fuera de rango y categoría de métrica desconocida.

## 4. Perfilar Bronze con DuckDB

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/01_perfilar_bronze.sql
```

> **Qué observar:** Los 16 conteos por entidad/lote y las muestras textuales del lote 2. El lector usa `all_varchar = true`: un valor problemático no aborta la ingesta por una inferencia de tipo prematura.

> El perfilado materializa el ***schema-on-read***: DuckDB examina primero la evidencia textual de Bronze y posterga las decisiones de tipo hasta contar con reglas explícitas.

## 5. Crear staging, normalizar y clasificar

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T minio-admin sh /scripts/limpiar_salidas.sh
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/02_procesar_silver.sql
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/05_verificar_calidad.sql
```

Las tablas `raw_*` conservan `lote_id`, `archivo_origen`, `numero_fila`, `ingerido_en` y `evidencia_original`. Las tablas `silver_*` contienen los tipos ya validados. Ningún rechazo se elimina en silencio.

> Normalizar de forma segura significa convertir representaciones equivalentes, como `Sí`, fechas conocidas o coma decimal, sin inventar valores ni corregir reglas de negocio. La procedencia por lote, archivo y fila aporta linaje; los códigos de error, conteos y rechazos conservados aportan evidencia de calidad y una base elemental de gobierno del dato.

Conteos esperados:

| Entidad | Recibidas | Aceptadas | Rechazadas |
| --- | ---: | ---: | ---: |
| usuarios | 10 | 8 | 2 |
| tipos_fuente | 7 | 7 | 0 |
| datasets | 13 | 10 | 3 |
| tipos_modelo | 5 | 5 | 0 |
| modelos | 12 | 10 | 2 |
| experimentos | 13 | 10 | 3 |
| experimentos_modelos | 13 | 11 | 2 |
| metricas | 36 | 32 | 4 |

Distribución esperada de los 16 rechazos:

| Código | Cantidad |
| --- | ---: |
| `DUPLICATE_KEY` | 2 |
| `UNKNOWN_USER` | 2 |
| `INVALID_DATE` | 2 |
| `MISSING_REQUIRED` | 1 |
| `NEGATIVE_QUANTITY` | 1 |
| `UNKNOWN_SOURCE_TYPE` | 1 |
| `UNKNOWN_MODEL_TYPE` | 1 |
| `UNKNOWN_DATASET` | 1 |
| `INVALID_BOOLEAN` | 1 |
| `UNKNOWN_MODEL` | 1 |
| `INVALID_RANGE` | 1 |
| `UNKNOWN_EXPERIMENT` | 1 |
| `UNKNOWN_METRIC_CATEGORY` | 1 |

El último resultado de `05_verificar_calidad.sql` debe ser `CONTROLES_OK`.

## 6. Inspeccionar DuckDB gráficamente

`clase_05.duckdb` vive en `./duckdb_data`, una carpeta del host montada como bind mount en `/workspace` dentro de `duckdb-transformer`. Esto permite abrir la UI oficial de DuckDB **directamente desde tu máquina**, sin pasar por la red de Docker.

Instalar el CLI de DuckDB una única vez (binario portable, sin dependencias, disponible para Windows, macOS y Linux): seguir <https://duckdb.org/install>.

```bash
curl https://install.duckdb.org | sh
```

**Dónde ejecutarlo:** terminal en tu máquina (no `docker compose exec`), desde `clase_05/practica`.

```bash
duckdb duckdb_data/clase_05.duckdb
```

Dentro del prompt de DuckDB:

```sql
LOAD ui;
CALL start_ui_server();
```

Debe abrirse el navegador en `http://localhost:4213` (o imprimir esa URL si no abre automáticamente). En la UI, elegir o crear un notebook local conectado a `clase_05` y comparar estas capas:

| Tablas | Qué permiten observar |
| --- | --- |
| `raw_*` | Staging textual, lote, archivo, fila y evidencia original |
| `evaluados_*` | Valores normalizados junto con `codigo_error` |
| `silver_*` | Sólo filas aceptadas y ya tipadas |
| `rechazos` | Las 16 filas excluidas con causa y trazabilidad |
| `resumen_calidad` | Balance recibido, aceptado y rechazado por entidad |

Crear una celda SQL, pegar juntas las cuatro consultas siguientes y ejecutar la celda. Este bloque no es un comando de terminal: no pasarlo a `ejecutar_sql.sh` mientras la UI mantiene abierta la base.

**Dónde ejecutarlo:** DuckDB UI → notebook local conectado a `clase_05`.

```sql
SELECT * FROM resumen_calidad ORDER BY entidad;

SELECT codigo_error, count(*) AS cantidad
FROM rechazos
GROUP BY codigo_error
ORDER BY codigo_error;

SELECT lote_id, nombre, valor, fecha_registro
FROM silver_metricas
ORDER BY lote_id, id;

SUMMARIZE silver_metricas;
```

Resultados esperados, en el mismo orden:

- El resumen de las 8 entidades, con 109 recibidas, 93 aceptadas y 16 rechazadas en total.
- La distribución de los 16 rechazos entre los 13 códigos de error indicados en el paso 5.
- Las 32 métricas Silver ordenadas por lote e identificador.
- El perfil estadístico y de tipos de las columnas de `silver_metricas`.

Las consultas se ejecutan localmente en el proceso nativo de DuckDB que abriste en tu terminal. Esa interfaz no tiene autenticación; por eso corre exclusivamente sobre `localhost` de tu máquina y no se publica ningún puerto de esta UI en Docker.

> La comparación visual entre `raw_*`, `evaluados_*`, `silver_*` y `rechazos` permite seguir el mismo registro desde su estado original hasta su aceptación o rechazo. La UI sirve sólo para inspección; no forma parte del pipeline ni debe permanecer activa durante escrituras.

Tu proceso `duckdb` local mantiene abierto `duckdb_data/clase_05.duckdb`. Para separar claramente inspección y escritura, cualquier paso manual del contenedor falla mientras ese archivo sigue abierto en tu terminal. Comprobarlo intentando continuar sin cerrarlo: debe devolver un error no nulo (DuckDB rechaza el lock del archivo) y no modificar datos.

> Cerrar la UI obligatoriamente antes de volver a los pasos de escritura: en la terminal donde corre `duckdb`, presionar `Ctrl+D` (o ejecutar `.exit`).

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

A diferencia de los pasos manuales, el pipeline automatizado (paso 12) no puede cerrar por vos esa UI: corre en tu máquina, fuera del contenedor. Si sigue abierta, `ejecutar_pipeline.sh` falla en el primer paso DuckDB con el mismo error de lock; cerrala manualmente y volvé a ejecutarlo.

## 7. Publicar Silver y calidad en MinIO

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/03_publicar_silver.sql
docker compose exec -T minio-admin sh -c 'mc alias set local http://minio-storage:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc ls --recursive local/lakehouse'
```

Además de los 16 objetos Bronze deben aparecer 8 Parquet Silver y 2 Parquet de calidad. Abrir uno desde la consola MinIO para reconocer que el formato ya no es el CSV operacional original.

> MinIO muestra el comportamiento de un Data Lake sobre almacenamiento de objetos: conserva objetos de distintas capas y formatos, y Parquet aporta almacenamiento columnar para consumo analítico. Parquet y la organización Medallion no bastan para formar un Lakehouse. El bucket `lakehouse` es sólo un identificador y no una afirmación arquitectónica.

## 8. Revisar el modelo Gold

Antes de cargar, observar las tablas creadas por `postgres/01_crear_warehouse.sql`:

- Dimensiones: `dim_fecha`, `dim_usuario`, `dim_dataset`, `dim_experimento`, `dim_metrica`, `dim_modelo`.
- Participación N:M: `bridge_experimento_modelo`.
- Hecho: `fact_metricas_experimentos`.
- Control: `control.control_cargas`.

El grano del hecho es **una métrica registrada para un experimento en una fecha/hora**. No existe `modelo_key` en el hecho porque una métrica de origen pertenece al experimento y un experimento puede involucrar varios modelos. Atribuirla a cada modelo duplicaría o inventaría significado.

> El DDL separa hechos medibles, dimensiones descriptivas y una tabla puente para la relación N:M. El modelo es dimensional, pero híbrido y parcialmente copo de nieve, no una estrella pura, porque algunas dimensiones se relacionan con otras dimensiones.

## 9. Cargar Gold desde DuckDB

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/04_cargar_gold.sql
docker compose exec -T postgres-warehouse sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /dev/stdin' < postgres/03_verificar_carga.sql
```

DuckDB elimina y repuebla Gold dentro de una transacción: dimensiones primero, después bridge y hecho. El control debe mostrar:

> Respecto del Warehouse PostgreSQL, este tramo es similar a ETL: DuckDB transforma y valida Silver antes de cargar y publicar las estructuras analíticas de Gold.

**Salida esperada:**

```text
lote_01_inicial  84  0   COMPLETADO
lote_02_nuevos    9  16  COMPLETADO
```

Los conteos principales deben ser 32 hechos y 11 participaciones.

## 10. Consultar con pgAdmin

Abrir <http://localhost:8085> e ingresar con `PGADMIN_DEFAULT_EMAIL` y `PGADMIN_DEFAULT_PASSWORD`.

Registrar el servidor:

| Campo | Valor |
| --- | --- |
| Name | `BDIA Clase 5` |
| Host name/address | `postgres-warehouse` |
| Port | `5432` |
| Maintenance database | `bdia_dw` |
| Username | `bdia_user` |
| Password | valor de `POSTGRES_PASSWORD` |

Dentro de la red Docker el host es `postgres-warehouse`; `localhost:5432` se usa solamente desde una herramienta externa. Abrir Query Tool, `File → Open File...`: el diálogo abre directamente en la carpeta `postgres/` (Compose la monta en el home del usuario de pgAdmin) con los tres scripts. Abrir `02_consultas_olap_y_calidad.sql` y ejecutarlo completo: las tres consultas de integridad finales deben devolver cero.

> Los CSV representan la extracción desde una fuente operacional orientada al registro de transacciones. Gold representa el consumo analítico: integra dimensiones y hechos para consultas OLAP sin operar sobre el origen.

## 11. Demostrar idempotencia y reproceso

Ejecutar nuevamente el recorrido automatizado:

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
sh scripts/ejecutar_pipeline.sh
```

Observaciones esperadas:

- Ambos lotes Bronze informan que ya existen y no se sobrescriben.
- Silver y calidad se regeneran con los mismos conteos.
- Gold vuelve a quedar con 32 hechos, 11 participaciones y dos controles de lote.
- No aparecen dimensiones ni hechos duplicados.

Esta recarga completa es también el mecanismo de reproceso didáctico: una corrección se incorporaría como un nuevo lote inmutable y luego se volverían a derivar Silver y Gold. No se edita el objeto Bronze original.

> La idempotencia permite reproducir las capas derivadas sin duplicar resultados. Silver y Gold pueden regenerarse; Bronze permanece inmutable como evidencia y cualquier corrección ingresa mediante un lote nuevo.

## 12. Atajo para repetir toda la práctica

Después de crear `.env`, este comando ejecuta los pasos técnicos y sus controles:

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
sh scripts/ejecutar_pipeline.sh
```

Usarlo como verificación o recuperación, no como reemplazo de observar cada capa durante el primer recorrido.

## 13. Detener o reiniciar

Conservar volúmenes:

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
docker compose down
```

Eliminar exclusivamente el estado de Clase 5 y volver al inicio:

**Dónde ejecutarlo:** terminal, desde `clase_05/practica`.

```bash
sh scripts/reiniciar_practica.sh
```

El segundo comando ejecuta `docker compose down -v --remove-orphans` bajo el proyecto fijo `bdia_clase_05`. No toca los stacks ni volúmenes de otras clases.

## 14. Problemas frecuentes

- Si un puerto está ocupado, cambiar únicamente su variable en `.env`; todos siguen ligados a `127.0.0.1`.
- Si PostgreSQL conserva credenciales anteriores, el volumen ya existía. Usar el reinicio completo sólo si se acepta borrar el estado de esta práctica.
- Si Bronze informa una carga parcial, reiniciar la práctica. El cargador se niega a completar silenciosamente un prefijo incompleto.
- Si falla la descarga de una extensión DuckDB en el primer uso, verificar la conectividad a Internet y repetir el comando; las extensiones quedan en el volumen de DuckDB.
- Si la UI local (`duckdb duckdb_data/clase_05.duckdb`) no abre el navegador, abrir manualmente `http://localhost:4213`. Requiere acceso a `https://ui.duckdb.org` para el frontend.
- Si un paso DuckDB del contenedor informa un lock/`Conflicting lock is held`, es porque la UI local sigue abierta en tu terminal: cerrala con `Ctrl+C` (o `.exit`) y reintentar.
- Si el CLI `duckdb` no está instalado en tu máquina, seguir <https://duckdb.org/install>; es el mismo requisito para cualquier sistema operativo.
- Si pgAdmin no encuentra `postgres-warehouse`, comprobar que el servidor se registró desde pgAdmin y no desde el host.

## 15. Cierre conceptual

> **Alcance:** Esta práctica usa un fixture pequeño, local y por lotes; por lo tanto, no implementa Big Data. Nube, IaaS, PaaS, SaaS, DBaaS y los despliegues *on-premise*, cloud e híbridos quedan en el plano conceptual. Tampoco incorpora tablas de archivos con ACID, evolución de esquema, catálogo, *time travel*, Delta Lake, Apache Iceberg o Apache Hudi; en consecuencia, no implementa un Lakehouse completo.

| Concepto | Evidencia observada | Alcance |
| --- | --- | --- |
| Arquitectura | Flujo CSV → MinIO → DuckDB → PostgreSQL | Pipeline local por lotes |
| ETL | Silver se transforma antes de cargar Gold | ETL relativo al Warehouse |
| ELT | Bronze se carga antes de perfilar y transformar | Flujo similar a ELT |
| Data Lake | Objetos CSV y Parquet organizados en MinIO | S3 compatible, local |
| Warehouse | Hechos, dimensiones y bridge en PostgreSQL | Gold analítico acotado |
| Medallion | Capas Bronze, Silver y Gold | Organización de datos, no producto completo |
| Gobierno | Linaje, controles, calidad y rechazos conservados | Gobierno básico, sin catálogo |
| Lakehouse | Parquet y capas Medallion | Incompleto: sin tablas ACID ni servicios asociados |
| Cloud | Semánticas S3 compatibles y servicios en contenedores | No es un despliegue cloud ni implementa modelos de servicio |
| Big Data | 16 CSV, 93 aceptadas y 16 rechazadas | Fixture pequeño; no Big Data |
| OLTP/OLAP | CSV de origen frente a consultas analíticas en Gold | Fuente operacional simulada y consumo OLAP |
| Estrella/copo de nieve | Hecho, dimensiones, bridge y relaciones entre dimensiones | Modelo híbrido, parcialmente copo de nieve |
