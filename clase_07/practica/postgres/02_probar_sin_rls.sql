-- Objetivo: mostrar el problema que motiva esta practica: sin Row Level Security,
--   cualquier sesion que pueda conectarse ve los datos de todos los equipos mezclados.
-- Requiere / entradas: haber corrido scripts/cargar_datos.py (tenants, documentos y
--   fragmentos cargados). Se ejecuta como el usuario administrador (propietario de
--   las tablas), antes de activar RLS.
-- Produce / modifica: no modifica datos; solo lectura.
-- Resultado esperado: las consultas devuelven filas de los 6 equipos sin ningun
--   filtro, en la misma sesion, sin haber declarado a que equipo pertenece esa sesion.
-- Guia: este es el estado inicial de cualquier tabla multi-tenant que solo distingue
--   filas por una columna tenant_id sin ningun mecanismo que haga cumplir el filtro.
--   Confiar en que cada consulta de la aplicacion agregue WHERE tenant_id = ... no es
--   sostenible: alcanza una consulta que lo olvide para mezclar datos entre equipos.

SELECT
    d.tenant_id,
    t.nombre AS equipo,
    count(*) AS documentos
FROM documentos d
JOIN tenants t ON t.id = d.tenant_id
GROUP BY d.tenant_id, t.nombre
ORDER BY d.tenant_id;

-- Sin ningun WHERE tenant_id, esta consulta devuelve documentos de los 6 equipos
-- en un unico resultado: no hay forma de saber, mirando solo esta salida, que la
-- aplicacion deberia estar mostrando solamente los de un equipo especifico.
SELECT
    d.id,
    t.nombre AS equipo,
    d.titulo,
    d.categoria
FROM documentos d
JOIN tenants t ON t.id = d.tenant_id
ORDER BY d.id
LIMIT 10;
