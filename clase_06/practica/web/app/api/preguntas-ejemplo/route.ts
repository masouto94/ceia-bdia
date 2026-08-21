import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

// En Docker, ./data se monta en /app/data (ver docker-compose.yml). En desarrollo
// local (npm run dev, sin Docker) se usa la ruta relativa al repo.
const RUTA_CONSULTAS =
  process.env.DATA_DIR
    ? path.join(process.env.DATA_DIR, "consultas_prueba.json")
    : path.join(process.cwd(), "..", "data", "consultas_prueba.json");

export async function GET() {
  try {
    const contenido = await fs.readFile(RUTA_CONSULTAS, "utf-8");
    const consultas = JSON.parse(contenido) as Array<{
      consulta_id: string;
      consulta: string;
      categoria_esperada: string;
    }>;
    const resumen = consultas.map((q) => ({
      id: q.consulta_id,
      consulta: q.consulta,
      categoria: q.categoria_esperada,
    }));
    return NextResponse.json({ consultas: resumen });
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: mensaje, consultas: [] }, { status: 500 });
  }
}
