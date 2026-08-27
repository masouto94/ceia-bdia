# Clase 07 — Seguridad aplicada: Row Level Security (RLS) multi-tenant

Se aplica seguridad a nivel de fila en PostgreSQL para lograr aislamiento multi-tenant, combinado con búsqueda vectorial sobre pgvector.

## Temas vistos

- Row Level Security: `ENABLE ROW LEVEL SECURITY` y `CREATE POLICY ... USING (...) WITH CHECK (...)`.
- Roles de aplicación de privilegio mínimo (sin `BYPASSRLS`), con separación de un rol de solo lectura.
- Demostración del problema (sin RLS los datos de distintos tenants se mezclan) frente a la solución (con RLS activo).
- Uso de `SET LOCAL app.tenant_id` para fijar el contexto de tenant por sesión/transacción.
- Verificación de que el aislamiento también aplica a la búsqueda vectorial: el top-k de similitud nunca sale del tenant activo.
- Intentos activos de romper el aislamiento (lectura, inserción, modificación y borrado cruzado entre tenants), que deben fallar.

## Práctica

RLS aplicado a un esquema con 6 tenants/equipos, documentos y fragmentos vectorizados, más una interfaz web que demuestra el bloqueo cruzado entre tenants tanto para RAG como para Text-to-SQL con un rol de solo lectura.
