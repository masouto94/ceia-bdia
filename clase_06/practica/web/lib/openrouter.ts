import type { FragmentoRecuperado } from "./db";

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

const PROMPT_SISTEMA = `Sos un asistente que responde preguntas sobre la plataforma de \
experimentos de IA de la organización, usando EXCLUSIVAMENTE el contexto que se te \
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

export interface RespuestaOpenRouter {
  respuesta: string;
  modelo: string;
  uso?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

export async function generarRespuesta(
  pregunta: string,
  fragmentos: FragmentoRecuperado[]
): Promise<RespuestaOpenRouter> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error(
      "Falta OPENROUTER_API_KEY en el entorno del servidor (.env de clase_06/practica)."
    );
  }
  const modelo = process.env.OPENROUTER_MODEL || "openai/gpt-4o-mini";
  const contexto = armarContexto(fragmentos);

  const respuesta = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: modelo,
      messages: [
        { role: "system", content: PROMPT_SISTEMA },
        {
          role: "user",
          content: `Contexto recuperado de la base de datos:\n\n${contexto}\n\nPregunta: ${pregunta}`,
        },
      ],
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
