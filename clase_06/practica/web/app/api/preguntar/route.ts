import { NextRequest, NextResponse } from "next/server";
import { recuperarFragmentos } from "@/lib/db";
import { obtenerEmbeddingConsulta } from "@/lib/embeddings";
import { generarRespuesta } from "@/lib/openrouter";

export async function POST(request: NextRequest) {
  let body: { pregunta?: string; topK?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Body inválido, se esperaba JSON." }, { status: 400 });
  }

  const pregunta = body.pregunta?.trim();
  if (!pregunta) {
    return NextResponse.json({ error: "Falta 'pregunta'." }, { status: 400 });
  }
  const topK = body.topK && body.topK > 0 && body.topK <= 20 ? body.topK : 5;

  try {
    // 1) Recuperación: pgvector busca los fragmentos más cercanos a la pregunta.
    const vector = await obtenerEmbeddingConsulta(pregunta);
    const fragmentos = await recuperarFragmentos(vector, topK);

    if (fragmentos.length === 0) {
      return NextResponse.json(
        { error: "No se recuperó ningún fragmento. ¿Se cargaron los documentos?" },
        { status: 404 }
      );
    }

    // 2) Generación: el LLM redacta la respuesta usando SOLO ese contexto.
    const { respuesta, modelo, uso } = await generarRespuesta(pregunta, fragmentos);

    return NextResponse.json({ pregunta, fragmentos, respuesta, modelo, uso });
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: mensaje }, { status: 502 });
  }
}
