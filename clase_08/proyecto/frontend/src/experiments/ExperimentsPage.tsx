import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Archive,
  Info,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Search,
} from "lucide-react";
import * as api from "../api";
import { RowActions } from "../components/custom/RowActions";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Field, FieldGroup } from "../components/ui/field";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";

const statusLabel: Record<api.ExperimentStatus, string> = {
  draft: "Borrador",
  running: "En ejecución",
  completed: "Completado",
  failed: "Fallido",
};
const pageSizes = [10, 20, 30, 40, 50];
const defaultQuery: api.ExperimentsQuery = {
  page: 1,
  per_page: 10,
  search: "",
  status: "",
  archived: false,
  sort: "created_at:desc",
};
const experimentSorts = new Set<api.ExperimentsQuery["sort"]>([
  "created_at:desc",
  "created_at:asc",
  "name:asc",
  "name:desc",
  "result_count:desc",
]);
function queryFrom(params: URLSearchParams): api.ExperimentsQuery {
  const page = Number(params.get("page"));
  const perPage = Number(params.get("per_page"));
  const status = params.get("status");
  const sort = params.get("sort");
  return {
    page: page > 0 ? page : defaultQuery.page,
    per_page: pageSizes.includes(perPage) ? perPage : defaultQuery.per_page,
    search: params.get("search") ?? "",
    status: ["draft", "running", "completed", "failed"].includes(status ?? "")
      ? (status as api.ExperimentStatus)
      : "",
    archived: params.get("archived") === "true",
    sort: experimentSorts.has(sort as api.ExperimentsQuery["sort"])
      ? (sort as api.ExperimentsQuery["sort"])
      : defaultQuery.sort,
  };
}
const typeLabel: Record<api.MetricType, string> = {
  number: "Número",
  text: "Texto",
  boolean: "Sí/no",
  json: "JSON",
};
const date = (value: string) =>
  new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
const metricValue = (metric: api.Metric) => {
  const value = metric[`${metric.value_type}_value` as keyof api.Metric];
  if (metric.value_type === "boolean") return value ? "Sí" : "No";
  if (metric.value_type === "json") return JSON.stringify(value);
  return String(value ?? "—");
};

function ExperimentDialog({
  experiment,
  canMutate,
  onClose,
  onChanged,
}: {
  experiment: api.Experiment | null;
  canMutate: boolean;
  onClose: () => void;
  onChanged: (experiment?: api.Experiment) => void;
}) {
  const [detail, setDetail] = useState<api.Experiment | null>(null);
  const [error, setError] = useState("");
  const [output, setOutput] = useState("");
  const [resultStatus, setResultStatus] = useState<"completed" | "failed">(
    "completed",
  );
  const [metricName, setMetricName] = useState("");
  const [metricType, setMetricType] = useState<api.MetricType>("number");
  const [metricRaw, setMetricRaw] = useState("");
  const [transitioning, setTransitioning] = useState(false);
  useEffect(() => {
    if (!experiment) return;
    api
      .getExperiment(experiment.id)
      .then(setDetail)
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "No se pudo cargar el experimento.",
        ),
      );
  }, [experiment]);
  if (!experiment) return null;
  const transition = async (status: api.ExperimentStatus) => {
    if (transitioning) return;
    setTransitioning(true);
    try {
      await api.updateExperiment(experiment.id, { status });
      onChanged();
      onClose();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo actualizar el experimento.",
      );
    } finally {
      setTransitioning(false);
    }
  };
  const submitResult = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      let value: api.MetricInput["value"] = metricRaw;
      if (metricType === "number") value = Number(metricRaw);
      if (metricType === "boolean") value = metricRaw === "true";
      if (metricType === "json") value = JSON.parse(metricRaw) as object;
      const metrics = metricName
        ? [{ name: metricName, type: metricType, value }]
        : [];
      const result = await api.appendExperimentResult(experiment.id, {
        status: resultStatus,
        output_summary: output || undefined,
        metrics,
        terminal_status: resultStatus,
      });
      onChanged(result.experiment);
      onClose();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Revisá el valor de la métrica.",
      );
    }
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-describedby="experiment-description"
        className="experiment-dialog"
      >
        <div className="dialog-header">
          <DialogTitle>{experiment.name}</DialogTitle>
          <DialogDescription id="experiment-description">
            Estado, resultados y procedencia registrada.
          </DialogDescription>
        </div>
        {!detail && !error && <p>Cargando detalle…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {detail && (
          <>
            <dl className="details-list">
              <div>
                <dt>Estado</dt>
                <dd>
                  <Badge>{statusLabel[detail.status]}</Badge>
                </dd>
              </div>
              <div>
                <dt>Creado</dt>
                <dd>{date(detail.created_at)}</dd>
              </div>
            </dl>
            {detail.results?.length ? (
              detail.results.map((result) => (
                <article className="result-card" key={result.id}>
                  <strong>Resultado {statusLabel[result.status]}</strong>
                  <span className="muted">
                    Registrado {date(result.created_at)}
                  </span>
                  {result.input_summary && (
                    <p>
                      <b>Entrada:</b> {result.input_summary}
                    </p>
                  )}
                  {result.output_summary && (
                    <p>
                      <b>Salida:</b> {result.output_summary}
                    </p>
                  )}
                  {result.metrics.map((metric) => (
                    <div className="metric" key={metric.id}>
                      <b>{metric.name}</b>
                      <span>
                        {metricValue(metric)} {metric.unit ?? ""}
                      </span>
                      <small>
                        {typeLabel[metric.value_type]}
                        {metric.step === null ? "" : ` · paso ${metric.step}`} ·{" "}
                        {date(metric.recorded_at)}
                      </small>
                    </div>
                  ))}
                </article>
              ))
            ) : (
              <p className="notice">Todavía no hay resultados registrados.</p>
            )}
            {canMutate && detail.status === "draft" && (
              <RowActions
                actions={[
                  {
                    label: "Iniciar experimento",
                    icon: Play,
                    onClick: () => void transition("running"),
                    busy: transitioning,
                  },
                ]}
              />
            )}
            {canMutate && detail.status === "running" && (
              <form onSubmit={submitResult}>
                <FieldGroup>
                  <Field>
                    <label htmlFor="result-status">Resultado</label>
                    <select
                      id="result-status"
                      value={resultStatus}
                      onChange={(event) =>
                        setResultStatus(
                          event.target.value as "completed" | "failed",
                        )
                      }
                    >
                      <option value="completed">Completado</option>
                      <option value="failed">Fallido</option>
                    </select>
                  </Field>
                  <Field>
                    <label htmlFor="result-output">Resumen de salida</label>
                    <input
                      id="result-output"
                      value={output}
                      onChange={(event) => setOutput(event.target.value)}
                    />
                  </Field>
                  <Field>
                    <label htmlFor="metric-name">Métrica opcional</label>
                    <input
                      id="metric-name"
                      value={metricName}
                      onChange={(event) => setMetricName(event.target.value)}
                    />
                  </Field>
                  {metricName && (
                    <div className="metric-fields">
                      <Field>
                        <label htmlFor="metric-type">Tipo</label>
                        <select
                          id="metric-type"
                          value={metricType}
                          onChange={(event) =>
                            setMetricType(event.target.value as api.MetricType)
                          }
                        >
                          {Object.entries(typeLabel).map(([value, label]) => (
                            <option value={value} key={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field>
                        <label htmlFor="metric-value">Valor</label>
                        {metricType === "boolean" ? (
                          <select
                            id="metric-value"
                            value={metricRaw}
                            onChange={(event) =>
                              setMetricRaw(event.target.value)
                            }
                            required
                          >
                            <option value="">Seleccionar</option>
                            <option value="true">Sí</option>
                            <option value="false">No</option>
                          </select>
                        ) : (
                          <input
                            id="metric-value"
                            value={metricRaw}
                            onChange={(event) =>
                              setMetricRaw(event.target.value)
                            }
                            required
                          />
                        )}
                      </Field>
                    </div>
                  )}
                  <Button type="submit">Registrar resultado</Button>
                </FieldGroup>
              </form>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ExperimentsPage({ canMutate }: { canMutate: boolean }) {
  const [params, setParams] = useSearchParams();
  const query = useMemo(() => queryFrom(params), [params]);
  const [result, setResult] = useState<api.ExperimentsResponse | null>(null);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0);
  const [search, setSearch] = useState(query.search);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [name, setName] = useState(""),
    [creating, setCreating] = useState(false),
    [selected, setSelected] = useState<api.Experiment | null>(null);
  const [editing, setEditing] = useState<api.Experiment | null>(null);
  const [editingName, setEditingName] = useState("");
  const [archiving, setArchiving] = useState<api.Experiment | null>(null);
  const [mutating, setMutating] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(query.search), 0);
    return () => window.clearTimeout(timer);
  }, [query.search]);
  useEffect(() => {
    let active = true;
    api
      .getExperiments(query)
      .then((next) => active && setResult(next))
      .catch(
        (reason) =>
          active &&
          setError(
            reason instanceof Error
              ? reason.message
              : "No se pudieron cargar los experimentos.",
          ),
      )
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [query, reload]);
  const update = (next: Partial<api.ExperimentsQuery>) => {
    setLoading(true);
    setError("");
    const output = new URLSearchParams();
    Object.entries({ ...query, ...next }).forEach(([key, value]) =>
      output.set(key, String(value)),
    );
    setParams(output);
  };
  const searchSubmit = (event: FormEvent) => {
    event.preventDefault();
    update({ search, page: 1 });
  };
  const changeExperiment = async (
    experiment: api.Experiment,
    payload: api.ExperimentUpdate,
  ) => {
    if (mutating) return;
    setMutating(true);
    setError("");
    try {
      await api.updateExperiment(experiment.id, payload);
      setEditing(null);
      setArchiving(null);
      setLoading(true);
      setReload((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo actualizar el experimento.",
      );
    } finally {
      setMutating(false);
    }
  };
  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createExperiment(name.trim());
      setName("");
      setCreating(false);
      update({ page: 1 });
      setReload((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo crear el experimento.",
      );
    }
  };
  const actionsFor = (item: api.Experiment) => [
    {
      label: "Ver detalle",
      icon: Info,
      onClick: () => setSelected(item),
      disabled: mutating,
    },
    ...(canMutate
      ? [
          {
            label: "Editar nombre",
            icon: Pencil,
            onClick: () => {
              setEditing(item);
              setEditingName(item.name);
            },
            disabled: mutating,
          },
          ...(item.archived_at
            ? [
                {
                  label: "Restaurar experimento",
                  icon: RotateCcw,
                  onClick: () =>
                    void changeExperiment(item, { archived: false }),
                  disabled: mutating,
                  busy: mutating,
                },
              ]
            : item.status === "running"
              ? []
              : [
                  {
                    label: "Archivar experimento",
                    icon: Archive,
                    onClick: () => setArchiving(item),
                    disabled: mutating,
                  },
                ]),
        ]
      : []),
  ];
  return (
    <section className="experiments-page">
      <div className="page-header">
        <div>
          <h1>Experimentos</h1>
          <p className="muted">
            Seguimiento de ejecuciones, resultados y métricas.
          </p>
        </div>
        {canMutate && (
          <Button onClick={() => setCreating(true)}>
            <Plus />
            Nuevo
          </Button>
        )}
      </div>
      {creating && (
        <form className="notice inline-form" onSubmit={create}>
          <label htmlFor="experiment-name">Nombre del experimento</label>
          <input
            id="experiment-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={200}
            required
            autoFocus
          />
          <Button type="submit">Crear</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setCreating(false)}
          >
            Cancelar
          </Button>
        </form>
      )}
      <form className="directory-toolbar" onSubmit={searchSubmit}>
        <label>
          Alcance de experimentos
          <select
            aria-label="Alcance de experimentos"
            value={query.archived ? "archived" : "active"}
            onChange={(event) =>
              update({ archived: event.target.value === "archived", page: 1 })
            }
          >
            <option value="active">Activos</option>
            <option value="archived">Archivados</option>
          </select>
        </label>
        <label className="search-field">
          <span className="sr-only">Buscar experimentos</span>
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar experimentos"
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
                value={query.status}
                onChange={(event) =>
                  update({
                    status: event.target
                      .value as api.ExperimentsQuery["status"],
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="draft">Borrador</option>
                <option value="running">En ejecución</option>
                <option value="completed">Completado</option>
                <option value="failed">Fallido</option>
              </select>
            </label>
            <label>
              Ordenar
              <select
                value={query.sort}
                onChange={(event) =>
                  update({
                    sort: event.target.value as api.ExperimentsQuery["sort"],
                    page: 1,
                  })
                }
              >
                <option value="created_at:desc">Más recientes</option>
                <option value="created_at:asc">Más antiguos</option>
                <option value="name:asc">Nombre A-Z</option>
                <option value="name:desc">Nombre Z-A</option>
                <option value="result_count:desc">Más resultados</option>
              </select>
            </label>
          </div>
        )}
      </form>
      {loading ? (
        <div
          className="desktop-table-loading"
          aria-label="Cargando experimentos"
        >
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ) : error ? (
        <section className="notice error" role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              setError("");
              setLoading(true);
              setReload((value) => value + 1);
            }}
          >
            Reintentar
          </Button>
        </section>
      ) : result?.items.length ? (
        <>
          <div className="desktop-table">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Actualizado</TableHead>
                  <TableHead className="actions-cell">Acción</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>
                      <Badge>{statusLabel[item.status]}</Badge>
                    </TableCell>
                    <TableCell>{date(item.updated_at)}</TableCell>
                    <TableCell className="actions-cell">
                      <RowActions actions={actionsFor(item)} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="member-cards">
            {result.items.map((item) => (
              <article className="member-card" key={item.id}>
                <strong>{item.name}</strong>
                <Badge>{statusLabel[item.status]}</Badge>
                <span className="muted">{date(item.updated_at)}</span>
                <RowActions actions={actionsFor(item)} />
              </article>
            ))}
          </div>
          <nav className="pagination" aria-label="Paginación de experimentos">
            <span>{result.total} experimentos</span>
            <div className="pagination-page-size">
              <label htmlFor="experiments-per-page">Filas por página</label>
              <select
                id="experiments-per-page"
                value={query.per_page}
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
      ) : (
        <section className="notice">
          {query.search ||
          query.status ||
          query.archived ||
          query.sort !== defaultQuery.sort ? (
            "No hay experimentos que coincidan con los filtros."
          ) : (
            <>
              No hay experimentos todavía.
              {canMutate
                ? " Creá el primero para comenzar."
                : " Cuando el equipo cree uno, aparecerá aquí."}
            </>
          )}
        </section>
      )}
      {editing && (
        <Dialog
          open
          onOpenChange={(open) => !open && !mutating && setEditing(null)}
        >
          <DialogContent aria-describedby="edit-experiment-description">
            <DialogTitle>Editar nombre</DialogTitle>
            <DialogDescription id="edit-experiment-description">
              Actualizá el nombre del experimento.
            </DialogDescription>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const nextName = editingName.trim();
                if (nextName)
                  void changeExperiment(editing, { name: nextName });
              }}
            >
              <FieldGroup>
                <Field>
                  <label htmlFor="edit-experiment-name">
                    Nombre del experimento
                  </label>
                  <input
                    id="edit-experiment-name"
                    value={editingName}
                    onChange={(event) => setEditingName(event.target.value)}
                    maxLength={200}
                    required
                    aria-invalid={!editingName.trim()}
                  />
                </Field>
                <Button
                  type="submit"
                  disabled={mutating || !editingName.trim()}
                >
                  Guardar nombre
                </Button>
              </FieldGroup>
            </form>
          </DialogContent>
        </Dialog>
      )}
      <AlertDialog
        open={Boolean(archiving)}
        onOpenChange={(open) => !open && !mutating && setArchiving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archivar experimento</AlertDialogTitle>
            <AlertDialogDescription>
              El historial y los resultados se conservan. El experimento dejará
              de aparecer entre los activos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={mutating}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={mutating}
              onClick={() =>
                archiving &&
                void changeExperiment(archiving, { archived: true })
              }
            >
              Archivar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <ExperimentDialog
        key={selected?.id ?? "closed"}
        experiment={selected}
        canMutate={canMutate && !selected?.archived_at}
        onClose={() => setSelected(null)}
        onChanged={(changedExperiment) => {
          if (!changedExperiment) {
            setReload((value) => value + 1);
            return;
          }
          setResult((current) =>
            current
              ? {
                  ...current,
                  items: current.items.map((item) =>
                    item.id === changedExperiment.id ? changedExperiment : item,
                  ),
                }
              : current,
          );
        }}
      />
    </section>
  );
}
