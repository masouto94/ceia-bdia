-- Objetivo: intentar romper deliberadamente el aislamiento multi-tenant desde una
--   sesion del equipo (tenant) 1, para comprobar que RLS + privilegio minimo lo
--   impiden en cada uno de los cuatro tipos de operacion (leer, insertar, modificar,
--   eliminar), no solo en la lectura.
-- Requiere / entradas: Pasos 01, 03 y 04 completos. EJECUTAR ESTE ARCHIVO CON EL ROL
--   aplicacion (psql -U aplicacion ...); con el usuario administrador todos estos
--   intentos tendrian exito, porque RLS no se aplica a superusuarios ni propietarios.
-- Produce / modifica: los intentos de escritura estan disenados para fallar; no debe
--   quedar ninguna fila nueva ni modificada de otro tenant al terminar este archivo.
-- Resultado esperado: SELECT cruzado devuelve 0 filas (RLS filtra en silencio, sin
--   error); INSERT cruzado falla con "new row violates row-level security policy"
--   (WITH CHECK); UPDATE cruzado afecta 0 filas (USING no encuentra la fila ajena
--   para modificar); DELETE falla con "permission denied" (el rol aplicacion no
--   tiene privilegio DELETE otorgado, ni siquiera llega a evaluarse contra RLS).
-- Guia: se usa SET (no SET LOCAL) para que app.tenant_id quede fijo durante todo
--   este script de demostracion; en la aplicacion real, cada transaccion debe fijar
--   su propio contexto con SET LOCAL dentro de BEGIN/COMMIT (ver Paso 05). Cada
--   intento de este archivo corre como una sentencia independiente en modo
--   autocommit: un error en un intento no impide que los siguientes se ejecuten,
--   que es justamente lo que se quiere observar aqui.

SET app.tenant_id = '1';

-- 1) Lectura cruzada: pedir explicitamente filas de otro tenant.
--    Esperado: 0 filas, sin error. La clausula USING de la politica excluye
--    cualquier fila cuyo tenant_id no coincida con app.tenant_id, sin importar
--    que la consulta las pida por su tenant_id explicito.
SELECT count(*) AS filas_de_otro_tenant_visibles
FROM documentos
WHERE tenant_id = 2;

-- 2) Insercion cruzada: intentar crear un documento a nombre de otro tenant.
--    Esperado: ERROR "new row violates row-level security policy for table
--    documentos" (clausula WITH CHECK).
INSERT INTO documentos (tenant_id, titulo, categoria, activo)
VALUES (2, 'Documento insertado desde el tenant 1', 'ataque_simulado', true);

-- 3) Modificacion cruzada: intentar alterar un documento de otro tenant.
--    Esperado: "UPDATE 0" (0 filas afectadas), sin error. La misma clausula USING
--    que filtra la lectura filtra que filas puede ver un UPDATE para modificar.
UPDATE documentos
SET titulo = 'Modificado desde el tenant 1'
WHERE tenant_id = 2;

-- 4) Eliminacion: intentar borrar un documento, incluso uno del propio tenant.
--    Esperado: ERROR "permission denied for table documentos". El rol aplicacion
--    no tiene privilegio DELETE otorgado (Paso 04): PostgreSQL rechaza el comando
--    por privilegios, antes de siquiera considerar ninguna politica de RLS.
DELETE FROM documentos
WHERE tenant_id = 1;
