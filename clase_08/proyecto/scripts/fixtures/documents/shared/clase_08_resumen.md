# Clase 08 — Proyecto integrador: Espacio de experimentos de IA

Proyecto integrador de tres días que combina todos los temas del curso en una aplicación multi-tenant completa: modelado relacional, RLS, RAG con pgvector, almacenamiento de objetos y autenticación.

## Temas vistos

- Arquitectura multi-servicio: FastAPI (backend), React/Vite (frontend de tenant), Astro (landing pública), PostgreSQL con pgvector y RLS, MinIO (archivos privados), Mailpit (correo local de pruebas).
- Autenticación y sesión mediante cookies HttpOnly + protección CSRF, con roles fijos por tenant (`admin`, `member`, `viewer`).
- Ingesta de documentos privados (PDF, TXT, MD), fragmentación (chunking) y generación de embeddings con pgvector.
- Aislamiento RLS multi-tenant extendido a toda la aplicación, con un panel de "plataforma" separado y aislado de la vista de tenant.
- Asistente combinado: RAG documental + Text-to-SQL sobre datos relacionales, ambos respetando el aislamiento por tenant.
- Migraciones con Alembic, fixtures de datos de prueba y scripts de verificación y reseteo seguro del entorno local.

## Práctica

Recorrido de tres días: día 1 landing/autenticación/RLS, día 2 experimentos/documentos/embeddings, día 3 asistente combinado y pruebas de aislamiento cruzado entre tenants. Pensado como demo educativa, no apto para producción.
