import { NextResponse } from "next/server";
import { listarTenants } from "@/lib/db";

export async function GET() {
  try {
    const tenants = await listarTenants();
    return NextResponse.json({ tenants });
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : "Error desconocido";
    return NextResponse.json({ error: mensaje, tenants: [] }, { status: 500 });
  }
}
