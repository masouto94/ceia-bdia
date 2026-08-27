-- Objetivo: activar Row Level Security sobre documentos y fragmentos y definir la
--   politica de aislamiento por tenant, para que cada sesion vea solamente las filas
--   del equipo declarado en su propio contexto.
-- Requiere / entradas: tablas creadas (Paso 01) con datos cargados; se ejecuta como
--   el usuario administrador (propietario de las tablas).
-- Produce / modifica: ENABLE ROW LEVEL SECURITY y CREATE POLICY sobre documentos y
--   fragmentos.
-- Resultado esperado: RLS activo en ambas tablas; ninguna fila visible todavia para
--   una sesion sin app.tenant_id fijado (current_setting sin valor por defecto falla).
-- Guia: USING controla que filas puede LEER/actualizar/borrar la sesion; WITH CHECK
--   controla que filas puede ESCRIBIR (INSERT/UPDATE) la sesion. Declarar ambas
--   clausulas de forma explicita, aunque el valor sea el mismo, evita que falte una
--   sin que nadie lo note (ver postgres/06_intentar_romper_aislamiento.sql, que
--   prueba especificamente el caso de insercion cruzada).

ALTER TABLE documentos
ENABLE ROW LEVEL SECURITY;

CREATE POLICY documentos_tenant
ON documentos
USING (
    tenant_id =
    current_setting('app.tenant_id')::BIGINT
)
WITH CHECK (
    tenant_id =
    current_setting('app.tenant_id')::BIGINT
);

ALTER TABLE fragmentos
ENABLE ROW LEVEL SECURITY;

CREATE POLICY fragmentos_tenant
ON fragmentos
USING (
    tenant_id =
    current_setting('app.tenant_id')::BIGINT
)
WITH CHECK (
    tenant_id =
    current_setting('app.tenant_id')::BIGINT
);
