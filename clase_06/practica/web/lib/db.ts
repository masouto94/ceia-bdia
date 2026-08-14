import { Pool } from "pg";

let pool: Pool | null = null;

export function obtenerPool(): Pool {
  if (!pool) {
    pool = new Pool({
      host: process.env.POSTGRES_HOST || "localhost",
      port: Number(process.env.POSTGRES_PORT || 5432),
      database: process.env.POSTGRES_DB,
      user: process.env.POSTGRES_USER,
      password: process.env.POSTGRES_PASSWORD,
      max: 5,
    });
  }
  return pool;
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
 * Recupera los fragmentos más cercanos a un vector de consulta, combinando
 * el filtro relacional (solo documentos activos) con el orden por distancia
 * coseno — el mismo patrón del Paso 3 de la práctica (postgres/02_consultas_similitud.sql).
 */
export async function recuperarFragmentos(
  vector: number[],
  topK: number
): Promise<FragmentoRecuperado[]> {
  const vectorLiteral = `[${vector.join(",")}]`;
  const resultado = await obtenerPool().query(
    `SELECT f.id, f.contenido, f.pagina, d.titulo, d.categoria,
            f.embedding <=> $1::vector AS distancia
     FROM fragmentos f
     JOIN documentos d ON d.id = f.documento_id
     WHERE d.activo = TRUE
     ORDER BY distancia
     LIMIT $2;`,
    [vectorLiteral, topK]
  );
  return resultado.rows;
}
