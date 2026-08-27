import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Download,
  Info,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import * as api from "../api";
import { RowActions } from "../components/custom/RowActions";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";

const statusLabel: Record<api.DocumentStatus, string> = {
  pending: "Pendiente",
  processing: "Procesando",
  ready: "Listo",
  failed: "Fallido",
};
const pageSizes = [10, 20, 30, 40, 50];
const defaults: api.DocumentsQuery = {
  page: 1,
  per_page: 10,
  search: "",
  status: "",
  sort: "name:asc",
};
const sorts = new Set<api.DocumentsQuery["sort"]>([
  "name:asc",
  "name:desc",
  "status:asc",
  "status:desc",
]);
const message = (reason: unknown) =>
  reason instanceof Error
    ? reason.message
    : "No se pudo completar la solicitud.";

function queryFrom(params: URLSearchParams): api.DocumentsQuery {
  const page = Number(params.get("page"));
  const perPage = Number(params.get("per_page"));
  const status = params.get("status");
  const sort = params.get("sort");
  return {
    page: page > 0 ? page : defaults.page,
    per_page: pageSizes.includes(perPage) ? perPage : defaults.per_page,
    search: params.get("search") ?? "",
    status: ["pending", "processing", "ready", "failed"].includes(status ?? "")
      ? (status as api.DocumentStatus)
      : "",
    sort: sorts.has(sort as api.DocumentsQuery["sort"])
      ? (sort as api.DocumentsQuery["sort"])
      : defaults.sort,
  };
}

function sizeLabel(bytes: number | undefined) {
  return bytes ? `${Math.ceil(bytes / 1024)} KB` : "—";
}

const date = (value: string) =>
  new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

function DocumentInfoDialog({
  document,
  onClose,
}: {
  document: api.Document | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<api.DocumentDetail | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!document) return;
    let active = true;
    api
      .getDocument(document.id)
      .then((value) => active && setDetail(value))
      .catch((reason) => active && setError(message(reason)));
    return () => {
      active = false;
    };
  }, [document, retry]);
  if (!document) return null;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent aria-describedby="document-info-description">
        <div className="dialog-header">
          <DialogTitle>Información del documento</DialogTitle>
          <DialogDescription id="document-info-description">
            Detalles y procesamiento del documento seleccionado.
          </DialogDescription>
        </div>
        {!detail && !error && <p>Cargando información…</p>}
        {error && (
          <section className="notice error" role="alert">
            <p>{error}</p>
            <Button
              variant="outline"
              onClick={() => {
                setError("");
                setRetry((value) => value + 1);
              }}
            >
              Reintentar
            </Button>
          </section>
        )}
        {detail && (
          <dl className="details-list">
            <div>
              <dt>Nombre</dt>
              <dd>{detail.name}</dd>
            </div>
            <div>
              <dt>Tipo</dt>
              <dd>{detail.content_type ?? "—"}</dd>
            </div>
            <div>
              <dt>Tamaño</dt>
              <dd>{sizeLabel(detail.size_bytes)}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd>
                <Badge>{statusLabel[detail.ingestion_status]}</Badge>
              </dd>
            </div>
            <div>
              <dt>Chunks activos</dt>
              <dd>{detail.active_chunk_count}</dd>
            </div>
            {detail.latest_run ? (
              <>
                <div>
                  <dt>Último procesamiento</dt>
                  <dd>{statusLabel[detail.latest_run.status]}</dd>
                </div>
                <div>
                  <dt>Chunks del último procesamiento</dt>
                  <dd>{detail.latest_run.chunk_count}</dd>
                </div>
                <div>
                  <dt>Fecha del último procesamiento</dt>
                  <dd>{date(detail.latest_run.created_at)}</dd>
                </div>
                {detail.latest_run.error && (
                  <div>
                    <dt>Error del último procesamiento</dt>
                    <dd>{detail.latest_run.error}</dd>
                  </div>
                )}
              </>
            ) : (
              <div>
                <dt>Último procesamiento</dt>
                <dd>Sin procesamientos registrados</dd>
              </div>
            )}
          </dl>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function DocumentsPage({ canMutate }: { canMutate: boolean }) {
  const [params, setParams] = useSearchParams();
  const queryState = useMemo(() => queryFrom(params), [params]);
  const [result, setResult] = useState<api.DocumentsResponse | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [citations, setCitations] = useState<api.Citation[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [search, setSearch] = useState(queryState.search);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selected, setSelected] = useState<api.Document | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(queryState.search), 0);
    return () => window.clearTimeout(timer);
  }, [queryState.search]);
  useEffect(() => {
    let active = true;
    api
      .getDocuments(queryState)
      .then((next) => active && setResult(next))
      .catch((reason) => active && setError(message(reason)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [queryState, reload]);

  const update = (next: Partial<api.DocumentsQuery>) => {
    setLoading(true);
    setError("");
    const output = new URLSearchParams();
    Object.entries({ ...queryState, ...next }).forEach(([key, value]) =>
      output.set(key, String(value)),
    );
    setParams(output);
  };
  const refresh = () => setReload((value) => value + 1);
  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy("upload");
    setError("");
    try {
      await api.uploadDocument(file);
      setFile(null);
      refresh();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy("");
    }
  };
  const ingest = async (document: api.Document) => {
    setBusy(document.id);
    setError("");
    try {
      await api.ingestDocument(document.id);
      refresh();
    } catch (reason) {
      setError(message(reason));
      refresh();
    } finally {
      setBusy("");
    }
  };
  const download = async (document: api.Document) => {
    setError("");
    try {
      const url = URL.createObjectURL(await api.downloadDocument(document.id));
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = document.name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(message(reason));
    }
  };
  const retrieve = async (event: FormEvent) => {
    event.preventDefault();
    if (!retrievalQuery.trim()) return;
    setBusy("retrieve");
    setError("");
    try {
      setCitations(
        (await api.retrieveDocuments(retrievalQuery.trim())).citations,
      );
    } catch (reason) {
      setError(message(reason));
      setCitations([]);
    } finally {
      setBusy("");
    }
  };
  const emptyMessage =
    queryState.search || queryState.status
      ? "No hay documentos que coincidan con los filtros."
      : canMutate
        ? "No hay documentos todavía. Subí uno para comenzar."
        : "No hay documentos todavía. La carga está disponible para integrantes autorizados.";
  const items = result?.items ?? [];

  return (
    <section className="workspace-page">
      <div className="page-header">
        <div>
          <h1>Documentos</h1>
          <p className="muted">
            Archivos privados y evidencia recuperable del espacio actual.
          </p>
        </div>
      </div>
      {canMutate && (
        <form className="notice inline-form" onSubmit={upload}>
          <label htmlFor="document-file">Archivo PDF, TXT o MD</label>
          <input
            id="document-file"
            type="file"
            accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
            required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <Button type="submit" disabled={!file || busy === "upload"}>
            <Upload />
            {busy === "upload" ? "Subiendo…" : "Subir archivo"}
          </Button>
        </form>
      )}
      <form
        className="directory-toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          update({ search, page: 1 });
        }}
      >
        <label className="search-field">
          <span className="sr-only">Buscar documentos</span>
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar documentos"
          />
        </label>
        <Button
          type="button"
          variant="outline"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          Filtros <ChevronDown />
        </Button>
        <Button type="submit">Buscar</Button>
        {filtersOpen && (
          <div className="filters">
            <label>
              Estado
              <select
                value={queryState.status}
                onChange={(event) =>
                  update({
                    status: event.target.value as api.DocumentsQuery["status"],
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="pending">Pendiente</option>
                <option value="processing">Procesando</option>
                <option value="ready">Listo</option>
                <option value="failed">Fallido</option>
              </select>
            </label>
            <label>
              Ordenar
              <select
                value={queryState.sort}
                onChange={(event) =>
                  update({
                    sort: event.target.value as api.DocumentsQuery["sort"],
                    page: 1,
                  })
                }
              >
                <option value="name:asc">Nombre A-Z</option>
                <option value="name:desc">Nombre Z-A</option>
                <option value="status:asc">Estado A-Z</option>
                <option value="status:desc">Estado Z-A</option>
              </select>
            </label>
          </div>
        )}
      </form>
      {error && !loading && (
        <section className="notice error" role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              setError("");
              setLoading(true);
              refresh();
            }}
          >
            Reintentar
          </Button>
        </section>
      )}
      {loading ? (
        <div className="desktop-table-loading" aria-label="Cargando documentos">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ) : (
        !error &&
        result && (
          <>
            <div className="desktop-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Tipo y tamaño</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead className="actions-cell">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length ? (
                    items.map((document) => (
                      <TableRow key={document.id}>
                        <TableCell>{document.name}</TableCell>
                        <TableCell>
                          {document.content_type ?? "—"} ·{" "}
                          {sizeLabel(document.size_bytes)}
                        </TableCell>
                        <TableCell>
                          <Badge>
                            {statusLabel[document.ingestion_status]}
                          </Badge>
                        </TableCell>
                        <TableCell className="actions-cell">
                          <RowActions
                            actions={[
                              {
                                label: "Ver información del documento",
                                icon: Info,
                                onClick: () => setSelected(document),
                              },
                              {
                                label: "Descargar documento",
                                icon: Download,
                                onClick: () => void download(document),
                                disabled: busy === document.id,
                              },
                              ...(canMutate
                                ? [
                                    {
                                      label:
                                        document.ingestion_status === "ready"
                                          ? "Reprocesar documento"
                                          : "Ingerir documento",
                                      icon: RefreshCw,
                                      onClick: () => void ingest(document),
                                      disabled:
                                        document.ingestion_status ===
                                        "processing",
                                      busy: busy === document.id,
                                    },
                                  ]
                                : []),
                            ]}
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4}>{emptyMessage}</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            {items.length > 0 && (
              <div className="member-cards">
                {items.map((document) => (
                  <article
                    className="member-card document-card"
                    key={document.id}
                  >
                    <strong>{document.name}</strong>
                    <Badge>{statusLabel[document.ingestion_status]}</Badge>
                    <span className="muted">
                      {document.content_type ?? "—"} ·{" "}
                      {sizeLabel(document.size_bytes)}
                    </span>
                    <footer>
                      <RowActions
                        actions={[
                          {
                            label: "Ver información del documento",
                            icon: Info,
                            onClick: () => setSelected(document),
                          },
                          {
                            label: "Descargar documento",
                            icon: Download,
                            onClick: () => void download(document),
                            disabled: busy === document.id,
                          },
                          ...(canMutate
                            ? [
                                {
                                  label:
                                    document.ingestion_status === "ready"
                                      ? "Reprocesar documento"
                                      : "Ingerir documento",
                                  icon: RefreshCw,
                                  onClick: () => void ingest(document),
                                  disabled:
                                    document.ingestion_status === "processing",
                                  busy: busy === document.id,
                                },
                              ]
                            : []),
                        ]}
                      />
                    </footer>
                  </article>
                ))}
              </div>
            )}
            <nav className="pagination" aria-label="Paginación de documentos">
              <span>{result.total} documentos</span>
              <div className="pagination-page-size">
                <label htmlFor="documents-per-page">Filas por página</label>
                <select
                  id="documents-per-page"
                  value={queryState.per_page}
                  onChange={(event) =>
                    update({ per_page: Number(event.target.value), page: 1 })
                  }
                >
                  {pageSizes.map((size) => (
                    <option key={size}>{size}</option>
                  ))}
                </select>
              </div>
              <span>
                Página {result.page} de {result.pages || 1}
              </span>
              <div>
                <Button
                  aria-label="Primera página"
                  variant="outline"
                  disabled={result.page <= 1}
                  onClick={() => update({ page: 1 })}
                >
                  <ChevronsLeft />
                </Button>
                <Button
                  aria-label="Página anterior"
                  variant="outline"
                  disabled={result.page <= 1}
                  onClick={() => update({ page: result.page - 1 })}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  aria-label="Página siguiente"
                  variant="outline"
                  disabled={result.page >= result.pages}
                  onClick={() => update({ page: result.page + 1 })}
                >
                  <ChevronRight />
                </Button>
                <Button
                  aria-label="Última página"
                  variant="outline"
                  disabled={result.page >= result.pages}
                  onClick={() => update({ page: result.pages || 1 })}
                >
                  <ChevronsRight />
                </Button>
              </div>
            </nav>
          </>
        )
      )}
      <DocumentInfoDialog
        key={selected?.id ?? "closed"}
        document={selected}
        onClose={() => setSelected(null)}
      />
      <form className="notice inline-form" onSubmit={retrieve}>
        <label htmlFor="retrieval-query">
          Buscar evidencia en documentos ingeridos
        </label>
        <input
          id="retrieval-query"
          value={retrievalQuery}
          maxLength={1000}
          required
          onChange={(event) => setRetrievalQuery(event.target.value)}
        />
        <Button type="submit" disabled={busy === "retrieve"}>
          {busy === "retrieve" ? "Buscando…" : "Buscar"}
        </Button>
      </form>
      {citations.length ? (
        <section aria-label="Fragmentos recuperados" className="citation-list">
          {citations.map((item) => (
            <article className="notice" key={item.chunk_id}>
              <strong>
                {item.document_name} · fragmento {item.ordinal + 1}
              </strong>
              <p>{item.content}</p>
            </article>
          ))}
        </section>
      ) : (
        retrievalQuery &&
        busy !== "retrieve" && (
          <p className="muted">No hay fragmentos para mostrar.</p>
        )
      )}
    </section>
  );
}
