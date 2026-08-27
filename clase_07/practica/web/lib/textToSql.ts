import { llamarOpenRouter } from "./openrouter";

/**
 * IMPORTANTE — lo que sigue es una capa de UX barata, NO el control de acceso.
 *
 * limpiarSql() y validarSql() rechazan rápido, antes de tocar la base de datos,
 * las formas más obvias de SQL generado que no queremos ni intentar ejecutar
 * (texto vacío, algo que no es un SELECT, múltiples sentencias, comentarios,
 * tablas fuera del esquema expuesto). Esto mejora la experiencia (falla rápido,
 * con un mensaje claro) y reduce ruido, pero un LLM adversarialmente promptedeado
 * puede en principio producir SQL que pase esta validación y aun así intente
 * algo indebido.
 *
 * El límite real está en otro lado, en dos capas independientes de esta
 * validación:
 *   - El rol `aplicacion_solo_lectura` (postgres/08_crear_rol_solo_lectura.sql)
 *     solo tiene GRANT SELECT sobre documentos/fragmentos: no puede escribir,
 *     sin importar qué texto SQL sintácticamente válido se le pida ejecutar.
 *   - Las políticas de RLS (postgres/03_activar_rls_y_politicas.sql) restringen
 *     las filas visibles al tenant activo, sin importar qué condición WHERE (o
 *     su ausencia) traiga la consulta.
 * Si esta validación tuviera un bug y dejara pasar algo que no debería, esas dos
 * capas siguen conteniendo el daño a nivel de base de datos.
 */

const ESQUEMA_PERMITIDO = `
Tablas disponibles (solo lectura):

documentos(id, titulo, categoria, activo)
fragmentos(id, documento_id, numero_fragmento, contenido, pagina)

fragmentos.documento_id referencia documentos.id.
`;

const PROMPT_SISTEMA_SQL = `Sos un generador de consultas SQL de solo lectura para PostgreSQL.

${ESQUEMA_PERMITIDO}

Reglas estrictas:
- Generá EXACTAMENTE UNA sentencia SELECT que ayude a responder la pregunta del usuario.
- Nunca uses INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, GRANT, REVOKE ni TRUNCATE.
- No filtres por tenant_id: el sistema ya restringe los resultados automáticamente, no lo hagas vos.
- No uses punto y coma.
- No uses bloques de código markdown (nada de \`\`\`sql).
- Respondé ÚNICAMENTE con el texto SQL, sin explicaciones ni ningún otro texto.`;

/**
 * Le pide al LLM que genere una única sentencia SELECT en lenguaje SQL a partir
 * de una pregunta en lenguaje natural. Devuelve el texto crudo de la respuesta
 * (todavía sin limpiar ni validar): limpiarSql() y validarSql() se aplican
 * después, en el route handler.
 */
export async function generarSql(pregunta: string): Promise<string> {
  const { respuesta } = await llamarOpenRouter([
    { role: "system", content: PROMPT_SISTEMA_SQL },
    { role: "user", content: pregunta },
  ]);
  return respuesta;
}

/**
 * Quita los fences de bloque de código markdown (```sql ... ``` o ``` ... ```)
 * si el modelo los agregó a pesar de la instrucción, recorta espacios en blanco,
 * y quita un único ';' final si está presente.
 */
export function limpiarSql(texto: string): string {
  let limpio = texto.trim();
  const conFences = limpio.match(/^```(?:sql)?\s*([\s\S]*?)\s*```$/i);
  if (conFences) {
    limpio = conFences[1].trim();
  }
  limpio = limpio.trim();
  if (limpio.endsWith(";")) {
    limpio = limpio.slice(0, -1).trim();
  }
  return limpio;
}

const PALABRAS_PROHIBIDAS =
  /\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|COPY|CALL|EXECUTE|VACUUM|MERGE)\b/i;

const TABLAS_PERMITIDAS = new Set(["documentos", "fragmentos"]);

export type ResultadoValidacion = { ok: true } | { ok: false; motivo: string };

/**
 * Valida el SQL ya limpio (ver limpiarSql) antes de ejecutarlo. Es la capa de
 * UX descripta arriba, no el control de acceso real: ver el comentario de
 * módulo.
 */
export function validarSql(sql: string): ResultadoValidacion {
  const texto = sql.trim();

  if (!texto) {
    return { ok: false, motivo: "El modelo no generó ninguna consulta." };
  }

  if (!/^select\b/i.test(texto)) {
    return { ok: false, motivo: "Solo se permiten consultas SELECT." };
  }

  if (texto.includes(";")) {
    return { ok: false, motivo: "La consulta contiene ';': solo se permite una única sentencia." };
  }

  const prohibida = texto.match(PALABRAS_PROHIBIDAS);
  if (prohibida) {
    return {
      ok: false,
      motivo: `La consulta contiene una palabra clave no permitida: ${prohibida[0]}`,
    };
  }

  if (texto.includes("--") || texto.includes("/*")) {
    return { ok: false, motivo: "No se permiten comentarios en la consulta." };
  }

  const tablasReferenciadas = [
    ...texto.matchAll(/\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)/gi),
  ].map((m) => m[1].toLowerCase());

  for (const tabla of tablasReferenciadas) {
    if (!TABLAS_PERMITIDAS.has(tabla)) {
      return { ok: false, motivo: `La consulta referencia una tabla no permitida: ${tabla}` };
    }
  }

  return { ok: true };
}
