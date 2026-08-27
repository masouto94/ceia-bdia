-- Objetivo: comprobar que la busqueda por similitud (pgvector) tambien respeta el
--   aislamiento por tenant: RLS se aplica sobre el plan de ORDER BY ... <=> ..., no
--   solo sobre un SELECT simple.
-- Requiere / entradas: Pasos 01, 03 y 04 completos, datos cargados con embeddings.
--   EJECUTAR ESTE ARCHIVO CON EL ROL aplicacion (psql -U aplicacion ...).
-- Produce / modifica: no modifica datos; solo lectura.
-- Resultado esperado: los k fragmentos mas cercanos que devuelve la consulta
--   pertenecen unicamente al tenant activo en la sesion, aunque la tabla fragmentos
--   contenga vectores de los 6 equipos y alguno de otro equipo sea semanticamente
--   mas cercano al vector de consulta.
-- Guia: esto es exactamente la mitigacion documentada en data/documentos.json
--   (DOC-011): el filtro de tenant_id debe aplicarse junto con el ordenamiento por
--   distancia, no como un descarte posterior sobre resultados ya calculados. Con RLS
--   activo, el propio planificador de PostgreSQL incorpora la condicion de la
--   politica en el plan de ejecucion antes del ORDER BY, no despues.

SET app.tenant_id = '1';

-- Vector de consulta: se usa el embedding de un fragmento ya cargado como si fuera
-- una pregunta del usuario, para poder probar la practica sin un servicio externo
-- que genere el vector. En una aplicacion real, este vector lo calcula el mismo
-- modelo de embeddings que uso scripts/cargar_datos.py, a partir de la pregunta.
SELECT
    f.id,
    t.nombre AS equipo,
    f.tenant_id,
    d.titulo,
    round((f.embedding <=> (SELECT embedding FROM fragmentos WHERE tenant_id = 1 ORDER BY id LIMIT 1))::numeric, 4) AS distancia
FROM fragmentos f
JOIN documentos d ON d.id = f.documento_id
JOIN tenants t ON t.id = f.tenant_id
ORDER BY f.embedding <=> (SELECT embedding FROM fragmentos WHERE tenant_id = 1 ORDER BY id LIMIT 1)
LIMIT 5;

-- Verificacion explicita: todas las filas del resultado anterior deben pertenecer
-- al tenant activo. Si esta consulta devuelve una fila, el aislamiento en la
-- busqueda vectorial fallo.
SELECT count(*) AS filas_fuera_del_tenant_activo
FROM (
    SELECT
        f.tenant_id
    FROM fragmentos f
    ORDER BY f.embedding <=> (SELECT embedding FROM fragmentos WHERE tenant_id = 1 ORDER BY id LIMIT 1)
    LIMIT 5
) AS top_k
WHERE tenant_id <> 1;
