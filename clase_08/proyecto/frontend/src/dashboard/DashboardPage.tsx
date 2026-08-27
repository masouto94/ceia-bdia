import { useEffect, useState } from "react";
import { format, subDays } from "date-fns";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Download,
  LayoutGrid,
  List,
  RefreshCw,
} from "lucide-react";
import * as api from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { collectDashboardExportRows } from "./dashboardExport";
import { DateRangePicker } from "./DateRangePicker";
import { validateCalendarDateRange } from "./calendarDateRange";

const today = () => format(new Date(), "yyyy-MM-dd");
const startFor = (days: number) =>
  format(subDays(new Date(), days - 1), "yyyy-MM-dd");
const pageSizes = [10, 20, 30, 40, 50];
const statusLabel: Record<api.DashboardStatus, string> = {
  draft: "Borrador",
  running: "En ejecución",
  completed: "Completado",
  failed: "Fallido",
};
const displayDate = (value: string) =>
  new Intl.DateTimeFormat("es-AR", { dateStyle: "medium" }).format(
    new Date(value),
  );

type Filters = api.DashboardQuery;
type ViewMode = "charts" | "table";
const initialFilters = (): Filters => ({
  from: startFor(30),
  to: today(),
  search: "",
  status: "",
  sort: "created_at:desc",
  page: 1,
  per_page: 10,
});

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function exportXlsx(result: api.DashboardResponse, query: Filters) {
  const rows = await collectDashboardExportRows(
    result,
    query,
    api.getDashboard,
  );
  const { default: ExcelJS } = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Panel");
  sheet.addRow([
    "Panel de experimentos",
    `${result.range.from} a ${result.range.to}`,
  ]);
  sheet.addRow([
    "Experimentos",
    result.kpis.total,
    "En ejecución",
    result.kpis.running,
    "Completados",
    result.kpis.completed,
    "Resultados",
    result.kpis.results,
  ]);
  sheet.addRow([]);
  sheet.addRow(["Nombre", "Estado", "Creado", "Resultados", "Última métrica"]);
  rows.forEach((row) => sheet.addRow(row));
  sheet.columns.forEach((column) => {
    column.width = 20;
  });
  const bytes = await workbook.xlsx.writeBuffer();
  download(
    new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
    `panel-${result.range.from}-${result.range.to}.xlsx`,
  );
}

async function exportPdf(result: api.DashboardResponse, query: Filters) {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const pdf = new jsPDF();
  pdf.text("Panel de experimentos", 14, 16);
  pdf.text(`${result.range.from} a ${result.range.to}`, 14, 24);
  const rows = await collectDashboardExportRows(
    result,
    query,
    api.getDashboard,
  );
  autoTable(pdf, {
    startY: 30,
    head: [["Nombre", "Estado", "Creado", "Resultados", "Última métrica"]],
    body: rows,
    foot: [
      [
        "KPIs",
        `Experimentos: ${result.kpis.total} · Resultados: ${result.kpis.results}`,
      ],
    ],
  });
  pdf.save(`panel-${result.range.from}-${result.range.to}.pdf`);
}

export function DashboardPage() {
  const [draftFilters, setDraftFilters] = useState<Filters>(initialFilters);
  const [query, setQuery] = useState<Filters>(draftFilters);
  const [result, setResult] = useState<api.DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rangeError, setRangeError] = useState("");
  const [reload, setReload] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("charts");
  useEffect(() => {
    let active = true;
    void Promise.resolve()
      .then(() => {
        if (active) {
          setLoading(true);
          setError("");
        }
        return api.getDashboard(query);
      })
      .then((next) => {
        if (active) setResult(next);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "No se pudo cargar el panel.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, reload]);
  const patchDraft = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setDraftFilters((current) => ({ ...current, [key]: value, page: 1 }));
  const applyFilters = () => setQuery({ ...draftFilters, page: 1 });
  const applyDateRange = ({ from, to }: Pick<Filters, "from" | "to">) => {
    const validation = validateCalendarDateRange(from, to, 366);
    if (!validation.valid) {
      setRangeError(
        validation.inclusiveDays < 1
          ? "La fecha final debe ser igual o posterior a la inicial."
          : "El período debe tener un máximo de 366 días inclusivos.",
      );
      return;
    }
    const next = { ...draftFilters, from, to, page: 1 };
    setRangeError("");
    setDraftFilters(next);
    setQuery(next);
  };
  const changePage = (page: number) =>
    setQuery((current) => ({ ...current, page }));
  const changePageSize = (per_page: number) => {
    setDraftFilters((current) => ({ ...current, per_page, page: 1 }));
    setQuery((current) => ({ ...current, per_page, page: 1 }));
  };
  const changeView = (nextView: ViewMode) => {
    setViewMode(nextView);
    setQuery((current) =>
      current.page === 1 ? current : { ...current, page: 1 },
    );
  };
  const exportQuery = { ...query, page: 1, per_page: 50 };

  return (
    <section className="dashboard-page">
      <div className="page-header">
        <div>
          <h1>Panel</h1>
          <p className="muted">
            El período actualiza indicadores y gráficos; búsqueda y estado
            filtran solo la tabla y sus exportaciones.
          </p>
        </div>
        {result && (
          <div className="dashboard-actions">
            <Button
              variant="outline"
              disabled={Boolean(rangeError)}
              onClick={() => void exportXlsx(result, exportQuery)}
            >
              <Download data-icon="inline-start" />
              Exportar XLSX
            </Button>
            <Button
              variant="outline"
              disabled={Boolean(rangeError)}
              onClick={() => void exportPdf(result, exportQuery)}
            >
              <Download data-icon="inline-start" />
              Exportar PDF
            </Button>
          </div>
        )}
      </div>
      <div
        role="group"
        aria-label="Vista del dashboard"
        className="dashboard-view-toggle"
      >
        <Button
          type="button"
          variant={viewMode === "charts" ? "default" : "outline"}
          aria-pressed={viewMode === "charts"}
          onClick={() => changeView("charts")}
        >
          <LayoutGrid data-icon="inline-start" />
          Gráficos
        </Button>
        <Button
          type="button"
          variant={viewMode === "table" ? "default" : "outline"}
          aria-pressed={viewMode === "table"}
          onClick={() => changeView("table")}
        >
          <List data-icon="inline-start" />
          Tabla
        </Button>
      </div>
      <form
        data-testid="dashboard-filters"
        className="dashboard-toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters();
        }}
      >
        <DateRangePicker
          range={{ from: query.from, to: query.to }}
          onApply={applyDateRange}
        />
        {rangeError && <p role="alert">{rangeError}</p>}
        <label className="dashboard-search">
          Buscar experimentos
          <input
            aria-label="Buscar experimentos"
            placeholder="Buscar experimentos"
            value={draftFilters.search}
            onChange={(event) => patchDraft("search", event.target.value)}
          />
        </label>
        <label>
          Estado
          <select
            value={draftFilters.status}
            onChange={(event) =>
              patchDraft("status", event.target.value as Filters["status"])
            }
          >
            <option value="">Todos</option>
            {Object.entries(statusLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ordenar
          <select
            value={draftFilters.sort}
            onChange={(event) =>
              patchDraft("sort", event.target.value as Filters["sort"])
            }
          >
            <option value="created_at:desc">Más recientes</option>
            <option value="created_at:asc">Más antiguos</option>
            <option value="name:asc">Nombre A-Z</option>
            <option value="result_count:desc">Más resultados</option>
          </select>
        </label>
        <Button type="submit">Aplicar filtros</Button>
      </form>
      {error ? (
        <section className="notice error" role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => setReload((value) => value + 1)}
          >
            <RefreshCw data-icon="inline-start" />
            Reintentar
          </Button>
        </section>
      ) : !result ? (
        <div aria-label="Cargando panel">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ) : (
        <>
          <div className="kpi-grid">
            {[
              ["Experimentos", result.kpis.total],
              ["En ejecución", result.kpis.running],
              ["Completados", result.kpis.completed],
              ["Resultados", result.kpis.results],
            ].map(([label, value]) => (
              <article className="kpi-card" key={String(label)}>
                <span className="muted">{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
          {viewMode === "charts" && (
            <div className="dashboard-charts">
              <article className="chart-card">
                <h2>Actividad diaria</h2>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={result.daily}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="experiments"
                      name="Experimentos"
                      stroke="var(--brand-accent)"
                    />
                    <Line
                      type="monotone"
                      dataKey="results"
                      name="Resultados"
                      stroke="var(--primary)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </article>
              <article className="chart-card">
                <h2>Estados</h2>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={result.statuses}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="status"
                      tickFormatter={(status: api.DashboardStatus) =>
                        statusLabel[status]
                      }
                    />
                    <YAxis />
                    <Tooltip
                      labelFormatter={(status) =>
                        statusLabel[status as api.DashboardStatus] ??
                        String(status)
                      }
                    />
                    <Bar
                      dataKey="count"
                      name="Cantidad"
                      fill="var(--brand-accent)"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </article>
            </div>
          )}
          {viewMode === "table" &&
            (loading ? (
              <div className="dashboard-loading">
                <Skeleton />
                <Skeleton />
              </div>
            ) : result.items.length ? (
              <>
                <div className="desktop-table">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Experimento</TableHead>
                        <TableHead>Estado</TableHead>
                        <TableHead>Creado</TableHead>
                        <TableHead>Resultados</TableHead>
                        <TableHead>Última métrica</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.items.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>{item.name}</TableCell>
                          <TableCell>
                            <Badge>{statusLabel[item.status]}</Badge>
                          </TableCell>
                          <TableCell>{displayDate(item.created_at)}</TableCell>
                          <TableCell>{item.result_count}</TableCell>
                          <TableCell>{item.latest_metric ?? "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <div className="dashboard-cards">
                  {result.items.map((item) => (
                    <article className="member-card" key={item.id}>
                      <strong>{item.name}</strong>
                      <Badge>{statusLabel[item.status]}</Badge>
                      <span className="muted">
                        {item.result_count} resultados ·{" "}
                        {item.latest_metric ?? "—"}
                      </span>
                    </article>
                  ))}
                </div>
                <nav className="pagination" aria-label="Paginación del panel">
                  <span>{result.total} experimentos</span>
                  <div className="pagination-page-size">
                    <label htmlFor="dashboard-per-page">Filas por página</label>
                    <select
                      id="dashboard-per-page"
                      value={query.per_page}
                      onChange={(event) =>
                        changePageSize(Number(event.target.value))
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
                      onClick={() => changePage(1)}
                    >
                      <ChevronsLeft />
                    </Button>
                    <Button
                      aria-label="Página anterior"
                      variant="outline"
                      disabled={result.page <= 1}
                      onClick={() => changePage(result.page - 1)}
                    >
                      <ChevronLeft />
                    </Button>
                    <Button
                      aria-label="Página siguiente"
                      variant="outline"
                      disabled={result.page >= result.pages}
                      onClick={() => changePage(result.page + 1)}
                    >
                      <ChevronRight />
                    </Button>
                    <Button
                      aria-label="Última página"
                      variant="outline"
                      disabled={result.page >= result.pages}
                      onClick={() => changePage(result.pages || 1)}
                    >
                      <ChevronsRight />
                    </Button>
                  </div>
                </nav>
              </>
            ) : (
              <section className="notice">
                No hay experimentos que coincidan con los filtros.
              </section>
            ))}
        </>
      )}
    </section>
  );
}
