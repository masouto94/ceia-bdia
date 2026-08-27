import { NextRequest, NextResponse } from "next/server";
import { intentarCruzarTenant } from "@/lib/db";

function esEnteroPositivo(valor: unknown): valor is number {
  return typeof valor === "number" && Number.isInteger(valor) && valor > 0;
}

export async function POST(request: NextRequest) {
  let body: { tenantActivo?: number; tenantObjetivo?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Body inválido, se esperaba JSON." }, { status: 400 });
  }

  const { tenantActivo, tenantObjetivo } = body;
  if (!esEnteroPositivo(tenantActivo) || !esEnteroPositivo(tenantObjetivo)) {
    return NextResponse.json(
      { error: "Faltan 'tenantActivo'/'tenantObjetivo' o no son enteros positivos." },
      { status: 400 }
    );
  }

  try {
    // Intento deliberado, desde la propia aplicación, de leer documentos de otro
    // tenant fijando app.tenant_id = tenantActivo. En un sistema correctamente
    // configurado con RLS, esto debe devolver siempre un array vacío.
    const filas = await intentarCruzarTenant(tenantActivo, tenantObjetivo);
    return NextResponse.json({ filas, bloqueado: filas.length === 0 });
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: mensaje }, { status: 500 });
  }
}
