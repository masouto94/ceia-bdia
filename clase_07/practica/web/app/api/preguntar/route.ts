import { NextRequest, NextResponse } from "next/server";
import { ejecutarSqlGenerado, recuperarFragmentos } from "@/lib/db";
import { obtenerEmbeddingConsulta } from "@/lib/embeddings";
import { armarContexto, armarContextoDesdeFilas, generarRespuesta } from "@/lib/openrouter";
import { generarSql, limpiarSql, validarSql } from "@/lib/textToSql";

export async function POST(request: NextRequest) {
  let body: { pregunta?: string; tenantId?: number; modo?: "embeddings" | "sql"; topK?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Body inválido, se esperaba JSON." }, { status: 400 });
  }

  const pregunta = body.pregunta?.trim();
  if (!pregunta) {
    return NextResponse.json({ error: "Falta 'pregunta'." }, { status: 400 });
  }

  const tenantId = body.tenantId;
  if (!Number.isInteger(tenantId) || (tenantId as number) <= 0) {
    return NextResponse.json({ error: "Falta 'tenantId' o no es un entero positivo." }, { status: 400 });
  }

  const modo = body.modo === "sql" ? "sql" : "embeddings";

  if (modo === "sql") {
    // Modo Text-to-SQL: el LLM genera la consulta y esta se ejecuta de verdad,
    // pero bajo el rol de solo lectura (lib/db.ts, ejecutarSqlGenerado) y sujeta
    // a las mismas políticas de RLS que el resto de la práctica. La validación
    // de abajo (lib/textToSql.ts) es solo una capa de UX, no el control real.
    try {
      const sqlCrudo = await generarSql(pregunta);
      const sql = limpiarSql(sqlCrudo);

      const validacion = validarSql(sql);
      if (!validacion.ok) {
        return NextResponse.json({ error: validacion.motivo, sqlGenerado: sql }, { status: 422 });
      }

      let filas: Record<string, unknown>[];
      try {
        filas = await ejecutarSqlGenerado(sql, tenantId as number);
      } catch (error) {
        const mensaje = error instanceof Error ? error.message : "Error desconocido";
        return NextResponse.json({ error: mensaje, sqlGenerado: sql }, { status: 502 });
      }

      const contexto = armarContextoDesdeFilas(filas);
      const { respuesta, modelo, uso } = await generarRespuesta(pregunta, contexto);
      return NextResponse.json({
        pregunta,
        modo: "sql",
        sqlGenerado: sql,
        filas,
        respuesta,
        modelo,
        uso,
      });
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : "Error desconocido";
      return NextResponse.json({ error: mensaje }, { status: 502 });
    }
  }

  const topK = body.topK && body.topK > 0 && body.topK <= 20 ? body.topK : 5;

  try {
    // 1) Recuperación: pgvector busca los fragmentos más cercanos a la pregunta,
    //    dentro del tenant fijado en la sesión (ver lib/db.ts, RLS lo garantiza).
    const vector = await obtenerEmbeddingConsulta(pregunta);
    const fragmentos = await recuperarFragmentos(vector, topK, tenantId as number);

    if (fragmentos.length === 0) {
      return NextResponse.json(
        { error: "No se recuperó ningún fragmento. ¿Se cargaron los documentos para este equipo?" },
        { status: 404 }
      );
    }

    // 2) Generación: el LLM redacta la respuesta usando SOLO ese contexto.
    const contexto = armarContexto(fragmentos);
    const { respuesta, modelo, uso } = await generarRespuesta(pregunta, contexto);

    return NextResponse.json({ pregunta, modo: "embeddings", fragmentos, respuesta, modelo, uso });
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: mensaje }, { status: 502 });
  }
}
