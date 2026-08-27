import {
  type ChangeEvent,
  type FocusEvent,
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
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import {
  BookOpen,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  ShieldCheck,
  Users,
} from "lucide-react";
import * as api from "./api";
import type { Session } from "./api";
import { LANDING_URL } from "./config/publicUrls";
import { Button } from "./components/ui/button";
import { Field, FieldError, FieldGroup } from "./components/ui/field";
import { ConfirmDialog } from "./components/custom/ConfirmDialog";
import { PasswordInput } from "./components/custom/PasswordInput";
import { ThemeProvider, ThemeToggle } from "./theme";
import { UsersPage } from "./admin/UsersPage";
import { ExperimentsPage } from "./experiments/ExperimentsPage";
import { DocumentsPage } from "./documents/DocumentsPage";
import { AssistantPage } from "./assistant/AssistantPage";
import { DashboardPage } from "./dashboard/DashboardPage";
import { AuditPage } from "./audit/AuditPage";
import { PlatformApp } from "./platform/PlatformApp";

type Auth = {
  session: Session | null;
  checking: boolean;
  refresh: () => Promise<void>;
  end: () => Promise<void>;
};
const AuthContext = createContext<Auth | null>(null);
const useAuth = () => {
  const value = useContext(AuthContext);
  if (!value) throw new Error("Falta el proveedor de autenticación");
  return value;
};

function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const sessionRequest = useRef(0);
  const refresh = async () => {
    const request = ++sessionRequest.current;
    try {
      const nextSession = await api.getSession();
      if (request === sessionRequest.current) setSession(nextSession);
    } catch {
      if (request === sessionRequest.current) setSession(null);
    } finally {
      if (request === sessionRequest.current) setChecking(false);
    }
  };
  useEffect(() => {
    const request = ++sessionRequest.current;
    void api
      .getSession()
      .then((nextSession) => {
        if (request === sessionRequest.current) setSession(nextSession);
      })
      .catch(() => {
        if (request === sessionRequest.current) setSession(null);
      })
      .finally(() => {
        if (request === sessionRequest.current) setChecking(false);
      });
  }, []);
  const end = async () => {
    try {
      await api.logout();
    } finally {
      setSession(null);
    }
  };
  return (
    <AuthContext.Provider value={{ session, checking, refresh, end }}>
      {children}
    </AuthContext.Provider>
  );
}
function Protected({ children }: { children: ReactNode }) {
  const { session, checking } = useAuth();
  if (checking) return <p>Cargando sesión…</p>;
  return session ? <>{children}</> : <Navigate to="/login" replace />;
}
const items = [
  { to: "/dashboard", label: "Panel", icon: LayoutDashboard },
  { to: "/users", label: "Personas", icon: Users },
  { to: "/experiments", label: "Experimentos", icon: FlaskConical },
  { to: "/documents", label: "Documentos", icon: BookOpen },
  { to: "/assistant", label: "Asistente", icon: MessageSquare },
  { to: "/audit", label: "Auditoría", icon: ShieldCheck },
];
function MainLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const { session, end } = useAuth();
  const location = useLocation();
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <span className="brand">Espacio de experimentos</span>
        <nav className="menu" aria-label="Navegación principal">
          {items
            .filter(
              (item) =>
                (item.to !== "/users" ||
                  session?.capabilities.includes("members:manage")) &&
                (item.to !== "/audit" || session?.role === "admin"),
            )
            .map(({ to, label, icon: Icon }) => (
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
          <span className="muted">
            Espacio de trabajo: {session?.tenant_name}
          </span>
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
        title="¿Querés cerrar la sesión?"
        description="Vas a salir del espacio de trabajo actual."
        destructive
        onConfirm={end}
      />
    </div>
  );
}
type AuthMode = "login" | "register" | "request" | "confirm";
type AuthField =
  | "email"
  | "tenant"
  | "token"
  | "password"
  | "passwordConfirmation";
type AuthValues = Record<AuthField, string>;

const authFields: Record<AuthMode, AuthField[]> = {
  login: ["email", "password"],
  register: ["tenant", "email", "password", "passwordConfirmation"],
  request: ["email"],
  confirm: ["token", "password", "passwordConfirmation"],
};

function AuthPage({ mode }: { mode: AuthMode }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { session, refresh } = useAuth();
  const recoveryToken =
    mode === "confirm" ? (searchParams.get("token") ?? "") : "";
  const hasRecoveryToken = recoveryToken.length > 0;
  const [message, setMessage] = useState("");
  const [values, setValues] = useState<AuthValues>({
    email: "",
    tenant: "",
    token: recoveryToken,
    password: "",
    passwordConfirmation: "",
  });
  const [touched, setTouched] = useState<Partial<Record<AuthField, boolean>>>(
    {},
  );
  const [errors, setErrors] = useState<Partial<Record<AuthField, string>>>({});
  const validateField = (field: AuthField, candidate = values) => {
    const value = candidate[field].trim();
    if (field === "email") {
      if (!value) return "Ingresá tu correo electrónico.";
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
        ? undefined
        : "Ingresá un correo electrónico válido.";
    }
    if (field === "tenant")
      return value ? undefined : "Ingresá el nombre del equipo.";
    if (field === "token")
      return value ? undefined : "Ingresá el código de recuperación.";
    if (field === "password") {
      if (!value) return "Ingresá tu contraseña.";
      return mode === "login" || value.length >= 8
        ? undefined
        : "La contraseña debe tener al menos 8 caracteres.";
    }
    if (!value) {
      return mode === "confirm"
        ? "Repetí la nueva contraseña."
        : "Repetí la contraseña.";
    }
    return value === candidate.password
      ? undefined
      : "Las contraseñas no coinciden.";
  };
  const validateFields = (fields: AuthField[], candidate = values) =>
    fields.reduce<Partial<Record<AuthField, string>>>((next, field) => {
      const error = validateField(field, candidate);
      if (error) next[field] = error;
      return next;
    }, {});
  const setField = (field: AuthField, event: ChangeEvent<HTMLInputElement>) => {
    const nextValues = { ...values, [field]: event.target.value };
    setValues(nextValues);
    setErrors((current) => {
      const next = { ...current };
      if (touched[field]) next[field] = validateField(field, nextValues) ?? "";
      if (field === "password" && touched.passwordConfirmation) {
        next.passwordConfirmation =
          validateField("passwordConfirmation", nextValues) ?? "";
      }
      return next;
    });
  };
  const blurField = (field: AuthField, event: FocusEvent<HTMLInputElement>) => {
    if (
      event.currentTarget.parentElement?.contains(
        event.relatedTarget as Node | null,
      )
    )
      return;
    setTouched((current) => ({ ...current, [field]: true }));
    setErrors((current) => ({
      ...current,
      [field]: validateField(field) ?? "",
    }));
  };
  const inputProps = (field: AuthField) => {
    const error = errors[field];
    return {
      id: `${mode}-${field}`,
      value: values[field],
      onChange: (event: ChangeEvent<HTMLInputElement>) =>
        setField(field, event),
      onBlur: (event: FocusEvent<HTMLInputElement>) => blurField(field, event),
      "aria-invalid": error ? true : undefined,
      "aria-describedby": error ? `${mode}-${field}-error` : undefined,
    };
  };
  const fieldError = (field: AuthField) =>
    errors[field] ? (
      <FieldError id={`${mode}-${field}-error`}>{errors[field]}</FieldError>
    ) : null;
  if (session && mode !== "confirm") {
    return <Navigate to="/dashboard" replace />;
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fields =
      mode === "confirm" && hasRecoveryToken
        ? authFields[mode].filter((field) => field !== "token")
        : authFields[mode];
    const nextErrors = validateFields(fields);
    setTouched(Object.fromEntries(fields.map((field) => [field, true])));
    setErrors(nextErrors);
    const firstInvalid = fields.find((field) => nextErrors[field]);
    if (firstInvalid) {
      document.getElementById(`${mode}-${firstInvalid}`)?.focus();
      return;
    }
    setMessage("");
    const password = values.password;
    try {
      if (mode === "login") {
        await api.login(values.email, password);
        await refresh();
      }
      if (mode === "register") {
        await api.register(values.email, password, values.tenant);
        await refresh();
      }
      if (mode === "request") {
        await api.requestRecovery(values.email);
        setMessage(
          "Si la cuenta existe, se enviaron las instrucciones de recuperación.",
        );
      }
      if (mode === "confirm") {
        await api.confirmRecovery(
          hasRecoveryToken ? recoveryToken : values.token,
          password,
        );
        navigate("/login", { replace: true });
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "No se pudo completar la solicitud",
      );
    }
  };
  const title =
    mode === "login"
      ? "Ingresar"
      : mode === "register"
        ? "Crear espacio"
        : mode === "request"
          ? "Recuperar contraseña"
          : "Guardar contraseña";
  return (
    <div className="auth">
      <div className="auth-panel">
        <a href={LANDING_URL} className="muted">
          ← Volver al inicio
        </a>
        <form className="card" noValidate onSubmit={submit}>
          <div className="auth-heading">
            <p className="auth-brand">Espacio de Experimentos</p>
            <ThemeToggle />
          </div>
          <h1>{title}</h1>
          <p className="muted">Accedé al espacio de trabajo de tu equipo.</p>
          <FieldGroup>
            {mode === "confirm" && !hasRecoveryToken && (
              <Field data-invalid={errors.token ? true : undefined}>
                <label htmlFor={`${mode}-token`}>Código de recuperación</label>
                <input
                  {...inputProps("token")}
                  name="token"
                  placeholder="Pegá el código recibido por correo"
                  required
                />
                {fieldError("token")}
              </Field>
            )}
            {mode === "register" && (
              <Field data-invalid={errors.tenant ? true : undefined}>
                <label htmlFor={`${mode}-tenant`}>Nombre del equipo</label>
                <input
                  {...inputProps("tenant")}
                  name="tenant"
                  placeholder="Ej.: Laboratorio de datos"
                  required
                />
                {fieldError("tenant")}
              </Field>
            )}
            {mode !== "confirm" && (
              <Field data-invalid={errors.email ? true : undefined}>
                <label htmlFor={`${mode}-email`}>Correo electrónico</label>
                <input
                  {...inputProps("email")}
                  name="email"
                  type="email"
                  placeholder="nombre@equipo.edu"
                  required
                />
                {fieldError("email")}
              </Field>
            )}
            {mode !== "request" && (
              <Field data-invalid={errors.password ? true : undefined}>
                <label htmlFor={`${mode}-password`}>Contraseña</label>
                <PasswordInput
                  {...inputProps("password")}
                  name="password"
                  minLength={8}
                  placeholder={
                    mode === "login"
                      ? "Ingresá tu contraseña"
                      : "Mínimo 8 caracteres"
                  }
                  required
                />
                {fieldError("password")}
              </Field>
            )}
            {(mode === "register" || mode === "confirm") && (
              <Field
                data-invalid={errors.passwordConfirmation ? true : undefined}
              >
                <label htmlFor={`${mode}-passwordConfirmation`}>
                  Confirmar contraseña
                </label>
                <PasswordInput
                  {...inputProps("passwordConfirmation")}
                  name="passwordConfirmation"
                  minLength={8}
                  placeholder={
                    mode === "register"
                      ? "Repetí la contraseña"
                      : "Repetí la nueva contraseña"
                  }
                  required
                />
                {fieldError("passwordConfirmation")}
              </Field>
            )}
            <Button className="auth-submit" type="submit">
              {mode === "login"
                ? "Ingresar"
                : mode === "register"
                  ? "Crear espacio"
                  : mode === "request"
                    ? "Enviar instrucciones"
                    : "Guardar contraseña"}
            </Button>
            {message && (
              <p className="error" role="alert">
                {message}
              </p>
            )}
          </FieldGroup>
          <nav className="auth-links" aria-label="Opciones de acceso">
            <Link to="/login">Ingresar</Link>
            <Link to="/register">Crear una cuenta</Link>
            <Link to="/recovery">Recuperar contraseña</Link>
          </nav>
          {mode === "login" && (
            <p className="muted platform-cross-link">
              ¿Sos administrador de plataforma?{" "}
              <Link to="/platform">Entrá acá →</Link>
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
function UsersRoute() {
  const { session } = useAuth();
  return (
    <UsersPage
      canManage={session?.capabilities.includes("members:manage") ?? false}
      currentUserId={session?.user_id}
    />
  );
}
function AuditRoute() {
  const { session } = useAuth();
  return session?.role === "admin" ? (
    <AuditPage />
  ) : (
    <Navigate to="/dashboard" replace />
  );
}
function ExperimentsRoute() {
  const { session } = useAuth();
  return <ExperimentsPage canMutate={session?.role !== "viewer"} />;
}
function DocumentsRoute() {
  const { session } = useAuth();
  return <DocumentsPage canMutate={session?.role !== "viewer"} />;
}
function AppRoutes() {
  return (
    <Routes>
      <Route path="/platform/*" element={<PlatformApp />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/recovery" element={<AuthPage mode="request" />} />
      <Route path="/recovery/confirm" element={<AuthPage mode="confirm" />} />
      <Route path="/reset-password" element={<AuthPage mode="confirm" />} />
      <Route
        path="/*"
        element={
          <Protected>
            <MainLayout>
              <Routes>
                <Route
                  path="/"
                  element={<Navigate to="/dashboard" replace />}
                />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/users" element={<UsersRoute />} />
                <Route path="/experiments" element={<ExperimentsRoute />} />
                <Route path="/documents" element={<DocumentsRoute />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/audit" element={<AuditRoute />} />
                <Route
                  path="*"
                  element={<Navigate to="/dashboard" replace />}
                />
              </Routes>
            </MainLayout>
          </Protected>
        }
      />
    </Routes>
  );
}
export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ThemeProvider>
  );
}
