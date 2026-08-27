# Clase 02 — PostgreSQL y pgAdmin con Docker

Primera clase de laboratorio. Se levanta el entorno base de PostgreSQL que sirve de caso guía para las clases siguientes del curso.

## Temas vistos

- Uso de Docker Compose para levantar PostgreSQL y pgAdmin como interfaz de administración web.
- Creación de tablas, inserciones (`INSERT`) y consultas básicas (`SELECT`, `WHERE`, `ORDER BY`, `LIMIT`).
- Restricciones de integridad (constraints) y verificación de que la base las respeta.
- Administración del servidor de base de datos vía pgAdmin.

## Práctica

Se construyó un esquema base de experimentos de IA: `usuarios`, `datasets`, `modelos`, `experimentos`, `experimentos_modelos` y `métricas`. Este esquema es la base que se normaliza, optimiza y transforma en las clases 3, 5, 6 y 7.
