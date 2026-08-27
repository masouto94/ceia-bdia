-- Objetivo: verificar que dos sesiones con distinto app.tenant_id ven conjuntos de
--   datos distintos y disjuntos, ahora que RLS esta activo.
-- Requiere / entradas: Pasos 01, 03 y 04 completos. EJECUTAR ESTE ARCHIVO CON EL ROL
--   aplicacion (psql -U aplicacion ...), no con el usuario administrador: el
--   administrador es propietario de las tablas y RLS no se le aplica por defecto,
--   con lo cual este archivo mostraria todas las filas sin importar app.tenant_id.
-- Produce / modifica: no modifica datos; solo lectura, dentro de transacciones que
--   se cierran con COMMIT.
-- Resultado esperado: la sesion con app.tenant_id = '1' ve solo documentos/fragmentos
--   de tenant_id = 1; la sesion con app.tenant_id = '2' ve solo los de tenant_id = 2.
--   Los conjuntos de resultados no se superponen.
-- Guia: SET LOCAL fija la variable de sesion solo para la transaccion en curso; al
--   hacer COMMIT (o ROLLBACK), el valor deja de estar activo. Esto es intencional:
--   en una aplicacion real con un pool de conexiones compartido, usar SET en lugar
--   de SET LOCAL dejaria el contexto de un tenant "pegado" a la conexion fisica y
--   filtrando hacia la siguiente sesion que la reutilice (ver data/documentos.json,
--   DOC-002, para un incidente real de este tipo).

-- Sesion simulada del equipo (tenant) 1.
BEGIN;
SET LOCAL app.tenant_id = '1';

SELECT count(*) AS documentos_visibles FROM documentos;
SELECT count(*) AS fragmentos_visibles FROM fragmentos;
SELECT id, titulo, categoria FROM documentos ORDER BY id;

COMMIT;

-- Sesion simulada del equipo (tenant) 2. Repetir cambiando el valor para
-- comparar manualmente contra cualquier otro tenant (1 a 6).
BEGIN;
SET LOCAL app.tenant_id = '2';

SELECT count(*) AS documentos_visibles FROM documentos;
SELECT count(*) AS fragmentos_visibles FROM fragmentos;
SELECT id, titulo, categoria FROM documentos ORDER BY id;

COMMIT;
