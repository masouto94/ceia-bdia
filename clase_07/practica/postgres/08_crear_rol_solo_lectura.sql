-- Objetivo: crear un segundo rol de base de datos, exclusivamente de solo lectura,
--   para que el SQL generado por el LLM (modo Text-to-SQL de la interfaz web) se
--   ejecute bajo un rol que NO puede escribir, ni siquiera si el texto generado
--   fuera un INSERT/UPDATE/DELETE sintacticamente valido.
-- Requiere / entradas: tablas y politicas creadas (Pasos 01 y 03); se ejecuta como
--   el usuario administrador.
-- Produce / modifica: CREATE ROLE aplicacion_solo_lectura; GRANT de conexion, uso
--   de esquema y SELECT sobre documentos y fragmentos unicamente.
-- Resultado esperado: el rol aplicacion_solo_lectura existe, no es superusuario, no
--   tiene BYPASSRLS, y no puede INSERT/UPDATE/DELETE ni ejecutar DDL sobre ninguna
--   tabla.
-- Guia: esta practica ya demuestra (Paso 6) que un rol de aplicacion sin DELETE ni
--   DDL, combinado con RLS, contiene el acceso incluso cuando la propia aplicacion
--   intenta cruzar tenants. El modo Text-to-SQL agrega un tercer factor de riesgo
--   que los pasos anteriores no cubren: el texto SQL en si no lo escribe un
--   desarrollador de confianza, lo genera un LLM a partir de lenguaje natural, y
--   puede ser manipulado con prompt injection para que intente escribir en vez de
--   solo leer. Por eso el rol que ejecuta ese SQL es uno nuevo y todavia mas
--   acotado que `aplicacion`: ni siquiera tiene INSERT/UPDATE, que `aplicacion` si
--   necesita para su propio flujo de carga. Esto es cinturon y tiradores junto con
--   la validacion de entrada de `web/lib/textToSql.ts` y las politicas de RLS del
--   Paso 5: si la validacion de la aplicacion tuviera un bug y dejara pasar una
--   sentencia de escritura, este GRANT la rechaza igual, a nivel de base de datos.
--   Corresponde al primer punto del checklist de la slide 46 de
--   material_desarrollo/clase7.pdf: "usuario SQL de solo lectura".
--
-- No se otorga ningun privilegio sobre `tenants`: a diferencia de `aplicacion`
-- (que la necesita para resolver codigo->id al cargar datos), este rol solo
-- atiende preguntas de un tenant ya fijado por la aplicacion vía set_config(); no
-- tiene ningun caso de uso que requiera leer la tabla de tenants.

DROP ROLE IF EXISTS aplicacion_solo_lectura;

CREATE ROLE aplicacion_solo_lectura LOGIN PASSWORD 'solo_lectura_pass';

-- GRANT CONNECT no admite current_database() como identificador directo; se usa un
-- bloque DO con SQL dinamico para no hardcodear el nombre de la base (POSTGRES_DB)
-- y que este script funcione sin importar como se llame la base en .env.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO aplicacion_solo_lectura', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO aplicacion_solo_lectura;

GRANT SELECT ON documentos, fragmentos TO aplicacion_solo_lectura;

-- Deliberadamente sin GRANT INSERT/UPDATE/DELETE, sin GRANT sobre secuencias (no
-- hay ningun INSERT que las necesite) y sin ningun privilegio de
-- CREATE/ALTER/DROP: este rol nunca deberia poder modificar nada, pase lo que
-- pase en el texto SQL que reciba.
