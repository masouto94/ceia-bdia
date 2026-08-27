# BDIA - Práctica Clase 7

Práctica de seguridad aplicada en PostgreSQL: aislamiento multi-tenant con Row Level Security (RLS), roles de aplicación de privilegio mínimo, y verificación de que ese aislamiento se sostiene también sobre una búsqueda vectorial con `pgvector`. Modela seis equipos (tenants) que comparten el mismo esquema de `documentos` y `fragmentos`, y muestra primero el problema (sin RLS, los datos de todos los equipos quedan mezclados) y después la corrección (RLS + rol de aplicación sin `BYPASSRLS`).

**El esquema de tablas y las políticas de RLS siguen el mockup de la Clase 7** (`material_desarrollo/clase7.pdf`, Sección 9), no un diseño propio: la tabla `tenants`, las columnas `tenant_id`, y el patrón `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY ... USING (...) WITH CHECK (...)` de los slides 64 a 70 son el ejercicio mínimo. La tabla `fragmentos` con embeddings de `pgvector`, el rol `aplicacion` con privilegios explícitos, y el dataset de 24 documentos son extensión propia de esta práctica, no parte literal del mockup — misma postura que la práctica de Clase 6 sostiene frente a `clase6.pdf`.

## Ruta rápida

Requisitos: Docker Engine o Docker Desktop con Docker Compose, y puertos locales `5435`, `8087` disponibles (configurables en `.env`, elegidos para no chocar con `clase_06/practica`, que usa `5434`/`8086`).

Desde `clase_07/practica`:

```bash
cp .env.example .env
sh scripts/ejecutar_pipeline.sh
```

Resultado esperado:

```text
Tenants cargados: 6
Documentos cargados: 24
Fragmentos cargados: ~35-45 (según el fragmentado de los 24 documentos, 6 oraciones por fragmento)
Modelo de embeddings: intfloat/multilingual-e5-small (dimension 384)
```

seguido de: una demostración del problema sin RLS (documentos de los 6 equipos mezclados), la activación de RLS, la creación del rol `aplicacion`, dos sesiones simuladas con conteos distintos por tenant, cuatro intentos de romper el aislamiento que fallan o devuelven 0 filas, y una búsqueda vectorial cuyo top-k no sale del tenant activo.

## Servicios

| Servicio | Responsabilidad | Acceso local |
| --- | --- | --- |
| PostgreSQL + pgvector (`postgres-vectorial`) | Tablas `tenants`/`documentos`/`fragmentos`, extensión `vector`, RLS, rol `aplicacion` | `localhost:${POSTGRES_PORT}` (default `5435`) |
| Loader de embeddings (`loader-embeddings`) | Contenedor Python con `sentence-transformers`/`psycopg2`; corre `scripts/cargar_datos.py` | Sólo dentro de la red Compose (`docker compose exec`) |
| pgAdmin (`pgadmin-vectorial`) | Inspección visual y consultas | <http://localhost:8087> (default `PGADMIN_PORT`) |
| Embeddings API (`embeddings-api`) | Microservicio FastAPI que expone el mismo modelo local (`intfloat/multilingual-e5-small`) por HTTP, para que la interfaz web no dependa de Node corriendo `sentence-transformers` | `localhost:${EMBEDDINGS_API_PORT}` (default `8011`) |
| Interfaz web (`web-ui`) | Next.js + shadcn/ui: elige un tenant, pregunta con RAG (pgvector + LLM vía OpenRouter) sobre sus documentos, e intenta explícitamente leer los de otro tenant para demostrar que RLS lo bloquea | <http://localhost:3001> (default `WEB_PORT`) |

Todos los puertos publicados se vinculan solamente a `127.0.0.1`. Las credenciales de `.env.example` son didácticas y exclusivamente locales. `embeddings-api` y `web-ui` son opcionales: si no se necesita la demo visual, alcanza con `docker compose up -d postgres-vectorial loader-embeddings pgadmin-vectorial`. La interfaz web se conecta con el rol `aplicacion` (no con `POSTGRES_USER`), precisamente para quedar sujeta a las mismas políticas de RLS que el resto de la práctica.

## Flujo y archivos

```text
data/
  tenants.csv                6 equipos (codigo, nombre); codigo mapea equipo_id de documentos.json a un tenant_id real
  documentos.json             24 documentos (4 por equipo), fuente de verdad
  documento_id_map.json       generado por cargar_datos.py (no versionado)
postgres/
  01_crear_extension_y_tablas.sql      tenants + documentos(tenant_id) + fragmentos(tenant_id)
  02_probar_sin_rls.sql                el problema: sin RLS, todos los equipos mezclados
  03_activar_rls_y_politicas.sql       ENABLE ROW LEVEL SECURITY + CREATE POLICY (USING + WITH CHECK)
  04_crear_rol_aplicacion.sql          rol aplicacion, sin BYPASSRLS, GRANT mínimo (sin DELETE, sin DDL)
  05_verificar_aislamiento.sql         SET LOCAL app.tenant_id por sesión, dos tenants comparados
  06_intentar_romper_aislamiento.sql   lectura/inserción/modificación/eliminación cruzada: deben fallar
  07_busqueda_vectorial_con_rls.sql    ORDER BY embedding <=> ... también respeta el tenant activo
  08_crear_rol_solo_lectura.sql        rol aplicacion_solo_lectura, GRANT SELECT únicamente (usado por Text-to-SQL)
scripts/
  cargar_datos.py        inserta tenants, documentos y fragmentos con tenant_id, genera embeddings
  embeddings_api.py       extensión: microservicio FastAPI de embeddings (usado por web/)
  ejecutar_sql.sh         corre un archivo de postgres/ contra postgres-vectorial, con rol configurable
  ejecutar_pipeline.sh    atajo: levanta la pila y corre los pasos 01 a 08 en orden, con el rol correcto en cada uno
  reiniciar_practica.sh   TRUNCATE de tenants/documentos/fragmentos + recarga (conserva estructura, RLS y roles)
web/
  app/page.tsx                        UI: selector de tenant activo, chat RAG (embeddings o Text-to-SQL), panel "Intentar ver otro equipo"
  app/api/tenants/route.ts            lista los tenants para los selectores
  app/api/preguntar/route.ts          orquesta recuperación (pgvector con RLS, o SQL generado por el LLM) + generación (OpenRouter)
  app/api/intentar-cruzar/route.ts    intenta leer documentos de otro tenant, para demostrar el bloqueo de RLS
  lib/db.ts, lib/embeddings.ts, lib/openrouter.ts, lib/textToSql.ts   helpers de cada paso del pipeline; db.ts usa los roles `aplicacion` y `aplicacion_solo_lectura`
  Dockerfile              build multi-stage (output: standalone)
docs/
  guia-practica.md        recorrido paso a paso
docker-compose.yml        postgres-vectorial + loader-embeddings + pgadmin-vectorial + embeddings-api + web-ui
Dockerfile.loader         imagen Python del loader (sentence-transformers, psycopg2); reutilizada por embeddings-api
requirements.txt          dependencias del loader y de embeddings_api.py
README.md                 este archivo
```

La guía operacional completa está en [`docs/guia-practica.md`](docs/guia-practica.md).

## Esquema de tablas

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants (
  id     BIGSERIAL PRIMARY KEY,
  nombre TEXT NOT NULL
);

CREATE TABLE documentos (
  id        BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  titulo    TEXT NOT NULL,
  categoria TEXT,
  activo    BOOLEAN DEFAULT TRUE
);

CREATE TABLE fragmentos (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         BIGINT NOT NULL REFERENCES tenants(id),
  documento_id      BIGINT NOT NULL REFERENCES documentos(id),
  numero_fragmento  INTEGER,
  contenido         TEXT NOT NULL,
  pagina            INTEGER,
  embedding         VECTOR(384),
  modelo_embedding  TEXT,
  fecha_indexacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`fragmentos.tenant_id` está denormalizado a propósito: cada fragmento guarda el mismo `tenant_id` que su documento padre, en lugar de resolverlo con un `JOIN` contra `documentos`. Esto es lo que permite que las políticas de RLS sobre `fragmentos` — y en particular la búsqueda vectorial del Paso 9 — filtren directamente por columna, sin que el plan de ejecución dependa de un `JOIN` para aplicar el aislamiento.

## Row Level Security

```sql
ALTER TABLE documentos
ENABLE ROW LEVEL SECURITY;

CREATE POLICY documentos_tenant
ON documentos
USING (
    tenant_id = current_setting('app.tenant_id')::BIGINT
)
WITH CHECK (
    tenant_id = current_setting('app.tenant_id')::BIGINT
);
```

La misma política se repite sobre `fragmentos`. `USING` filtra qué filas puede leer, modificar o borrar una sesión; `WITH CHECK` filtra qué filas puede insertar o dejar como resultado de un `UPDATE`. Declarar ambas cláusulas de forma explícita, aunque el valor sea idéntico, es deliberado: `postgres/06_intentar_romper_aislamiento.sql` prueba específicamente el caso de inserción cruzada, que solo `WITH CHECK` puede impedir.

## El rol `aplicacion` y por qué importa quién se conecta

PostgreSQL exime del chequeo de RLS a los superusuarios y, por defecto, al propietario de la tabla. Si los pasos de verificación de esta práctica se corrieran con el mismo usuario administrador que crea las tablas, **todas las políticas de RLS quedarían sin efecto sobre esa sesión**, sin ningún mensaje de error que lo advirtiera: la práctica mostraría que el aislamiento "funciona" cuando en realidad la sesión nunca estuvo sujeta a él.

Por eso `postgres/04_crear_rol_aplicacion.sql` crea un rol `aplicacion` sin `SUPERUSER` ni `BYPASSRLS`, con privilegios acotados a `SELECT`, `INSERT` y `UPDATE` sobre `documentos` y `fragmentos` — sin `DELETE`, sin ningún `CREATE`/`ALTER`/`DROP` — y `scripts/ejecutar_sql.sh` acepta un segundo argumento con el rol de conexión. `scripts/ejecutar_pipeline.sh` pasa `aplicacion` explícitamente en los pasos 05, 06 y 07; `docs/guia-practica.md` lo repite en cada comando correspondiente.

`postgres/08_crear_rol_solo_lectura.sql` crea un segundo rol, `aplicacion_solo_lectura`, con `GRANT SELECT` únicamente sobre `documentos` y `fragmentos` — ni siquiera `INSERT`/`UPDATE`. Es el rol bajo el que corre el modo Text-to-SQL de la interfaz web (`web/lib/db.ts`, `ejecutarSqlGenerado`): el SQL que redacta el LLM se ejecuta de verdad, así que corre con el privilegio mínimo posible, más acotado incluso que `aplicacion`, y sujeto a las mismas políticas de RLS.

## Dataset

`data/documentos.json` contiene 24 documentos (`DOC-001`..`DOC-024`, 4 por cada uno de los 6 equipos de `data/tenants.csv`), con contenido original en español ambientado en los temas de la Clase 7: autenticación vs. autorización, privilegio mínimo, fuga de contexto en pools de conexión, migraciones que rompen políticas de RLS, un incidente de recuperación semántica (RAG) que devolvió datos de otro equipo, un agente de Text-to-SQL que generó consultas fuera de su alcance, un tablero de BI que mezclaba datos por falta de un filtro, y pruebas de penetración internas sobre el aislamiento. Cada equipo (`EQ01`..`EQ06`) reutiliza la misma identidad narrativa que `clase_06/practica/data/equipos.csv`, ambientado ahora en su propio incidente o decisión relacionada con seguridad y aislamiento.

Categorías usadas: `control_de_acceso`, `aislamiento_multi_tenant`, `roles_y_privilegios`, `auditoria`, `rag_seguro`, `text_to_sql_y_agentes`.

`scripts/cargar_datos.py` inserta primero los 6 tenants desde `data/tenants.csv` (columnas `codigo`, `nombre`) y construye el mapeo `codigo -> id real`; luego, para cada documento de `documentos.json`, resuelve su `equipo_id` (por ejemplo `EQ03`) contra ese mapeo para obtener el `tenant_id` con el que inserta el documento y todos sus fragmentos.

## Notas

- Este dataset y esta práctica están diseñados específicamente para PostgreSQL, la extensión `pgvector` y el mecanismo de Row Level Security; no requieren ni asumen ningún otro motor.
- Todas las fechas de los documentos están entre enero y julio de 2026.
- `documento_id` (`DOC-001`..`DOC-024`) es un identificador propio del dataset para trazabilidad; no es una columna de la tabla física (que usa `id BIGSERIAL`). `data/documento_id_map.json`, generado por `cargar_datos.py`, es el puente entre ambos.
- El esquema mínimo y el patrón de políticas están tomados de `material_desarrollo/clase7.pdf` (Sección 9, slides 64 a 70); la tabla `fragmentos` con `pgvector`, el rol `aplicacion` con privilegios explícitos, el dataset de 24 documentos y los intentos deliberados de romper el aislamiento son extensiones propias que cubren el resto de la agenda de la clase (RAG seguro, Text-to-SQL y agentes, auditoría) sin salirse del esquema mínimo del mockup.
