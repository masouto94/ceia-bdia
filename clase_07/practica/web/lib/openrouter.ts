import type { FragmentoRecuperado } from "./db";

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

const PROMPT_SISTEMA = `Sos un asistente que responde preguntas sobre los documentos internos \
de seguridad y control de acceso de tu equipo, usando EXCLUSIVAMENTE el contexto que se te \
provee a continuación. No inventes información que no esté en el contexto. Si el \
contexto no alcanza para responder, decilo explícitamente en vez de adivinar. \
Cuando cites un dato, indicá entre corchetes el número de fragmento del que sale, \
por ejemplo [fragmento 3].`;

export function armarContexto(fragmentos: FragmentoRecuperado[]): string {
  return fragmentos
    .map(
      (f, i) =>
        `[fragmento ${i + 1}] (documento: "${f.titulo}", categoría: ${f.categoria})\n${f.contenido}`
    )
    .join("\n\n");
}

/**
 * Formatea filas crudas devueltas por ejecutarSqlGenerado() (modo Text-to-SQL)
 * como bloques numerados, con el mismo estilo y separador que armarContexto()
 * usa para fragmentos, para que generarRespuesta() pueda tratar ambos modos de
 * recuperación de forma uniforme. Si no hay filas, lo dice explícitamente en el
 * contexto en vez de dejarlo vacío: sin esto, el LLM podría alucinar una
 * respuesta en lugar de admitir que la consulta no devolvió nada.
 */
export function armarContextoDesdeFilas(filas: Record<string, unknown>[]): string {
  if (filas.length === 0) {
    return "La consulta SQL generada no devolvió ninguna fila. No hay datos para responder la pregunta.";
  }
  return filas
    .map((fila, i) => {
      const lineas = Object.entries(fila).map(([clave, valor]) => `${clave}: ${valor}`);
      return `[fila ${i + 1}]\n${lineas.join("\n")}`;
    })
    .join("\n\n");
}

export interface RespuestaOpenRouter {
  respuesta: string;
  modelo: string;
  uso?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

interface MensajeChat {
  role: string;
  content: string;
}

/**
 * Hace la llamada HTTP a OpenRouter y maneja errores; centraliza lo que antes
 * vivía dentro de generarRespuesta(), para que textToSql.ts (generarSql) pueda
 * reusarlo en vez de duplicar el fetch y el manejo de errores.
 */
async function llamarOpenRouter(mensajes: MensajeChat[]): Promise<RespuestaOpenRouter> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error(
      "Falta OPENROUTER_API_KEY en el entorno del servidor (.env de clase_07/practica)."
    );
  }
  const modelo = process.env.OPENROUTER_MODEL || "openai/gpt-4o-mini";

  const respuesta = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: modelo,
      messages: mensajes,
    }),
  });

  if (!respuesta.ok) {
    const detalle = await respuesta.text();
    throw new Error(`OpenRouter respondió ${respuesta.status}: ${detalle}`);
  }

  const datos = await respuesta.json();
  return {
    respuesta: datos.choices?.[0]?.message?.content ?? "(sin respuesta)",
    modelo,
    uso: datos.usage,
  };
}

export async function generarRespuesta(
  pregunta: string,
  contexto: string
): Promise<RespuestaOpenRouter> {
  return llamarOpenRouter([
    { role: "system", content: PROMPT_SISTEMA },
    {
      role: "user",
      content: `Contexto recuperado de la base de datos:\n\n${contexto}\n\nPregunta: ${pregunta}`,
    },
  ]);
}

export { llamarOpenRouter };
