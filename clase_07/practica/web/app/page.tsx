"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Tenant {
  id: number;
  nombre: string;
}

interface Fragmento {
  id: number;
  contenido: string;
  pagina: number | null;
  titulo: string;
  categoria: string | null;
  distancia: number;
}

interface Uso {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
}

interface RespuestaPreguntar {
  pregunta: string;
  modo: "embeddings" | "sql";
  fragmentos?: Fragmento[];
  sqlGenerado?: string;
  filas?: Record<string, unknown>[];
  respuesta: string;
  modelo: string;
  uso?: Uso;
}

interface FilaCruzada {
  id: number;
  titulo: string;
  tenant_id: number;
}

interface RespuestaCruzar {
  filas: FilaCruzada[];
  bloqueado: boolean;
}

export default function Pagina() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantId, setTenantId] = useState<number | null>(null);

  const [pregunta, setPregunta] = useState("");
  const [modo, setModo] = useState<"embeddings" | "sql">("embeddings");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorSqlGenerado, setErrorSqlGenerado] = useState<string | null>(null);
  const [resultado, setResultado] = useState<RespuestaPreguntar | null>(null);

  const [tenantObjetivo, setTenantObjetivo] = useState<number | null>(null);
  const [cruzando, setCruzando] = useState(false);
  const [errorCruce, setErrorCruce] = useState<string | null>(null);
  const [resultadoCruce, setResultadoCruce] = useState<RespuestaCruzar | null>(null);

  useEffect(() => {
    fetch("/api/tenants")
      .then((r) => r.json())
      .then((datos) => {
        const lista = (datos.tenants ?? []) as Tenant[];
        setTenants(lista);
        if (lista.length > 0) {
          setTenantId(lista[0].id);
          setTenantObjetivo(lista[Math.min(1, lista.length - 1)].id);
        }
      })
      .catch(() => setTenants([]));
  }, []);

  async function preguntar() {
    if (!pregunta.trim() || tenantId == null) return;
    setCargando(true);
    setError(null);
    setErrorSqlGenerado(null);
    setResultado(null);
    try {
      const respuesta = await fetch("/api/preguntar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pregunta, tenantId, modo, topK: 5 }),
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        if (typeof datos.sqlGenerado === "string") {
          setErrorSqlGenerado(datos.sqlGenerado);
        }
        throw new Error(datos.error ?? `Error ${respuesta.status}`);
      }
      setResultado(datos);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setCargando(false);
    }
  }

  async function intentarCruzar() {
    if (tenantId == null || tenantObjetivo == null) return;
    setCruzando(true);
    setErrorCruce(null);
    setResultadoCruce(null);
    try {
      const respuesta = await fetch("/api/intentar-cruzar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenantActivo: tenantId,
          tenantObjetivo,
        }),
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(datos.error ?? `Error ${respuesta.status}`);
      }
      setResultadoCruce(datos);
    } catch (err) {
      setErrorCruce(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setCruzando(false);
    }
  }

  const nombreTenant = (id: number | null) =>
    tenants.find((t) => t.id === id)?.nombre ?? `equipo ${id}`;

  return (
    <main className="mx-auto max-w-4xl px-4 py-10 space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Clase 7 — Row Level Security multi-tenant
        </h1>
        <p className="text-muted-foreground">
          Cada pregunta se responde con búsqueda vectorial (pgvector) sobre los
          documentos del equipo activo; PostgreSQL restringe las filas visibles con
          Row Level Security, no la aplicación. La aplicación se conecta con un rol
          de privilegio mínimo (<code className="font-mono">aplicacion</code>) que
          nunca puede saltarse esas políticas.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Sesión actual</CardTitle>
          <CardDescription>
            Elegí el equipo (tenant) en cuyo nombre corren las consultas de esta
            sesión. Se fija como <code className="font-mono">app.tenant_id</code>{" "}
            en cada transacción contra la base.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Select
            value={tenantId != null ? String(tenantId) : undefined}
            onValueChange={(valor) => setTenantId(Number(valor))}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Elegir un equipo..." />
            </SelectTrigger>
            <SelectContent>
              {tenants.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hacer una pregunta</CardTitle>
          <CardDescription>
            Escribí una pregunta sobre los documentos internos del equipo activo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={modo === "embeddings" ? "default" : "outline"}
              onClick={() => setModo("embeddings")}
            >
              Búsqueda semántica (embeddings)
            </Button>
            <Button
              type="button"
              size="sm"
              variant={modo === "sql" ? "default" : "outline"}
              onClick={() => setModo("sql")}
            >
              Text-to-SQL
            </Button>
          </div>
          {modo === "sql" && (
            <p className="text-xs text-muted-foreground">
              El LLM va a redactar una consulta SQL real a partir de tu pregunta.
              Se ejecuta bajo un rol de solo lectura (<code className="font-mono">
                aplicacion_solo_lectura
              </code>) y sujeta a las mismas políticas de RLS que el resto de la
              práctica.
            </p>
          )}
          <Textarea
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            placeholder="¿Qué incidente de aislamiento tuvo nuestro equipo?"
            rows={3}
          />

          <Button
            onClick={preguntar}
            disabled={cargando || !pregunta.trim() || tenantId == null}
          >
            {cargando ? "Consultando..." : "Preguntar"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            <p>{error}</p>
            {errorSqlGenerado && (
              <pre className="mt-2 whitespace-pre-wrap break-words rounded bg-black/10 p-2 font-mono text-xs dark:bg-white/10">
                {errorSqlGenerado}
              </pre>
            )}
          </AlertDescription>
        </Alert>
      )}

      {cargando && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {resultado && !cargando && (
        <div className="space-y-6">
          {resultado.modo === "embeddings" && resultado.fragmentos && (
            <Card>
              <CardHeader>
                <CardTitle>
                  {resultado.fragmentos.length} fragmentos recuperados
                </CardTitle>
                <CardDescription>
                  Ordenados por distancia coseno (<code>embedding &lt;=&gt; consulta</code>),
                  dentro del tenant activo (<strong>{nombreTenant(tenantId)}</strong>) —
                  la consulta en sí no filtra por tenant, RLS lo hace por ella.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-72 pr-4">
                  <div className="space-y-4">
                    {resultado.fragmentos.map((f, i, fragmentos) => (
                      <div key={f.id} className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="secondary">[fragmento {i + 1}]</Badge>
                          <Badge variant="outline">{f.categoria}</Badge>
                          <span className="text-xs text-muted-foreground">
                            distancia = {f.distancia.toFixed(4)}
                          </span>
                        </div>
                        <p className="text-sm font-medium">{f.titulo}</p>
                        <p className="text-sm text-muted-foreground">{f.contenido}</p>
                        {i < fragmentos.length - 1 && <Separator className="mt-3" />}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}

          {resultado.modo === "sql" && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>SQL generado por el LLM</CardTitle>
                  <CardDescription>
                    Ejecutado bajo el rol de solo lectura{" "}
                    <code className="font-mono">aplicacion_solo_lectura</code>, con{" "}
                    <code className="font-mono">app.tenant_id</code> fijado en{" "}
                    <strong>{nombreTenant(tenantId)}</strong> — RLS se aplica igual
                    que en el modo de embeddings.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="max-h-40">
                    <pre className="whitespace-pre-wrap break-words font-mono text-xs">
                      {resultado.sqlGenerado}
                    </pre>
                  </ScrollArea>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>
                    {(resultado.filas ?? []).length} filas devueltas
                  </CardTitle>
                  <CardDescription>
                    Acotadas al tenant activo por RLS, sin importar qué haya pedido
                    la consulta generada.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-72 pr-4">
                    <div className="space-y-3">
                      {(resultado.filas ?? []).map((fila, i) => (
                        <div key={i} className="space-y-1">
                          <pre className="whitespace-pre-wrap break-words rounded bg-muted p-2 font-mono text-xs">
                            {JSON.stringify(fila, null, 2)}
                          </pre>
                          {i < (resultado.filas?.length ?? 0) - 1 && <Separator />}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Respuesta del LLM</CardTitle>
              <CardDescription>
                Modelo: <code>{resultado.modelo}</code>
                {resultado.uso?.total_tokens != null &&
                  ` · ${resultado.uso.total_tokens} tokens (${resultado.uso.prompt_tokens} entrada + ${resultado.uso.completion_tokens} salida)`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {resultado.respuesta}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Intentar ver otro equipo</CardTitle>
          <CardDescription>
            Con la sesión fijada en <strong>{nombreTenant(tenantId)}</strong>, esta
            acción le pide a la aplicación que lea documentos de otro equipo
            directamente. No debería importar que la aplicación lo pida: RLS tiene
            que bloquearlo igual.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select
            value={tenantObjetivo != null ? String(tenantObjetivo) : undefined}
            onValueChange={(valor) => setTenantObjetivo(Number(valor))}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Elegir equipo objetivo..." />
            </SelectTrigger>
            <SelectContent>
              {tenants.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            variant="outline"
            onClick={intentarCruzar}
            disabled={cruzando || tenantId == null || tenantObjetivo == null}
          >
            {cruzando ? "Intentando..." : "Intentar acceder"}
          </Button>

          {errorCruce && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{errorCruce}</AlertDescription>
            </Alert>
          )}

          {resultadoCruce && resultadoCruce.bloqueado && (
            <Alert className="border-emerald-500/50 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-500/40">
              <AlertTitle>Acceso bloqueado por RLS</AlertTitle>
              <AlertDescription className="text-emerald-800 dark:text-emerald-400">
                0 filas — Row Level Security impidió que la sesión de{" "}
                <strong>{nombreTenant(tenantId)}</strong> viera documentos de{" "}
                <strong>{nombreTenant(tenantObjetivo)}</strong>, a pesar de que la
                aplicación los pidió explícitamente.
              </AlertDescription>
            </Alert>
          )}

          {resultadoCruce && !resultadoCruce.bloqueado && (
            <Alert variant="destructive" className="border-2">
              <AlertTitle>
                ¡FUGA DE DATOS! Se leyeron {resultadoCruce.filas.length} filas de
                otro tenant
              </AlertTitle>
              <AlertDescription>
                <p className="mb-2">
                  Esto nunca debería pasar con RLS correctamente configurado. Filas
                  devueltas:
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  {resultadoCruce.filas.map((f) => (
                    <li key={f.id}>
                      #{f.id} — {f.titulo} (tenant_id={f.tenant_id})
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
