const EMBEDDINGS_API_URL =
  process.env.EMBEDDINGS_API_URL || "http://localhost:8000";

/**
 * Pide el embedding de una pregunta al microservicio Python (scripts/embeddings_api.py),
 * que usa el mismo modelo local (intfloat/multilingual-e5-small) con el que se
 * cargaron los documentos. Node no corre sentence-transformers directamente:
 * este es el único puente entre la interfaz web y el modelo de embeddings.
 */
export async function obtenerEmbeddingConsulta(texto: string): Promise<number[]> {
  const respuesta = await fetch(`${EMBEDDINGS_API_URL}/embed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto, tipo: "query" }),
  });

  if (!respuesta.ok) {
    const detalle = await respuesta.text();
    throw new Error(`embeddings_api respondió ${respuesta.status}: ${detalle}`);
  }

  const datos = await respuesta.json();
  return datos.vector as number[];
}
