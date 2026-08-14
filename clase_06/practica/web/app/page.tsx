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
  fragmentos: Fragmento[];
  respuesta: string;
  modelo: string;
  uso?: Uso;
}

interface PreguntaEjemplo {
  id: string;
  consulta: string;
  categoria: string;
}

export default function Pagina() {
  const [pregunta, setPregunta] = useState("");
  const [ejemplos, setEjemplos] = useState<PreguntaEjemplo[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<RespuestaPreguntar | null>(null);

  useEffect(() => {
    fetch("/api/preguntas-ejemplo")
      .then((r) => r.json())
      .then((datos) => setEjemplos(datos.consultas ?? []))
      .catch(() => setEjemplos([]));
  }, []);

  async function preguntar() {
    if (!pregunta.trim()) return;
    setCargando(true);
    setError(null);
    setResultado(null);
    try {
      const respuesta = await fetch("/api/preguntar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pregunta, topK: 5 }),
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(datos.error ?? `Error ${respuesta.status}`);
      }
      setResultado(datos);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setCargando(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10 space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Clase 6 — Búsqueda vectorial + RAG
        </h1>
        <p className="text-muted-foreground">
          PostgreSQL + <code className="font-mono">pgvector</code> recupera los
          fragmentos más parecidos a la pregunta; un LLM (vía OpenRouter) redacta
          la respuesta usando <strong>solo</strong> ese contexto. La base nunca
          genera texto, y el LLM nunca accede directamente a la base.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Hacer una pregunta</CardTitle>
          <CardDescription>
            Escribí una pregunta libre, o elegí una de las 25 consultas de prueba
            del dataset.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {ejemplos.length > 0 && (
            <Select
              onValueChange={(id) => {
                const elegida = ejemplos.find((e) => e.id === id);
                if (elegida) setPregunta(elegida.consulta);
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Elegir una pregunta de ejemplo..." />
              </SelectTrigger>
              <SelectContent>
                {ejemplos.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.id} — {e.consulta}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Textarea
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            placeholder="¿Por qué se demoran los registros de experimentos?"
            rows={3}
          />

          <Button onClick={preguntar} disabled={cargando || !pregunta.trim()}>
            {cargando ? "Consultando..." : "Preguntar"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
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
          <Card>
            <CardHeader>
              <CardTitle>
                {resultado.fragmentos.length} fragmentos recuperados
              </CardTitle>
              <CardDescription>
                Ordenados por distancia coseno (<code>embedding &lt;=&gt; consulta</code>) —
                esto es lo único que hace PostgreSQL/pgvector.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-72 pr-4">
                <div className="space-y-4">
                  {resultado.fragmentos.map((f, i) => (
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
                      {i < resultado.fragmentos.length - 1 && (
                        <Separator className="mt-3" />
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

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
    </main>
  );
}
