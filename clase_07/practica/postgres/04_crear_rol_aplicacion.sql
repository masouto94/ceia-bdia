-- Objetivo: crear el rol de base de datos que usa la aplicacion, con el privilegio
--   minimo necesario para operar, y sin ningun atributo que le permita saltarse RLS.
-- Requiere / entradas: tablas y politicas creadas (Pasos 01 y 03); se ejecuta como
--   el usuario administrador.
-- Produce / modifica: CREATE ROLE aplicacion; GRANT de conexion, uso de esquema,
--   SELECT/INSERT/UPDATE sobre documentos y fragmentos, y USAGE/SELECT sobre las
--   secuencias de sus columnas autoincrementales.
-- Resultado esperado: el rol aplicacion existe, no es superusuario, no tiene
--   BYPASSRLS, y no puede DELETE ni ejecutar DDL sobre documentos/fragmentos.
-- Guia: PostgreSQL exime del chequeo de RLS a los superusuarios y, por defecto, al
--   propietario de la tabla. Si los pasos siguientes (05, 06, 07) se corrieran con
--   el mismo usuario administrador que creo las tablas, todas las politicas de RLS
--   quedarian sin efecto y la practica mostraria un falso resultado de aislamiento.
--   Por eso los pasos siguientes deben ejecutarse con -U aplicacion, no con el
--   usuario administrador.

DROP ROLE IF EXISTS aplicacion;

CREATE ROLE aplicacion LOGIN PASSWORD 'aplicacion_pass';

-- GRANT CONNECT no admite current_database() como identificador directo; se usa un
-- bloque DO con SQL dinamico para no hardcodear el nombre de la base (POSTGRES_DB)
-- y que este script funcione sin importar como se llame la base en .env.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO aplicacion', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO aplicacion;

GRANT SELECT, INSERT, UPDATE ON documentos TO aplicacion;
GRANT SELECT, INSERT, UPDATE ON fragmentos TO aplicacion;

-- El rol aplicacion tambien puede leer tenants (necesario para resolver el
-- codigo->id de cada equipo al cargar datos), pero no puede modificarla: crear o
-- alterar un tenant queda reservado al rol de administracion.
GRANT SELECT ON tenants TO aplicacion;

-- Necesario para que INSERT funcione con columnas BIGSERIAL: el privilegio sobre
-- la tabla y el privilegio sobre su secuencia son cosas distintas en PostgreSQL.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aplicacion;

-- Sin DELETE: ningun caso de uso de la aplicacion requiere borrar documentos o
-- fragmentos. Sin ningun GRANT de CREATE/ALTER/DROP: la estructura y las politicas
-- de RLS se administran exclusivamente con el rol de administracion.
