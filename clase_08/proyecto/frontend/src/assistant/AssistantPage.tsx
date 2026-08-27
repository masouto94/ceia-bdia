import { type SyntheticEvent, useState } from "react";
import * as api from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";

const modes: [api.AssistantMode, string][] = [
  ["auto", "Automático"],
  ["document", "Documentos"],
  ["relational", "Datos relacionales"],
  ["combined", "Combinado"],
];
const unavailable = {
  document: "La evidencia documental no estuvo disponible.",
  relational: "Los datos relacionales no estuvieron disponibles.",
};

export function AssistantPage() {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<api.AssistantMode>("auto");
  const [result, setResult] = useState<api.AssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.queryAssistant(prompt.trim(), mode));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "El asistente no está disponible para esta consulta.",
      );
    } finally {
      setLoading(false);
    }
  };
  return (
    <section className="workspace-page assistant-page">
      <div className="page-header">
        <div>
          <h1>Asistente</h1>
          <p className="muted">
            Consultas con evidencia del espacio de trabajo actual.
          </p>
        </div>
      </div>
      <form className="card assistant-form" onSubmit={submit}>
        <label htmlFor="assistant-mode">Fuente de respuesta</label>
        <select
          id="assistant-mode"
          value={mode}
          onChange={(event) => setMode(event.target.value as api.AssistantMode)}
        >
          {modes.map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
        <label htmlFor="assistant-prompt">Consulta</label>
        <textarea
          id="assistant-prompt"
          value={prompt}
          maxLength={1000}
          required
          rows={5}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <small className="muted">{prompt.length}/1000 caracteres</small>
        <Button type="submit" disabled={loading}>
          {loading ? "Consultando…" : "Consultar"}
        </Button>
      </form>
      {error && (
        <section className="notice error" role="alert">
          {error} Intentá nuevamente más tarde.
        </section>
      )}
      {result && (
        <article className="card assistant-result" aria-live="polite">
          <div>
            <h2>Respuesta</h2>
            <Badge>
              {result.status === "partial" ? "Respuesta parcial" : "Completa"}
            </Badge>
          </div>
          <p>{result.answer}</p>
          {result.unavailable.map((source) => (
            <p className="muted" key={source}>
              {unavailable[source]}
            </p>
          ))}
          {result.citations.length > 0 && (
            <section>
              <h3>Fuentes documentales</h3>
              <div className="citation-list">
                {result.citations.map((item) => (
                  <article className="notice" key={item.chunk_id}>
                    <strong>
                      {item.document_name} · fragmento {item.ordinal + 1}
                    </strong>
                    <p>{item.content}</p>
                  </article>
                ))}
              </div>
            </section>
          )}
          {result.relational && (
            <section>
              <h3>Procedencia relacional</h3>
              <p>
                {result.relational.sql_provenance.row_count} filas consultadas.
              </p>
              <code className="provenance">
                {result.relational.sql_provenance.query}
              </code>
            </section>
          )}
        </article>
      )}
    </section>
  );
}
