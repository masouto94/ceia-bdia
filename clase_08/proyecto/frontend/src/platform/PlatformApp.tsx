import {
  type FormEvent,
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import {
  Building2,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldOff,
} from "lucide-react";
import * as api from "../api";
import { LANDING_URL } from "../config/publicUrls";
import { Button } from "../components/ui/button";
import { Field, FieldGroup } from "../components/ui/field";
import { ConfirmDialog } from "../components/custom/ConfirmDialog";
import { PasswordInput } from "../components/custom/PasswordInput";
import { ThemeToggle } from "../theme";

// Isolated platform-administration surface. This module never imports tenant
// pages (documents/experiments/assistant/members) and never reads the tenant
// session cookie — it only talks to /api/platform/* through platformRequest.

type PlatformAuthStatus = "checking" | "authenticated" | "anonymous";
type PlatformAuth = {
  status: PlatformAuthStatus;
  summary: api.PlatformSummary | null;
  refresh: () => Promise<void>;
  end: () => Promise<void>;
};
const PlatformAuthContext = createContext<PlatformAuth | null>(null);
const usePlatformAuth = () => {
  const value = useContext(PlatformAuthContext);
  if (!value)
    throw new Error("Falta el proveedor de autenticación de plataforma");
  return value;
};

function PlatformAuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<PlatformAuthStatus>("checking");
  const [summary, setSummary] = useState<api.PlatformSummary | null>(null);
  const request = useRef(0);
  const refresh = async () => {
    const id = ++request.current;
    try {
      const nextSummary = await api.getPlatformSummary();
      if (id === request.current) {
        setSummary(nextSummary);
        setStatus("authenticated");
      }
    } catch {
      if (id === request.current) {
        setSummary(null);
        setStatus("anonymous");
      }
    }
  };
  useEffect(() => {
    const id = ++request.current;
    void api
      .getPlatformSummary()
      .then((nextSummary) => {
        if (id === request.current) {
          setSummary(nextSummary);
          setStatus("authenticated");
        }
      })
      .catch(() => {
        if (id === request.current) {
          setSummary(null);
          setStatus("anonymous");
        }
      });
  }, []);
  const end = async () => {
    try {
      await api.platformLogout();
    } finally {
      setSummary(null);
      setStatus("anonymous");
    }
  };
  return (
    <PlatformAuthContext.Provider value={{ status, summary, refresh, end }}>
      {children}
    </PlatformAuthContext.Provider>
  );
}

function PlatformProtected({ children }: { children: ReactNode }) {
  const { status } = usePlatformAuth();
  if (status === "checking")
    return <p>Cargando sesión de plataforma…</p>;
  if (status === "anonymous")
    return <Navigate to="/platform/login" replace />;
  return <>{children}</>;
}

const navItems = [
  { to: "/platform/summary", label: "Resumen", icon: LayoutDashboard },
  { to: "/platform/tenants", label: "Espacios", icon: Building2 },
];

function PlatformLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const { end } = usePlatformAuth();
  const location = useLocation();
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <span className="brand">Administración de plataforma</span>
        <nav className="menu" aria-label="Navegación de plataforma">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              aria-current={location.pathname === to ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              <Icon data-icon="inline-start" />
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="content">
        <header>
          <Button
            className="mobile-toggle"
            variant="ghost"
            aria-label="Abrir navegación"
            onClick={() => setOpen(!open)}
          >
            <Menu data-icon="inline-start" />
          </Button>
          <span className="muted">Vista de plataforma (solo lectura)</span>
          <div className="header-actions">
            <ThemeToggle />
            <Button variant="outline" onClick={() => setSignOutOpen(true)}>
              <LogOut data-icon="inline-start" />
              Cerrar sesión
            </Button>
          </div>
        </header>
        <main>{children}</main>
      </div>
      <ConfirmDialog
        open={signOutOpen}
        onOpenChange={setSignOutOpen}
        title="¿Querés cerrar la sesión de plataforma?"
        description="Vas a salir de la administración de plataforma."
        destructive
        onConfirm={end}
      />
    </div>
  );
}

function PlatformLoginPage() {
  const { status, refresh } = usePlatformAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  if (status === "authenticated")
    return <Navigate to="/platform/summary" replace />;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api.platformLogin(email, password);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo iniciar sesión de plataforma.",
      );
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <div className="auth">
      <div className="auth-panel">
        <a href={LANDING_URL} className="muted">
          ← Volver al inicio
        </a>
        <form className="card" noValidate onSubmit={submit}>
          <div className="auth-heading">
            <p className="auth-brand">Administración de plataforma</p>
            <ThemeToggle />
          </div>
          <h1>Ingresar</h1>
          <p className="muted">
            Acceso exclusivo para administradores de plataforma.
          </p>
          <FieldGroup>
            <Field>
              <label htmlFor="platform-email">Correo electrónico</label>
              <input
                id="platform-email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field>
              <label htmlFor="platform-password">Contraseña</label>
              <PasswordInput
                id="platform-password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            <Button className="auth-submit" type="submit" disabled={submitting}>
              {submitting ? "Ingresando…" : "Ingresar"}
            </Button>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
          </FieldGroup>
          <p className="muted platform-cross-link">
            ¿Sos usuario de un espacio de trabajo?{" "}
            <Link to="/login">Entrá acá →</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

function PlatformDeniedNotice({ message }: { message: string }) {
  return (
    <div className="notice">
      <p className="error" role="alert">
        <ShieldOff data-icon="inline-start" aria-hidden="true" /> {message}
      </p>
    </div>
  );
}

const summaryTiles: { key: keyof api.PlatformSummary; label: string }[] = [
  { key: "tenant_count", label: "Espacios de trabajo" },
  { key: "active_tenant_count", label: "Espacios activos" },
  { key: "platform_admin_count", label: "Administradores de plataforma" },
  { key: "active_platform_admin_count", label: "Administradores activos" },
  { key: "experiment_count", label: "Experimentos" },
  { key: "document_count", label: "Documentos" },
];

function PlatformSummaryPage() {
  const { summary, status } = usePlatformAuth();
  if (status === "checking") return <p>Cargando resumen…</p>;
  if (status === "anonymous")
    return (
      <PlatformDeniedNotice message="No tenés acceso a la administración de plataforma." />
    );
  if (!summary)
    return (
      <p className="error" role="alert">
        No se pudo cargar el resumen de plataforma.
      </p>
    );
  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>Resumen de plataforma</h1>
      </div>
      <div className="kpi-grid">
        {summaryTiles.map((tile) => (
          <div className="kpi-card" key={tile.key}>
            <span className="muted">{tile.label}</span>
            <strong>{summary[tile.key]}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlatformTenantsPage() {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<api.PlatformTenantOverviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const limit = 20;
  useEffect(() => {
    let active = true;
    api
      .getPlatformTenantOverview({ search, limit, offset })
      .then((response) => {
        if (!active) return;
        setItems(response.items);
        setTotal(response.total);
        setError("");
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(
          err instanceof Error
            ? err.message
            : "No se pudo cargar la lista de espacios.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [search, offset]);
  const updateSearch = (value: string) => {
    setLoading(true);
    setSearch(value);
    setOffset(0);
  };
  const updateOffset = (value: number) => {
    setLoading(true);
    setOffset(value);
  };
  return (
    <div className="users-directory">
      <div className="page-header">
        <h1>Espacios de trabajo</h1>
      </div>
      <div className="directory-toolbar">
        <div className="search-field">
          <input
            aria-label="Buscar espacio de trabajo"
            placeholder="Buscar por nombre…"
            value={search}
            onChange={(event) => updateSearch(event.target.value)}
          />
        </div>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p>Cargando espacios…</p>
      ) : items.length === 0 ? (
        <p className="muted">No se encontraron espacios de trabajo.</p>
      ) : (
        <div className="desktop-table">
          <table>
            <thead>
              <tr>
                <th>Espacio</th>
                <th>Miembros activos</th>
                <th>Experimentos</th>
                <th>Documentos</th>
                <th>Última actividad</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.tenant_id}>
                  <td>
                    <Link to={`/platform/tenants/${item.tenant_id}`}>
                      {item.tenant_name}
                    </Link>
                  </td>
                  <td>{item.active_member_count}</td>
                  <td>{item.experiment_count}</td>
                  <td>{item.document_count}</td>
                  <td>{item.last_activity_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>
          {total === 0
            ? "0 resultados"
            : `${offset + 1}–${Math.min(offset + limit, total)} de ${total}`}
        </span>
        <div>
          <Button
            variant="outline"
            disabled={offset === 0}
            onClick={() => updateOffset(Math.max(0, offset - limit))}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            disabled={offset + limit >= total}
            onClick={() => updateOffset(offset + limit)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </div>
  );
}

const detailTiles: { key: keyof api.PlatformTenantDetail; label: string }[] = [
  { key: "active_member_count", label: "Miembros activos" },
  { key: "experiment_draft_count", label: "Experimentos en borrador" },
  { key: "experiment_running_count", label: "Experimentos en curso" },
  { key: "experiment_completed_count", label: "Experimentos completados" },
  { key: "experiment_failed_count", label: "Experimentos fallidos" },
  { key: "document_count", label: "Documentos" },
];

function PlatformTenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const [detail, setDetail] = useState<api.PlatformTenantDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!tenantId) return;
    let active = true;
    api
      .getPlatformTenantDetail(tenantId)
      .then((response) => {
        if (active) {
          setDetail(response);
          setError("");
        }
      })
      .catch((err: unknown) => {
        if (active)
          setError(
            err instanceof Error
              ? err.message
              : "No se pudo cargar el detalle del espacio.",
          );
      });
    return () => {
      active = false;
    };
  }, [tenantId]);
  // Derived (not stored) so a param change between two tenant ids shows a
  // loading state again without a synchronous setState inside the effect.
  const loading = !error && (!detail || detail.tenant_id !== tenantId);
  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>{detail?.tenant_name ?? "Detalle del espacio"}</h1>
        <Link to="/platform/tenants">Volver a espacios</Link>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p>Cargando detalle…</p>
      ) : detail ? (
        <div className="kpi-grid">
          {detailTiles.map((tile) => (
            <div className="kpi-card" key={tile.key}>
              <span className="muted">{tile.label}</span>
              <strong>{detail[tile.key]}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PlatformRoutes() {
  return (
    <Routes>
      <Route path="login" element={<PlatformLoginPage />} />
      <Route
        path="*"
        element={
          <PlatformProtected>
            <PlatformLayout>
              <Routes>
                <Route path="/" element={<Navigate to="/platform/summary" replace />} />
                <Route path="summary" element={<PlatformSummaryPage />} />
                <Route path="tenants" element={<PlatformTenantsPage />} />
                <Route
                  path="tenants/:tenantId"
                  element={<PlatformTenantDetailPage />}
                />
                <Route
                  path="*"
                  element={<Navigate to="/platform/summary" replace />}
                />
              </Routes>
            </PlatformLayout>
          </PlatformProtected>
        }
      />
    </Routes>
  );
}

export function PlatformApp() {
  return (
    <PlatformAuthProvider>
      <PlatformRoutes />
    </PlatformAuthProvider>
  );
}
