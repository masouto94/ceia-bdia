import {
  type FormEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Info,
  RefreshCw,
  Search,
} from "lucide-react";
import * as api from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Dialog,
  DialogClose,
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../components/ui/tooltip";
import { validateCalendarDateRange } from "../dashboard/calendarDateRange";

const pageSizes = [10, 20, 25, 50, 100];
const actions: Record<string, string> = {
  "auth.registration": "Registro de cuenta",
  "auth.login": "Inicio de sesión",
  "auth.logout": "Cierre de sesión",
  "auth.recovery.request": "Solicitud de recuperación",
  "auth.recovery.confirm": "Confirmación de recuperación",
  "security.csrf_denied": "Solicitud de seguridad rechazada",
  "membership.created": "Persona agregada",
  "membership.role_changed": "Rol actualizado",
  "membership.activation_changed": "Estado de persona actualizado",
  "document.upload": "Subida de documento",
  "document.ingest.started": "Ingesta de documento iniciada",
  "document.ingest.reprocessed": "Ingesta de documento reprocesada",
  "document.ingest.completed": "Ingesta de documento completada",
  "document.ingest.failed": "Ingesta de documento fallida",
  "experiment.created": "Experimento creado",
  "experiment.renamed": "Experimento renombrado",
  "experiment.result_added": "Resultado agregado",
  "experiment.archived": "Experimento archivado",
  "experiment.restored": "Experimento restaurado",
  "experiment.status_transition": "Transición de estado",
};
const outcomes: Record<string, string> = {
  success: "Correcto",
  denied: "Denegado",
  failed: "Fallido",
  rate_limited: "Límite alcanzado",
};
const sources: Record<api.AuditSource, string> = {
  audit: "Auditoría",
  experiment_status: "Estados de experimentos",
  ingestion: "Ingesta",
};
const safeDetailKeys: Record<string, string> = {
  filename: "Archivo",
  previous_status: "Estado anterior",
  next_status: "Estado siguiente",
  chunk_count: "Fragmentos",
};

type Filters = api.AuditEventsQuery;
const localDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const dateOffset = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return localDate(date);
};
const defaults = (): Filters => ({
  from: dateOffset(6),
  to: dateOffset(0),
  search: "",
  action: "",
  outcome: "",
  actor_id: "",
  page: 1,
  per_page: 25,
});
function queryFrom(params: URLSearchParams): Filters {
  const fallback = defaults();
  const page = Number(params.get("page"));
  const perPage = Number(params.get("per_page"));
  const from = params.get("from") ?? fallback.from;
  const to = params.get("to") ?? fallback.to;
  return {
    from,
    to,
    search: params.get("search") ?? "",
    action: params.get("action") ?? "",
    outcome: params.get("outcome") ?? "",
    actor_id: params.get("actor_id") ?? "",
    page: page > 0 ? page : 1,
    per_page: pageSizes.includes(perPage) ? perPage : fallback.per_page,
  };
}
const actionLabel = (action: string) => actions[action] ?? action;
const dateLabel = (value: string) =>
  new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
const safeDetails = (detail: unknown) =>
  Object.entries(
    detail && typeof detail === "object" && !Array.isArray(detail)
      ? (detail as Record<string, unknown>)
      : {},
  ).filter(
    ([key, value]) =>
      key in safeDetailKeys &&
      (typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean"),
  );

function DetailsDialog({
  event,
  onClose,
}: {
  event: api.AuditEvent | null;
  onClose: () => void;
}) {
  if (!event) return null;
  const details = safeDetails(event.detail);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent aria-describedby="audit-event-description">
        <div className="dialog-header">
          <DialogTitle>Detalles del evento</DialogTitle>
          <DialogDescription id="audit-event-description">
            Solo se muestran datos seguros del registro.
          </DialogDescription>
        </div>
        <dl className="details-list">
          <div>
            <dt>Acción</dt>
            <dd>{actionLabel(event.action)}</dd>
          </div>
          <div>
            <dt>Recurso</dt>
            <dd>{event.resource ?? "—"}</dd>
          </div>
          {details.map(([key, value]) => (
            <div key={key}>
              <dt>{safeDetailKeys[key]}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
        <div className="dialog-footer">
          <DialogClose asChild>
            <Button variant="outline">Cerrar</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}
function DetailsButton({
  event,
  onClick,
}: {
  event: api.AuditEvent;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger>
        <Button
          variant="outline"
          className="row-action-button"
          aria-label={`Ver detalles de ${actionLabel(event.action)}`}
          onClick={onClick}
        >
          <Info />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Ver detalles seguros</TooltipContent>
    </Tooltip>
  );
}
function EventRow({
  event,
  onSelect,
}: {
  event: api.AuditEvent;
  onSelect: () => void;
}) {
  return (
    <TableRow>
      <TableCell>{dateLabel(event.occurred_at)}</TableCell>
      <TableCell>{event.actor?.email ?? "Sistema"}</TableCell>
      <TableCell>{actionLabel(event.action)}</TableCell>
      <TableCell>
        <Badge>{outcomes[event.outcome] ?? event.outcome}</Badge>
      </TableCell>
      <TableCell>{event.resource ?? "—"}</TableCell>
      <TableCell>{sources[event.source] ?? event.source}</TableCell>
      <TableCell className="actions-cell">
        <DetailsButton event={event} onClick={onSelect} />
      </TableCell>
    </TableRow>
  );
}

export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const query = useMemo(() => queryFrom(params), [params]);
  const [draft, setDraft] = useState(query);
  const [members, setMembers] = useState<api.Member[]>([]);
  const [result, setResult] = useState<api.AuditEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<api.AuditEvent | null>(null);
  useLayoutEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser navigation is external state, not a local render loop.
    setDraft(query);
  }, [query]);
  useEffect(() => {
    let active = true;
    const loadMembers = async () => {
      try {
        const collected = new Map<string, api.Member>();
        for (let page = 1; active; page += 1) {
          const next = await api.getMembers({
            page,
            per_page: 50,
            search: "",
            role: "",
            status: "",
            sort: "email:asc",
          });
          next.items.forEach((member) => collected.set(member.user_id, member));
          if (page >= next.pages) break;
        }
        if (active) setMembers([...collected.values()]);
      } catch {
        if (active) setMembers([]);
      }
    };
    void loadMembers();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    api
      .getAuditEvents(query)
      .then((next) => {
        if (active) setResult(next);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "No se pudo cargar la auditoría.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, retry]);
  const update = (next: Partial<Filters>) => {
    setLoading(true);
    setError("");
    const merged = { ...query, ...next };
    const output = new URLSearchParams();
    Object.entries(merged).forEach(([key, value]) => {
      if (value !== "") output.set(key, String(value));
    });
    setParams(output);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!validateCalendarDateRange(draft.from, draft.to, 31).valid) {
      setError(
        "El período debe ser válido y tener un máximo 31 días inclusivos.",
      );
      return;
    }
    setError("");
    update({ ...draft, page: 1 });
  };
  return (
    <section className="audit-page">
      <div className="page-header">
        <div>
          <h1>Auditoría</h1>
          <p className="muted">
            Consultá la actividad del espacio de trabajo. No se pueden modificar
            registros.
          </p>
        </div>
      </div>
      <form className="directory-toolbar audit-toolbar" onSubmit={submit}>
        <label>
          Desde
          <input
            aria-label="Desde"
            type="date"
            value={draft.from}
            onChange={(event) =>
              setDraft({ ...draft, from: event.target.value })
            }
          />
        </label>
        <label>
          Hasta
          <input
            aria-label="Hasta"
            type="date"
            value={draft.to}
            onChange={(event) => setDraft({ ...draft, to: event.target.value })}
          />
        </label>
        <label className="search-field">
          <Search />
          <span className="sr-only">Buscar eventos</span>
          <input
            aria-label="Buscar eventos"
            value={draft.search}
            placeholder="Buscar acción o recurso"
            onChange={(event) =>
              setDraft({ ...draft, search: event.target.value })
            }
          />
        </label>
        <label>
          Acción
          <select
            value={draft.action}
            onChange={(event) =>
              setDraft({ ...draft, action: event.target.value })
            }
          >
            <option value="">Todas</option>
            {Object.entries(actions).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Resultado
          <select
            value={draft.outcome}
            onChange={(event) =>
              setDraft({ ...draft, outcome: event.target.value })
            }
          >
            <option value="">Todos</option>
            {Object.entries(outcomes).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Actor
          <select
            value={draft.actor_id}
            onChange={(event) =>
              setDraft({ ...draft, actor_id: event.target.value })
            }
          >
            <option value="">Todas las personas</option>
            {members.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {member.email}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit">Aplicar filtros</Button>
      </form>
      {loading ? (
        <>
          <p className="sr-only">Cargando auditoría</p>
          <div className="desktop-table-loading">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        </>
      ) : error ? (
        <section className="notice error" role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              setError("");
              setRetry((value) => value + 1);
            }}
          >
            <RefreshCw data-icon="inline-start" />
            Reintentar
          </Button>
        </section>
      ) : (
        result &&
        (result.items.length === 0 ? (
          <section className="notice">
            No hay eventos que coincidan con los filtros.
          </section>
        ) : (
          <>
            <div className="desktop-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha y hora</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Acción</TableHead>
                    <TableHead>Resultado</TableHead>
                    <TableHead>Recurso</TableHead>
                    <TableHead>Origen</TableHead>
                    <TableHead>Detalles</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.items.map((item) => (
                    <EventRow
                      key={item.id}
                      event={item}
                      onSelect={() => setSelected(item)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="audit-cards">
              {result.items.map((item) => (
                <article className="member-card" key={item.id}>
                  <strong>{actionLabel(item.action)}</strong>
                  <span className="muted">
                    {dateLabel(item.occurred_at)} ·{" "}
                    {item.actor?.email ?? "Sistema"}
                  </span>
                  <Badge>{outcomes[item.outcome] ?? item.outcome}</Badge>
                  <span>
                    {item.resource ?? "—"} ·{" "}
                    {sources[item.source] ?? item.source}
                  </span>
                  <DetailsButton
                    event={item}
                    onClick={() => setSelected(item)}
                  />
                </article>
              ))}
            </div>
            <nav className="pagination" aria-label="Paginación de auditoría">
              <span>{result.total} eventos</span>
              <div className="pagination-page-size">
                <label htmlFor="audit-per-page">Filas por página</label>
                <select
                  id="audit-per-page"
                  value={result.per_page}
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
        ))
      )}
      <TooltipProvider>
        <DetailsDialog event={selected} onClose={() => setSelected(null)} />
      </TooltipProvider>
    </section>
  );
}
