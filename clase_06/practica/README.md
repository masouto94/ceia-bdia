# BDIA - Práctica Clase 6

Práctica de bases de datos vectoriales sobre el caso de experimentos de IA de las clases 2 a 5. Modela documentos y fragmentos, genera embeddings con un modelo local, los almacena en PostgreSQL con `pgvector`, y consulta por similitud combinando filtros SQL, índices HNSW/IVFFlat y `EXPLAIN ANALYZE`.

**El esquema de tablas y los pasos de la práctica siguen el mockup de la Clase 6** (`material_desarrollo/clase6.pdf`, Sección 10 "Práctica guiada"), no un diseño propio. Cualquier extensión (por ejemplo una columna `metadata JSONB`, del slide 16) queda marcada como opcional, no como parte del ejercicio mínimo.

## Ruta rápida

Requisitos: Docker Engine o Docker Desktop con Docker Compose, y puertos locales `5434`, `8086` disponibles (configurables en `.env`).

Desde `clase_06/practica`:

```bash
cp .env.example .env
sh scripts/ejecutar_pipeline.sh
```

Resultado esperado:

```text
Documentos cargados: 30
Fragmentos cargados: ~50-60 (según el fragmentado de los 30 documentos, 6 oraciones por fragmento)
Modelo de embeddings: intfloat/multilingual-e5-small (dimensión 384)
```

más dos planes de `EXPLAIN ANALYZE` (sin índice / con HNSW e IVFFlat creados) para comparar.

## Servicios

| Servicio | Responsabilidad | Acceso local |
| --- | --- | --- |
| PostgreSQL + pgvector (`postgres-vectorial`) | Tablas `documentos`/`fragmentos`, extensión `vector`, índices | `localhost:${POSTGRES_PORT}` (default `5434`) |
| Loader de embeddings (`loader-embeddings`) | Contenedor Python con `sentence-transformers`/`psycopg2`; corre los scripts de carga y comparación | Sólo dentro de la red Compose (`docker compose exec`) |
| pgAdmin (`pgadmin-vectorial`) | Inspección visual y consultas | <http://localhost:8086> (default `PGADMIN_PORT`) |
| Embeddings API (`embeddings-api`) | Microservicio FastAPI que expone el mismo modelo local (`intfloat/multilingual-e5-small`) por HTTP, para que la interfaz web no dependa de Node corriendo `sentence-transformers` | `localhost:${EMBEDDINGS_API_PORT}` (default `8010`) |
| Interfaz web (`web-ui`) | Next.js + shadcn/ui: demo en clase de recuperación (pgvector) + generación (LLM vía OpenRouter) | <http://localhost:3000> (default `WEB_PORT`) |

Todos los puertos publicados se vinculan solamente a `127.0.0.1`. Las credenciales de `.env.example` son didácticas y exclusivamente locales. `embeddings-api` y `web-ui` son opcionales: si no se necesita la demo visual, alcanza con `docker compose up -d postgres-vectorial loader-embeddings pgadmin-vectorial`.

## Flujo y archivos

```text
data/
  equipos.csv               6 equipos/áreas (contexto narrativo, no columnas de la tabla)
  datasets.csv               8 datasets reutilizados de clases anteriores (idem)
  modelos.csv                 6 modelos de IA (idem)
  experimentos.csv            12 experimentos (idem)
  documentos.json             30 documentos ficticios (fuente de verdad)
  documentos.csv              los mismos 30 documentos en formato tabular
  consultas_prueba.json       25 consultas de prueba (fuente de verdad)
  consultas_prueba.csv        las mismas 25 consultas en formato tabular
  fragmentos_volumen.csv      generado por generar_volumen.py (no versionado, ver .gitignore)
  documento_id_map.json       generado por cargar_documentos.py (no versionado)
postgres/
  01_crear_extension_y_tablas.sql     Paso 1
  02_consultas_similitud.sql          Paso 3
  03_explain_sin_indice.sql           Paso 4a
  04_crear_indices.sql                Paso 4b (HNSW + IVFFlat)
  05_explain_con_indice.sql           Paso 4c
  06_actualizacion_reindexacion.sql   Extensión: UPDATE transaccional
  07_verificar_carga.sql              conteos de verificación
scripts/
  generar_volumen.py    genera ~10.000 fragmentos sintéticos a partir de documentos.json
  cargar_documentos.py  genera embeddings de los 30 documentos y los inserta en PostgreSQL
  cargar_volumen.py     genera embeddings del volumen sintético y los inserta en PostgreSQL
  comparar_busqueda.py  compara búsqueda literal (tsvector) vs. semántica (pgvector) con las 25 consultas
  responder_rag.py      extensión: recupera con pgvector y genera la respuesta con un LLM vía OpenRouter
  ejecutar_sql.sh       corre un archivo de postgres/ contra postgres-vectorial
  ejecutar_pipeline.sh  atajo: Pasos 1 a 4 de punta a punta
  reiniciar_practica.sh reinicio determinista, exclusivo de esta práctica
  embeddings_api.py     extensión: microservicio FastAPI de embeddings (usado por web/)
web/
  app/page.tsx                       UI de la demo (pregunta libre o de ejemplo)
  app/api/preguntar/route.ts         orquesta recuperación (pgvector) + generación (OpenRouter)
  app/api/preguntas-ejemplo/route.ts sirve consultas_prueba.json para el selector
  lib/db.ts, lib/embeddings.ts, lib/openrouter.ts   helpers de cada paso del pipeline
  Dockerfile             build multi-stage (output: standalone)
docs/
  guia-practica.md      recorrido paso a paso (equivalente al de Clase 5)
docker-compose.yml       postgres-vectorial + loader-embeddings + pgadmin-vectorial + embeddings-api + web-ui
Dockerfile.loader        imagen Python del loader (sentence-transformers, psycopg2); reutilizada por embeddings-api
requirements.txt         dependencias del loader y de embeddings_api.py
README.md                este archivo
```

`documentos.json`/`documentos.csv` y `consultas_prueba.json`/`consultas_prueba.csv` contienen la misma información en dos formatos: usar JSON para cargar con un script (preserva tipos y `null`), o CSV para inspección rápida.

La guía operacional completa está en [`docs/guia-practica.md`](docs/guia-practica.md).

## Esquema de tablas (tal como lo define el mockup)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documentos (
  id       BIGSERIAL PRIMARY KEY,
  titulo   TEXT NOT NULL,
  categoria TEXT,
  activo   BOOLEAN DEFAULT TRUE
);

CREATE TABLE fragmentos (
  id                BIGSERIAL PRIMARY KEY,
  documento_id      BIGINT NOT NULL REFERENCES documentos(id),
  numero_fragmento  INTEGER,
  contenido         TEXT NOT NULL,
  pagina            INTEGER,
  embedding         VECTOR(384),
  modelo_embedding  TEXT,
  fecha_indexacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`VECTOR(384)` no es una elección arbitraria: es la dimensión que produce el modelo local multilingüe usado por `scripts/cargar_documentos.py` (`intfloat/multilingual-e5-small`, vía `sentence-transformers`) — sin API key, sin costo, corrible en la máquina de cada estudiante. **El mismo modelo se usa para indexar y para consultar**: los embeddings de modelos distintos viven en espacios vectoriales distintos y no son comparables entre sí, por eso `fragmentos.modelo_embedding` queda registrado en cada fila.

## Qué se carga y qué queda como contexto

`documentos.json` tiene más campos de los que la tabla `documentos` guarda, a propósito: son la continuidad narrativa con las Clases 2-5 (equipo responsable, dataset, modelo, experimento, capa Medallion, nivel de confidencialidad, versión, palabras clave). `scripts/cargar_documentos.py` sólo inserta tres columnas por documento:

| Campo en `documentos.json` | Columna en `documentos` | Cómo se deriva |
| --- | --- | --- |
| `titulo` | `titulo` | directo |
| `categoria` | `categoria` | directo (una de las 8 categorías de la tabla de distribución más abajo) |
| `estado` | `activo` | `vigente`/`borrador` → `TRUE`; `archivado` → `FALSE` |
| `contenido` | se fragmenta hacia `fragmentos.contenido` | vía `dividir_en_fragmentos()` (compartida con `generar_volumen.py`) |

El resto de los campos (`equipo_id`, `dataset_id`, `modelo_id`, `experimento_id`, `componente`, `capa_medallion`, `nivel_confidencialidad`, `version`, `subcategoria`, `palabras_clave`) **no tienen columna propia en este esquema**: siguen presentes dentro del texto de `contenido` (los documentos mencionan `EQ01`, `DS05`, `MD02`, etc. explícitamente) y en los CSV de entidades, para quien quiera citarlos o extenderlos, pero no se insertan como columnas SQL. Esto coincide con el slide 16 del mockup ("Metadatos estructurados y JSONB"): recuperarlos como filtro es la motivación natural para agregar una columna `metadata JSONB` — queda como ejercicio opcional.

Solo un documento queda con `activo = FALSE`: `DOC-012`, el informe archivado y reemplazado por `DOC-015`.

## Distribución por categoría

| Categoría | Documentos | Temas |
| --- | ---: | --- |
| `infraestructura_despliegue` | 4 | on-premise, cloud, híbrida |
| `servicios_cloud` | 3 | IaaS, PaaS, servicios gestionados |
| `oltp_olap` | 4 | separación de cargas transaccionales y analíticas |
| `warehouse_analitico` | 4 | modelado dimensional, ETL/ELT, reconciliación |
| `data_lake` | 4 | gobierno, metadatos, duplicados |
| `lakehouse` | 4 | comparación de arquitecturas, sincronización |
| `arquitectura_medallion` | 4 | Bronce, Plata, Oro, reproceso |
| `big_data_costos` | 3 | volumen, escalabilidad, costos |

Hay continuidad narrativa entre varios documentos: un incidente (`DOC-008`) → un análisis de causa raíz (`DOC-009`) → una decisión de arquitectura (`DOC-010`) → una propuesta de mejora (`DOC-011`); y un informe archivado (`DOC-012`, `activo = FALSE`) reemplazado por una nota de implementación vigente (`DOC-015`).

## Consultas de prueba

`consultas_prueba.json`/`.csv` contiene 25 consultas con `consulta_id`, `consulta`, `documentos_relevantes_esperados`, `categoria_esperada`, `motivo_relevancia` y `filtro_sql_sugerido`.

- **Pensadas para búsqueda semántica**: la mayoría (`CON-01`, `CON-05`, `CON-08`, `CON-10`, `CON-20`, `CON-21`, entre otras) describen el problema con vocabulario distinto al de los documentos relevantes, a propósito, para comparar búsqueda semántica contra coincidencia literal — exactamente lo que corre `scripts/comparar_busqueda.py`.
- **Requieren filtros SQL combinados con similitud**: cada `filtro_sql_sugerido` combina `d.categoria` y/o `d.activo` y/o `f.fecha_indexacion` — las únicas columnas filtrables en este esquema mínimo.
- Dos consultas (`CON-07`, `CON-25`) piden explícitamente un filtro que el esquema mínimo no resuelve con una columna (capa Bronce/Plata/Oro, equipo responsable): quedan así a propósito, como evidencia de que ese filtro hoy sólo se resuelve por búsqueda semántica sobre el texto, o motivando la extensión opcional con `metadata JSONB`.
- Algunas consultas comparten vocabulario pero apuntan a documentos distintos (`CON-06`/`CON-10` mencionan "duplicados" pero corresponden a Data Lake y a Bronce respectivamente), para evidenciar falsos positivos de la búsqueda literal frente a la semántica.

## Notas

- Este dataset y esta práctica están diseñados específicamente para PostgreSQL y la extensión `pgvector`; no requieren ni asumen ningún otro motor.
- Todas las fechas de los documentos están entre enero y julio de 2026.
- `documento_id` (`DOC-001`..`DOC-030`) y `fragmento_id` son identificadores propios del dataset para trazabilidad entre archivos; no son columnas de la tabla física (que usa `id BIGSERIAL`). `data/documento_id_map.json`, generado por `cargar_documentos.py`, es el puente entre ambos.
- El esquema y los pasos de la práctica están tomados de `material_desarrollo/clase6.pdf` (Sección 10, "Práctica guiada con pgvector"); el volumen sintético, la comparación literal/semántica y la reindexación transaccional son extensiones que cubren el resto de la agenda de la clase (HNSW/IVFFlat, versionado, concurrencia) sin salirse del esquema mínimo.
- `scripts/responder_rag.py` es la única pieza que sale del alcance del mockup (que se detiene en la recuperación): agrega la generación con un LLM externo vía [OpenRouter](https://openrouter.ai/keys), usando `OPENROUTER_API_KEY`/`OPENROUTER_MODEL` en `.env`. Es opcional — el resto de la práctica no depende de tener esa key configurada.
- `web/` es una segunda forma de mostrar lo mismo que `responder_rag.py`, pensada para proyectar en clase: una interfaz Next.js + shadcn/ui donde se escribe una pregunta (o se elige una de las 25 de `consultas_prueba.json`) y se ve, por separado, qué recuperó pgvector (fragmentos + distancia coseno) y qué generó el LLM a partir de ese contexto. Usa el mismo modelo de embeddings (vía el microservicio `embeddings-api`) y el mismo prompt de generación que la versión CLI — no es una implementación paralela, es la misma lógica con otra interfaz. También opcional.
