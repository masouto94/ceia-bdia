import { Pool } from "pg";

let pool: Pool | null = null;
let poolSoloLectura: Pool | null = null;

/**
 * Pool de conexión de la aplicación web. Usa deliberadamente APLICACION_DB_USER /
 * APLICACION_DB_PASSWORD — el rol `aplicacion` creado en
 * postgres/04_crear_rol_aplicacion.sql — y NUNCA POSTGRES_USER/POSTGRES_PASSWORD
 * (el rol administrador que usa el loader). PostgreSQL exime del chequeo de RLS a
 * los superusuarios y, por defecto, al propietario de la tabla: si esta app se
 * conectara con el rol administrador, todas las políticas de RLS quedarían sin
 * efecto sobre sus consultas, sin ningún error que lo advirtiera.
 */
export function obtenerPool(): Pool {
  if (!pool) {
    pool = new Pool({
      host: process.env.POSTGRES_HOST || "localhost",
      port: Number(process.env.POSTGRES_PORT || 5432),
      database: process.env.POSTGRES_DB,
      user: process.env.APLICACION_DB_USER,
      password: process.env.APLICACION_DB_PASSWORD,
      max: 5,
    });
  }
  return pool;
}

export async function listarTenants(): Promise<{ id: number; nombre: string }[]> {
  const resultado = await obtenerPool().query(
    "SELECT id, nombre FROM tenants ORDER BY id;"
  );
  return resultado.rows;
}

export interface FragmentoRecuperado {
  id: number;
  contenido: string;
  pagina: number | null;
  titulo: string;
  categoria: string | null;
  distancia: number;
}

/**
 * Recupera los fragmentos más cercanos a un vector de consulta para el tenant
 * activo de la sesión. A propósito, la consulta NO filtra por tenant_id en su
 * cláusula WHERE: fijamos únicamente app.tenant_id vía set_config() (equivalente
 * parametrizado y seguro de `SET LOCAL app.tenant_id = '...'`, sin interpolar el
 * id en el texto SQL) y dejamos que las políticas de RLS de
 * postgres/03_activar_rls_y_politicas.sql sean las que restringen las filas
 * visibles. Ese es el punto pedagógico central: incluso una consulta sin ningún
 * filtro de tenant en el WHERE solo devuelve filas del tenant activo gracias a RLS.
 */
export async function recuperarFragmentos(
  vector: number[],
  topK: number,
  tenantId: number
): Promise<FragmentoRecuperado[]> {
  const vectorLiteral = `[${vector.join(",")}]`;
  const cliente = await obtenerPool().connect();
  try {
    await cliente.query("BEGIN");
    await cliente.query("SELECT set_config('app.tenant_id', $1, true);", [
      String(tenantId),
    ]);
    const resultado = await cliente.query(
      `SELECT f.id, f.contenido, f.pagina, d.titulo, d.categoria,
              f.embedding <=> $1::vector AS distancia
       FROM fragmentos f
       JOIN documentos d ON d.id = f.documento_id
       ORDER BY distancia
       LIMIT $2;`,
      [vectorLiteral, topK]
    );
    await cliente.query("COMMIT");
    return resultado.rows;
  } catch (error) {
    await cliente.query("ROLLBACK");
    throw error;
  } finally {
    cliente.release();
  }
}

/**
 * Intenta, desde el propio código de la aplicación, pedir documentos de OTRO
 * tenant distinto del activo en la sesión (tenantObjetivo), fijando
 * app.tenant_id = tenantActivo y consultando WHERE tenant_id = tenantObjetivo.
 * Es un ataque deliberado desde dentro de la app, para demostrar que RLS bloquea
 * el cruce incluso cuando quien lo intenta es la propia aplicación, no un
 * tercero. En un sistema correctamente configurado el resultado esperado es un
 * array vacío.
 */
export async function intentarCruzarTenant(
  tenantActivo: number,
  tenantObjetivo: number
): Promise<{ id: number; titulo: string; tenant_id: number }[]> {
  const cliente = await obtenerPool().connect();
  try {
    await cliente.query("BEGIN");
    await cliente.query("SELECT set_config('app.tenant_id', $1, true);", [
      String(tenantActivo),
    ]);
    const resultado = await cliente.query(
      "SELECT id, titulo, tenant_id FROM documentos WHERE tenant_id = $1;",
      [tenantObjetivo]
    );
    await cliente.query("COMMIT");
    return resultado.rows;
  } catch (error) {
    await cliente.query("ROLLBACK");
    throw error;
  } finally {
    cliente.release();
  }
}

/**
 * Pool separado para el rol de solo lectura (`aplicacion_solo_lectura`, creado en
 * postgres/08_crear_rol_solo_lectura.sql), usado exclusivamente para ejecutar el
 * SQL que genera el LLM en el modo Text-to-SQL. Es un pool distinto de
 * obtenerPool() a propósito: el rol `aplicacion` (usado por el resto de la app)
 * tiene INSERT/UPDATE, que este flujo no debería tener disponible bajo ninguna
 * circunstancia, ni siquiera por un bug en la validación de la consulta generada.
 */
export function obtenerPoolSoloLectura(): Pool {
  if (!poolSoloLectura) {
    poolSoloLectura = new Pool({
      host: process.env.POSTGRES_HOST || "localhost",
      port: Number(process.env.POSTGRES_PORT || 5432),
      database: process.env.POSTGRES_DB,
      user: process.env.APLICACION_SOLO_LECTURA_DB_USER,
      password: process.env.APLICACION_SOLO_LECTURA_DB_PASSWORD,
      max: 5,
    });
  }
  return poolSoloLectura;
}

/**
 * Ejecuta, bajo el rol `aplicacion_solo_lectura`, una consulta SELECT que generó
 * el LLM a partir de una pregunta en lenguaje natural (ver web/lib/textToSql.ts).
 *
 * El SQL recibido se envuelve como `SELECT * FROM ( ${sql} ) AS consulta_generada
 * LIMIT 20`, por dos motivos a la vez:
 *   1) Acota el resultado a 20 filas sin importar si el SQL generado traía su
 *      propio LIMIT, uno mayor, o ninguno.
 *   2) Fuerza a que el texto generado sea una única expresión SELECT válida: un
 *      `;` sobrante o una segunda sentencia rompen la sintaxis del subquery
 *      envolvente, y la consulta simplemente falla en vez de ejecutar algo
 *      inesperado (por ejemplo, dos sentencias separadas por `;`).
 *
 * app.tenant_id se fija con set_config() igual que en recuperarFragmentos(): el
 * SQL generado nunca necesita (ni debería) filtrar por tenant_id en su propio
 * texto, porque RLS restringe las filas visibles de todos modos. `statement_timeout`
 * se acota a 3s por si el LLM generara una consulta costosa (por ejemplo, un JOIN
 * sin condición).
 */
export async function ejecutarSqlGenerado(
  sql: string,
  tenantId: number
): Promise<Record<string, unknown>[]> {
  const cliente = await obtenerPoolSoloLectura().connect();
  try {
    await cliente.query("BEGIN");
    await cliente.query("SET LOCAL statement_timeout = '3000';");
    await cliente.query("SELECT set_config('app.tenant_id', $1, true);", [
      String(tenantId),
    ]);
    const resultado = await cliente.query(
      `SELECT * FROM ( ${sql} ) AS consulta_generada LIMIT 20;`
    );
    await cliente.query("COMMIT");
    return resultado.rows;
  } catch (error) {
    await cliente.query("ROLLBACK");
    throw error;
  } finally {
    cliente.release();
  }
}
