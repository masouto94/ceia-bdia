# Clase 05 — Infraestructura de datos: arquitectura Bronze/Silver/Gold

Se construye un pipeline analítico tipo lakehouse (arquitectura medallón) sobre object storage simulado, cerrando en un data warehouse dimensional.

## Temas vistos

- Arquitectura Bronze (datos crudos inmutables) → Silver (datos limpios y validados) → Gold (warehouse dimensional).
- MinIO como object storage compatible con S3, para almacenar Bronze en CSV y Silver en Parquet.
- DuckDB para perfilado de datos, staging "text-first", reglas de calidad y transformaciones.
- PostgreSQL como warehouse dimensional: modelo Gold con tablas de hechos y tablas puente N:M.
- Control de calidad de datos: separación explícita de filas aceptadas vs. rechazadas, con códigos de error, sin ocultar registros inválidos.
- Reproducibilidad e idempotencia del pipeline mediante scripts de ejecución y reinicio.

## Práctica

Pipeline completo que ingiere dos lotes CSV de experimentos de IA, los perfila y transforma con DuckDB, y carga un modelo dimensional Gold en PostgreSQL junto con un reporte de calidad de datos.
