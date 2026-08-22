# Sistema de recomendacion de contenidos

## Integrantes

- Carlos Berdaguer - a2605
- Lucas Campi - a2609
- Matias Souto - a2638

## Caso de uso

Portal general de contenidos que permite publicar, consultar y recomendar noticias, articulos, videos, publicaciones, cursos y documentos. El sistema utiliza preferencias, historial e interacciones para orientar recomendaciones y pgvector para realizar busquedas semanticas.

## Alcance

La implementacion es una prueba academica basica. Incluye el modelo relacional, datos de ejemplo, gestion de contenidos, registro de actividad y busqueda semantica. Se consideran usuarios consumidores y usuarios creadores. No se implementan autenticacion, permisos avanzados ni contenido privado.

## Tecnologias

- PostgreSQL 16 como base relacional.
- pgvector para embeddings y similitud coseno.
- FastAPI para la aplicacion.
- Docker Compose para ejecutar PostgreSQL y pgvector.
- `all-MiniLM-L6-v2` para generar vectores de 384 dimensiones.

Se descartan bases NoSQL y una base vectorial independiente para mantener una unica solucion simple y consistente.

## Datos principales identificados

- Usuarios, roles y preferencias declaradas.
- Contenidos (video, articulo, post, curso, documento), categorias y etiquetas.
- Historial de visualizaciones, busquedas y resultados de busqueda.
- Interacciones (visualizacion, reaccion, compartido, denuncia, gestion).
- Embeddings de fragmentos de texto para busqueda semantica.

## Estructura

- `docs/der.mmd`: modelo conceptual.
- `docs/modelo_logico.mmd`: modelo logico relacional.
- `sql/ddl.sql`: tipos, tablas, restricciones e indices.
- `sql/seed.sql`: datos de ejemplo.
- `sql/consultas.sql`: consultas representativas.
- `docs/arquitectura.md`: arquitectura de datos.
- `docs/informe_tecnico.md`: informe tecnico completo (incluye seguridad y escalabilidad).
- `data/ejemplos/`: ejemplos representativos.
- `embeddings/`: generacion y carga de embeddings.
- `app/`: aplicacion FastAPI.
- `docker-compose.yml`: servicios de PostgreSQL y pgAdmin.

## Ejecucion

Desde `tp_integrador`:

```bash
docker compose up -d
```

La primera inicializacion ejecuta `sql/ddl.sql` y `sql/seed.sql`. Para reinicializar una base local, deben eliminarse los volumenes o directorios de datos creados por Docker y volver a levantar los servicios.

Para ejecutar la aplicacion, configurar `.env` a partir de `.env.example` y utilizar el entorno Python del proyecto:

```bash
uv run --project .. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Para cargar embeddings, con PostgreSQL disponible (ejecutar como modulo, no como script directo):

```bash
uv run --project .. python -m embeddings.load_content_embeddings
```

## Consultas

El archivo `sql/consultas.sql` incluye:

1. filtrado por categoria y tipo;
2. relacion entre contenido, creador, categoria y etiquetas;
3. agregacion de visualizaciones e interacciones;
4. seleccion de contenidos segun preferencias e historial;
5. consulta con `EXPLAIN` para revisar indices;
6. busqueda semantica con pgvector.

## Decisiones principales

- Cada contenido pertenece a una unica categoria y su creacion se registra mediante `MANAGEMENT`.
- Las etiquetas, roles y resultados de busqueda se resuelven mediante tablas intermedias.
- Los atributos especificos se separan en tablas por tipo de contenido.
- Las interacciones comunes se almacenan en `INTERACTION` y sus detalles en tablas especializadas.
- Los embeddings son datos derivados y permanecen vinculados al contenido original mediante `content_id`.

## Limitaciones y mejoras

La solucion no incluye un recomendador avanzado, autenticacion, permisos efectivos, moderacion automatica, procesamiento distribuido ni almacenamiento analitico separado. Como mejoras futuras se podrian agregar una estrategia de hashing adaptativo, autorizacion, metricas precalculadas, procesamiento asincronico de embeddings y particionamiento de tablas de eventos.
