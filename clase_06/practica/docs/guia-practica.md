# Guía práctica: búsqueda vectorial con PostgreSQL y pgvector

El objetivo es ejecutar y observar, paso a paso, la práctica guiada de Clase 6 (Sección 10 del mockup): modelar documentos y fragmentos, generar embeddings con un modelo local, almacenarlos con `pgvector`, consultarlos por similitud combinada con SQL relacional, e indexar con HNSW e IVFFlat midiendo con `EXPLAIN ANALYZE`. El ritmo de trabajo es `Ejecutar → observar salida → explicación docente → continuar`.

## Resultado esperado

| Paso | Evidencia final |
| --- | --- |
| 1 | Extensión `vector` habilitada; tablas `documentos` y `fragmentos` vacías |
| 2 | 30 documentos (1 inactivo: `DOC-012`) y sus fragmentos, todos con `embedding` de 384 dimensiones |
| 3 | Ranking por distancia coseno, con y sin filtro relacional |
| 4 | Dos índices (HNSW, IVFFlat) y dos planes de `EXPLAIN ANALYZE` para comparar |

## 1. Preparar y levantar el entorno

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose ps
```

Los servicios `postgres-vectorial`, `loader-embeddings` y `pgadmin-vectorial` deben figurar en ejecución; `postgres-vectorial` debe estar saludable. La primera vez, `loader-embeddings` construye una imagen con `sentence-transformers` instalado (puede tardar unos minutos).

## 2. Paso 1 — Crear la estructura

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/01_crear_extension_y_tablas.sql
```

> **Qué observar:** `CREATE EXTENSION`, `CREATE TABLE documentos` y `CREATE TABLE fragmentos` (`postgres/01_crear_extension_y_tablas.sql`). Primero se define la estructura relacional; los vectores llegan recién en el paso siguiente.

## 3. Paso 2 — Cargar documentos y generar embeddings

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

```bash
docker compose exec -T loader-embeddings python3 scripts/cargar_documentos.py
```

Este es el único paso donde se generan vectores: `scripts/cargar_documentos.py` carga el modelo local `intfloat/multilingual-e5-small` (384 dimensiones), inserta los 30 documentos (`titulo`, `categoria`, `activo`) y, por cada uno, fragmenta el `contenido`, calcula el embedding de cada fragmento y lo inserta junto con `numero_fragmento`, `pagina`, `modelo_embedding` y `fecha_indexacion`.

> **Qué observar:** el script informa cuántos documentos y fragmentos cargó, y guarda `data/documento_id_map.json` (mapeo `DOC-xxx` → `id` real de PostgreSQL, usado por los scripts siguientes). Volver a ejecutarlo sin `--reset` no modifica nada: avisa que ya hay datos.

Verificar la carga:

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/07_verificar_carga.sql
```

Debe mostrar 30 documentos (1 inactivo), todos los fragmentos con `embedding` no nulo y una única dimensión: 384.

## 4. Paso 3 — Consultar por similitud

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/02_consultas_similitud.sql
```

> **Qué observar:** la primera consulta ordena por `embedding <=> (...)` usando el propio vector de un fragmento ya cargado como "consulta" (para poder probarlo sin una aplicación externa). La segunda combina esa distancia con `JOIN` y `WHERE d.activo = TRUE AND d.categoria = ...`, igual que el ejemplo del mockup. La tercera es una búsqueda literal (`ILIKE`) sobre el mismo contenido, para contrastar.

Para comparar las 25 consultas de prueba del dataset (búsqueda semántica vs. `tsvector`/`tsquery`) con un resumen de aciertos:

```bash
docker compose exec -T loader-embeddings python3 scripts/comparar_busqueda.py
```

> **Punto de discusión — dos ajustes que cambian el resultado, y por qué:**
>
> 1. **Título como contexto.** Los primeros intentos de este ejercicio mostraron que, sobre los 30 documentos base, una búsqueda literal simple (con `OR` entre los términos de la pregunta) empataba o superaba a la semántica en el top-5 (18/25 contra 12-13/25, según el modelo). La causa no era `pgvector` mal configurado: muchos fragmentos arrancan con una apertura genérica compartida entre documentos ("Equipo de X (EQXX) documenta/informa..."), que diluye la señal semántica del fragmento en sí. `scripts/cargar_documentos.py` y `scripts/cargar_volumen.py` calculan el embedding sobre `"{título del documento}. {fragmento}"` (no se guarda así en `contenido`, sólo se usa para el vector) — es la técnica de *contextual retrieval*. Con ese cambio solo, la semántica sube a 18/25 en el top-5 y 10/25 en el top-1: queda a la par de la literal, no todavía por delante.
> 2. **Tamaño del fragmento.** `dividir_en_fragmentos` agrupa 6 oraciones por fragmento (antes 3): con los mismos 30 documentos, esto da 52 fragmentos en vez de 84 — cada uno con más contenido propio y menos dominado por la apertura genérica. Con este cambio la semántica pasa a **22/25 en el top-5** (contra 19/25 de la literal): ahí sí gana con claridad. En el **top-1** el resultado se invierte levemente (8/25 semántica contra 11/25 literal): un fragmento más grande mejora las chances de que el documento correcto aparezca *entre los candidatos*, pero le cuesta algo de precisión para ser exactamente el primero. Para RAG esto es la métrica que importa: normalmente se le pasan varios candidatos al modelo generador, no solo el primero, así que recall@5 es más representativo que top-1.
>
> Ambos son ejemplos de un mismo principio: **cómo se fragmenta y se contextualiza el texto antes de vectorizarlo importa tanto como el modelo de embeddings elegido.** Ninguno de los dos requirió tocar el esquema (`VECTOR(384)` no cambió) ni la lógica de consulta SQL.

## 5. Paso 4 — Indexar y medir

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

Medir primero **sin** índice:

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/03_explain_sin_indice.sql
```

> **Qué observar:** un plan `Seq Scan` que recorre y ordena todas las filas de `fragmentos`.

Crear los índices:

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/04_crear_indices.sql
```

Medir de nuevo, ya **con** índices:

```bash
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/05_explain_con_indice.sql
```

> **Qué observar:** comparar filas procesadas, costo estimado y tiempo real entre los dos `EXPLAIN ANALYZE`. Con pocas filas (sólo los 30 documentos) el optimizador puede seguir eligiendo `Seq Scan`: un índice no garantiza que se use en todas las consultas, sobre todo en tablas chicas.

## 6. Extensión — Volumen sintético para medir HNSW e IVFFlat a escala

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`.

```bash
docker compose exec -T loader-embeddings python3 scripts/generar_volumen.py --objetivo 10000
docker compose exec -T loader-embeddings python3 scripts/cargar_volumen.py
```

El primer comando genera `data/fragmentos_volumen.csv` (84 fragmentos originales + variantes parafraseadas hasta llegar a ~10.000 filas). El segundo calcula el embedding de cada fila y la inserta en `fragmentos`, vinculada al documento base correspondiente vía `data/documento_id_map.json`.

Con ese volumen cargado, recrear el índice IVFFlat con más listas y repetir el `EXPLAIN ANALYZE`:

```sql
DROP INDEX idx_fragmentos_embedding_ivfflat;
CREATE INDEX idx_fragmentos_embedding_ivfflat
    ON fragmentos USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

> **Qué observar:** con miles de filas, HNSW e IVFFlat ya compiten en igualdad de condiciones contra la búsqueda exacta; ahí sí conviene esperar que el optimizador elija un índice, y recién ahí tiene sentido comparar HNSW contra IVFFlat en tiempo real, no sólo en la teoría del slide 32.

## 7. Extensión — Actualización consistente y reindexación

**Dónde ejecutarlo:** pgAdmin (Query Tool) o `psql` interactivo, no con `ejecutar_sql.sh` (necesita fijar variables con `\set` antes de correr el archivo).

Abrir `postgres/06_actualizacion_reindexacion.sql`, fijar `:fragmento_id`, `:nuevo_contenido`, `:nuevo_embedding` y `:modelo_embedding`, y ejecutar. La actualización de `contenido`, `embedding`, `modelo_embedding` y `fecha_indexacion` ocurre dentro de una única transacción: si algo falla a mitad de camino, `ROLLBACK` evita que el contenido y el vector quedaran desincronizados.

## 8. Extensión — Ciclo completo de RAG con un LLM (OpenRouter)

**Fuera del alcance del mockup**: la Sección 6 del mockup (slide 41) es explícita en que "la generación del texto ocurre después de la recuperación" y que "la responsabilidad de la base es recuperar contexto correcto, vigente y autorizado" — no generar texto. Este paso es opcional y muestra esa frontera en código: PostgreSQL/pgvector hace toda la recuperación; un LLM externo, sin acceso a la base, sólo redacta la respuesta a partir de lo que se le pasa como contexto.

**Dónde ejecutarlo:** terminal, desde `clase_06/practica`. Requiere una API key de OpenRouter (<https://openrouter.ai/keys>) cargada como `OPENROUTER_API_KEY` en `.env`.

```bash
docker compose exec -T loader-embeddings python3 scripts/responder_rag.py --consulta-id CON-05
```

También acepta una pregunta libre:

```bash
docker compose exec -T loader-embeddings python3 scripts/responder_rag.py --pregunta "¿Por qué se demoran los registros de experimentos?" --top-k 3
```

> **Qué observar:** el script imprime, en orden, (1) los fragmentos recuperados por `pgvector` con su distancia — la parte que ya se venía probando con `comparar_busqueda.py` —, (2) la respuesta del LLM, que cita `[fragmento N]` según el prompt del sistema, y (3) el conteo de tokens que devolvió OpenRouter. Si la base no tiene el fragmento correcto cargado, el LLM no puede inventarlo desde la nada porque el prompt le exige responder únicamente con el contexto provisto: el problema de calidad, si aparece, está en la recuperación, no en la generación. `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`) se puede cambiar por cualquier modelo del catálogo de OpenRouter.

## 9. Extensión — Interfaz web para la demo en clase

Muestra lo mismo que la Sección 8 (recuperación con pgvector + generación con un LLM), pero en una página para proyectar en lugar de una terminal. Es la misma lógica, no una implementación distinta: la API route de Next.js llama al mismo microservicio de embeddings, hace el mismo `SELECT ... ORDER BY embedding <=>` y arma el mismo prompt de sistema que `responder_rag.py`.

**Dónde ejecutarlo:** ya viene levantada por `docker compose up -d` (servicios `embeddings-api` y `web-ui`). Requiere `OPENROUTER_API_KEY` en `.env`, igual que la Sección 8.

Abrir <http://localhost:3000> (o el puerto configurado en `WEB_PORT`). La página permite:

1. Elegir una de las 25 preguntas de `consultas_prueba.json` en el selector, o escribir una libre.
2. Al enviar, ver primero los fragmentos que recuperó `pgvector` (documento, categoría y distancia coseno) — la parte que corre `docker compose exec ... comparar_busqueda.py` también muestra, en otro formato.
3. Debajo, la respuesta del LLM citando `[fragmento N]`, con el modelo usado y el conteo de tokens de OpenRouter.

> **Qué observar en clase:** separar visualmente las dos tarjetas (fragmentos recuperados / respuesta generada) es la forma más directa de mostrar la frontera de responsabilidad del slide 41: pgvector no redacta nada, el LLM no toca la base. Si conviene arrancar solo con el flujo de línea de comandos, alcanza con no levantar `embeddings-api`/`web-ui`: `docker compose up -d postgres-vectorial loader-embeddings pgadmin-vectorial`.

## 10. Consultar con pgAdmin

Abrir <http://localhost:8086> (o el puerto configurado en `PGADMIN_PORT`) e ingresar con `PGADMIN_DEFAULT_EMAIL`/`PGADMIN_DEFAULT_PASSWORD`.

Registrar el servidor:

| Campo | Valor |
| --- | --- |
| Name | `BDIA Clase 6` |
| Host name/address | `postgres-vectorial` |
| Port | `5432` |
| Maintenance database | valor de `POSTGRES_DB` |
| Username | valor de `POSTGRES_USER` |
| Password | valor de `POSTGRES_PASSWORD` |

Dentro de la red Docker el host es `postgres-vectorial`; `localhost:${POSTGRES_PORT}` se usa solamente desde una herramienta externa a Docker. En Query Tool, `File → Open File...` abre directamente en `postgres/` (Compose la monta en el home del usuario de pgAdmin).

## 11. Detener o reiniciar

Conservar datos:

```bash
docker compose down
```

Eliminar exclusivamente el estado de Clase 6 y volver al inicio:

```bash
sh scripts/reiniciar_practica.sh
```

Ese script ejecuta `docker compose down -v --remove-orphans` bajo el proyecto fijo `bdia_clase_06` y borra los archivos generados (`fragmentos_volumen.csv`, `documento_id_map.json`). No toca los stacks ni volúmenes de otras clases, ni el dataset fuente (`data/documentos.json`, `data/consultas_prueba.json`, etc.).

## 12. Atajo para repetir el pipeline base

```bash
sh scripts/ejecutar_pipeline.sh
```

Corre los Pasos 1 a 4 (sin volumen sintético ni el ejercicio de reindexación, que quedan como pasos manuales). Usarlo como verificación o recuperación, no como reemplazo de observar cada paso durante el primer recorrido.

## 13. Cierre conceptual

| Concepto | Evidencia observada |
| --- | --- |
| Modelado | `documentos` + `fragmentos`, con `embedding VECTOR(384)` |
| Consistencia modelo-vector | `modelo_embedding` registrado por fragmento; el mismo modelo indexa y consulta |
| Consulta híbrida | `JOIN` + `WHERE d.activo/categoria` + `ORDER BY embedding <=>` |
| Búsqueda exacta vs. índice | `EXPLAIN ANALYZE` antes/después de `CREATE INDEX` |
| HNSW vs. IVFFlat | mismo dataset, dos estrategias, comparadas a escala con el volumen sintético |
| Actualización consistente | `UPDATE` de contenido + embedding + versión dentro de una transacción |
| Búsqueda literal vs. semántica | `scripts/comparar_busqueda.py` sobre las 25 consultas de prueba |
