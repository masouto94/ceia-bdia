# Clase 03 — Diseño relacional, consultas intermedias y optimización

Se profundiza sobre el esquema de experimentos de IA creado en la clase 2, aplicando normalización y técnicas de optimización de consultas en PostgreSQL.

## Temas vistos

- Normalización (1FN, 2FN, 3FN): pasaje de columnas de texto libre a tablas catálogo.
- `JOIN`, subconsultas y funciones de ventana (window functions).
- Agregaciones con `GROUP BY`/`HAVING` y cálculo de rankings.
- Análisis de planes de ejecución con `EXPLAIN ANALYZE`, creación de índices y comparación de rendimiento antes/después.
- Vistas y vistas materializadas para consultas analíticas recurrentes.
- Uso de `JSONB` para almacenar parámetros flexibles de configuración de modelos.

## Práctica

Se amplió y refinó el esquema de experimentos de IA con normalización, índices, vistas y consultas analíticas, resuelto en una secuencia de 10 scripts SQL.
