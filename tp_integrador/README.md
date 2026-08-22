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
- MinIO para el almacenamiento de archivos.
- FastAPI para la aplicacion.
- Docker Compose para ejecutar PostgreSQL, pgvector y MinIO.
- `all-MiniLM-L6-v2` para generar vectores de 384 dimensiones.

Se descartan bases NoSQL y una base vectorial independiente para mantener una unica solucion simple y consistente.

## Datos principales identificados

- Usuarios, roles y preferencias declaradas.
- Contenidos (video, foto, articulo, post, curso, documento), categorias y etiquetas.
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
- `docker-compose.yml`: servicios de PostgreSQL, pgAdmin y MinIO.
- `data/`: archivos binarios de ejemplo (foto y video) para cargar en MinIO.

## Ejecucion

Desde `tp_integrador`, usar el script de inicializacion:

```bash
./setup.sh
```

Este script detiene y reinicia los contenedores (PostgreSQL, pgAdmin y MinIO), ejecuta `sql/ddl.sql` y `sql/seed.sql` en la primera inicializacion, espera a que MinIO este disponible y sube los archivos binarios de ejemplo al bucket `assets` usando `docker run minio/mc`. Para eliminar todos los datos incluyendo MinIO:

```bash
./setup.sh --purge
```

Para ejecutar la aplicacion, configurar `.env` a partir de `.env.example` y utilizar el entorno Python del proyecto:

```bash
uv run --project .. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alternativamente, usar el script combinado:

```bash
./setup.sh && ./run_app.sh
```

Para cargar embeddings, con PostgreSQL disponible (ejecutar como modulo, no como script directo):

```bash
uv run --project .. python -m embeddings.load_content_embeddings
```

## Consultas

El archivo `sql/consultas.sql` incluye:

1. filtrado por categoria y tipo;
2. relacion entre contenido, categoria y etiquetas;
3. agregacion de visualizaciones e interacciones;
4. seleccion de contenidos segun preferencias e historial;
5. consulta con `EXPLAIN` para revisar indices;
6. busqueda semantica con pgvector.

## Decisiones principales

- Cada contenido pertenece a una unica categoria y referencia mediante `creator_id` al usuario creador.
- `MANAGEMENT` registra acciones de gestion como edicion y eliminacion.
- Las etiquetas, roles y resultados de busqueda se resuelven mediante tablas intermedias.
- Los atributos especificos se separan en tablas por tipo de contenido.
- Las interacciones comunes se almacenan en `INTERACTION` y sus detalles en tablas especializadas.
- Los archivos binarios (fotos y videos) se almacenan en MinIO (S3-compatible); la base relacional almacena solo la URL de referencia, manteniendo separacion entre datos estructurados y no estructurados.
- Los embeddings son datos derivados y permanecen vinculados al contenido original mediante `content_id`.

## Limitaciones y mejoras

La solucion no incluye un recomendador avanzado, autenticacion, permisos efectivos, moderacion automatica, procesamiento distribuido ni almacenamiento analitico separado. Como mejoras futuras se podrian agregar una estrategia de hashing adaptativo, autorizacion, metricas precalculadas, procesamiento asincronico de embeddings y particionamiento de tablas de eventos.
