export type Session = {
  user_id: string;
  tenant_id: string;
  tenant_name: string;
  role: "admin" | "member" | "viewer";
  capabilities: string[];
};

const baseUrl = import.meta.env.VITE_API_URL ?? "/api";
const csrf = () =>
  document.cookie
    .split("; ")
    .find((part) => part.startsWith("csrf_token="))
    ?.split("=")[1];

const legacyMessages: Record<string, string> = {
  "authentication required": "Se requiere autenticación.",
  "CSRF validation failed": "Falló la validación de seguridad de la solicitud.",
  "select a tenant first": "Primero seleccioná un espacio de trabajo.",
  "role is not permitted": "Tu rol no tiene permiso para realizar esta acción.",
  "email is already registered": "El correo electrónico ya está registrado.",
  "invalid credentials":
    "El correo electrónico o la contraseña no son válidos.",
  "an active tenant membership is required":
    "Se requiere una membresía activa en un espacio de trabajo.",
  "invalid or expired recovery token":
    "El código de recuperación no es válido o venció.",
  "role must be admin, member, or viewer":
    "El rol debe ser administración, integrante o consulta.",
  "user is already attached to another tenant":
    "La persona ya pertenece a otro espacio de trabajo.",
};

const statusMessages: Record<number, string> = {
  400: "La solicitud no es válida.",
  401: "Se requiere autenticación.",
  403: "No tenés permiso para realizar esta acción.",
  404: "No se encontró el recurso solicitado.",
  409: "No se pudo completar la solicitud por un conflicto.",
  422: "Los datos enviados no son válidos.",
  429: "Se realizaron demasiadas solicitudes. Intentá nuevamente más tarde.",
};

const genericMessage = "No se pudo completar la solicitud.";
const internalError = "Ocurrió un error interno. Intentá nuevamente más tarde.";

function statusMessage(status: number): string {
  return status >= 500
    ? internalError
    : (statusMessages[status] ?? genericMessage);
}

type ValidationIssue = { loc?: unknown; type?: unknown; msg?: unknown };

function validationMessage(issue: ValidationIssue): string {
  const location = Array.isArray(issue.loc) ? issue.loc : [];
  const field = location.at(-1);
  const type = typeof issue.type === "string" ? issue.type : "";
  if (type === "missing") return "Este campo es obligatorio.";
  if (field === "email") return "Ingresá un correo electrónico válido.";
  if (field === "password" || type === "string_too_short") {
    return "La contraseña debe tener al menos 8 caracteres.";
  }
  return "Los datos enviados no son válidos.";
}

export function apiErrorMessage(
  detail: unknown,
  fallback = genericMessage,
): string {
  if (typeof detail === "string") {
    if (legacyMessages[detail]) return legacyMessages[detail];
    if (
      detail.startsWith("Se ") ||
      detail.startsWith("Falló ") ||
      detail.startsWith("Primero ") ||
      detail.startsWith("Tu ") ||
      detail.startsWith("El ") ||
      detail.startsWith("La ") ||
      detail.startsWith("Los ") ||
      detail.startsWith("No ") ||
      detail.startsWith("Ocurrió ")
    )
      return detail;
    return fallback;
  }
  if (Array.isArray(detail)) {
    const issue = detail.find(
      (item): item is ValidationIssue =>
        typeof item === "object" && item !== null,
    );
    if (issue) return validationMessage(issue);
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = {};
  new Headers(init.headers).forEach((value, key) => {
    headers[key] = value;
  });
  if (init.body && !(init.body instanceof FormData))
    headers["content-type"] = "application/json";
  if (method !== "GET") headers["x-csrf-token"] = csrf() ?? "";

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new Error("La API no está disponible.");
  }

  if (!response.ok) {
    const fallback = statusMessage(response.status);
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      // Non-JSON error responses use only the trusted status fallback.
    }
    throw new Error(apiErrorMessage(detail, fallback));
  }
  return response.json() as Promise<T>;
}

export const getSession = () => request<Session>("/auth/session");
export const login = (email: string, password: string) =>
  request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
export const register = (
  email: string,
  password: string,
  tenant_name: string,
) =>
  request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, tenant_name }),
  });
export const requestRecovery = (email: string) =>
  request("/auth/recovery/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
export const confirmRecovery = (token: string, password: string) =>
  request("/auth/recovery/confirm", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
export const logout = () => request("/auth/logout", { method: "POST" });
export type MemberRole = "admin" | "member" | "viewer";
export type MemberStatus = "active" | "inactive";
export type Member = {
  user_id: string;
  email: string;
  role: MemberRole;
  status: MemberStatus;
  password_setup_required: boolean;
};
export type MembersQuery = {
  page: number;
  per_page: number;
  search: string;
  role: "" | MemberRole;
  status: "" | MemberStatus;
  sort: string;
};
export type MembersResponse = {
  items: Member[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};
export const getMembers = (query: MembersQuery) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    params.set(key, String(value));
  return request<MembersResponse>(`/members?${params.toString()}`);
};
export const createMember = (email: string, role: MemberRole) =>
  request("/members", {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
export type MemberUpdate = {
  role?: MemberRole;
  active?: boolean;
};
export type MemberUpdateResponse = {
  membership_id: string;
  user_id: string;
  role: MemberRole;
  active: boolean;
};
export const updateMember = (membershipId: string, payload: MemberUpdate) =>
  request<MemberUpdateResponse>(
    `/members/${encodeURIComponent(membershipId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );

export type AuditSource = "audit" | "experiment_status" | "ingestion";
export type AuditOutcome = "success" | "denied" | "failed" | "rate_limited";
export type AuditEvent = {
  id: string;
  occurred_at: string;
  actor: { user_id: string; email: string } | null;
  action: string;
  outcome: AuditOutcome | string;
  resource: string | null;
  detail: unknown;
  source: AuditSource;
};
export type AuditEventsQuery = {
  from: string;
  to: string;
  search: string;
  action: string;
  outcome: string;
  actor_id: string;
  page: number;
  per_page: number;
};
export type AuditEventsResponse = {
  items: AuditEvent[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};
export const getAuditEvents = (query: AuditEventsQuery) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== "") params.set(key, String(value));
  }
  return request<AuditEventsResponse>(`/audit-events?${params.toString()}`);
};

export type ExperimentStatus = "draft" | "running" | "completed" | "failed";
export type MetricType = "number" | "text" | "boolean" | "json";
export type Metric = {
  id: string;
  name: string;
  value_type: MetricType;
  number_value: number | null;
  text_value: string | null;
  boolean_value: boolean | null;
  json_value: unknown;
  unit: string | null;
  step: number | null;
  recorded_at: string;
  creator_id: string;
};
export type ExperimentResult = {
  id: string;
  status: "completed" | "failed";
  input_summary: string | null;
  output_summary: string | null;
  created_at: string;
  creator_id: string;
  metrics: Metric[];
  experiment?: Experiment;
};
export type Experiment = {
  id: string;
  name: string;
  status: ExperimentStatus;
  created_at: string;
  updated_at: string;
  creator_id: string;
  archived_at?: string | null;
  archived_by?: string | null;
  results?: ExperimentResult[];
};
export type ExperimentsResponse = {
  items: Experiment[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};
export type MetricInput = {
  name: string;
  type: MetricType;
  value: number | string | boolean | object;
  unit?: string;
  step?: number;
};
export type ExperimentsQuery = {
  page: number;
  per_page: number;
  search: string;
  status: "" | ExperimentStatus;
  archived: boolean;
  sort:
    | "created_at:desc"
    | "created_at:asc"
    | "name:asc"
    | "name:desc"
    | "result_count:desc";
};
export const getExperiments = (query: ExperimentsQuery) => {
  const params = new URLSearchParams({
    page: String(query.page),
    per_page: String(query.per_page),
    sort: query.sort,
  });
  const search = query.search.trim();
  const status = query.status.trim();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (query.archived) params.set("archived", "true");
  return request<ExperimentsResponse>(`/experiments?${params.toString()}`);
};

export type DashboardStatus = ExperimentStatus;
export type DashboardQuery = {
  from: string;
  to: string;
  search: string;
  status: "" | DashboardStatus;
  sort:
    | "created_at:desc"
    | "created_at:asc"
    | "name:asc"
    | "name:desc"
    | "result_count:desc";
  page: number;
  per_page: number;
};
export type DashboardResponse = {
  range: { from: string; to: string };
  kpis: { total: number; running: number; completed: number; results: number };
  daily: {
    date: string;
    experiments: number;
    results: number;
    metric_average: number | null;
  }[];
  statuses: { status: DashboardStatus; count: number }[];
  items: {
    id: string;
    name: string;
    status: DashboardStatus;
    created_at: string;
    result_count: number;
    latest_metric: number | null;
  }[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};
export const getDashboard = (query: DashboardQuery) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    params.set(key, String(value));
  return request<DashboardResponse>(`/dashboard?${params.toString()}`);
};
export const getExperiment = (id: string) =>
  request<Experiment>(`/experiments/${id}`);
export const createExperiment = (name: string) =>
  request<Experiment>("/experiments", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
export type ExperimentUpdate = {
  name?: string;
  status?: ExperimentStatus;
  archived?: boolean;
};
export const updateExperiment = (id: string, payload: ExperimentUpdate) =>
  request<Experiment>(`/experiments/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
export const appendExperimentResult = (
  id: string,
  payload: {
    status: "completed" | "failed";
    input_summary?: string;
    output_summary?: string;
    metrics: MetricInput[];
    terminal_status?: "completed" | "failed";
    transition_reason?: string;
  },
) =>
  request<ExperimentResult>(`/experiments/${id}/results`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";
export type DocumentsQuery = {
  page: number;
  per_page: number;
  search: string;
  status: "" | DocumentStatus;
  sort: "name:asc" | "name:desc" | "status:asc" | "status:desc";
};
export type DocumentsResponse = {
  items: Document[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};
export type Document = {
  id: string;
  name: string;
  content_type?: string;
  size_bytes?: number;
  ingestion_status: DocumentStatus;
};
export type DocumentDetail = Document & {
  active_chunk_count: number;
  latest_run: {
    status: DocumentStatus;
    chunk_count: number;
    created_at: string;
    error: string | null;
  } | null;
};
export type Citation = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  ordinal: number;
  content: string;
  distance?: number;
};
export const getDocuments = (query: DocumentsQuery) => {
  const params = new URLSearchParams({
    page: String(query.page),
    per_page: String(query.per_page),
    sort: query.sort,
  });
  const search = query.search.trim();
  const status = query.status.trim();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  return request<DocumentsResponse>(`/documents?${params.toString()}`);
};
export const getDocument = (id: string) =>
  request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`);
export const uploadDocument = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return request<Document>("/documents", { method: "POST", body });
};
export const ingestDocument = (id: string) =>
  request<Document & { chunk_count: number }>(`/documents/${id}/ingest`, {
    method: "POST",
  });
export const retrieveDocuments = (query: string, limit = 5) =>
  request<{ citations: Citation[] }>("/documents/retrieve", {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });
export const downloadDocument = async (id: string) => {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/documents/${id}/download`, {
      credentials: "include",
    });
  } catch {
    throw new Error("La API no está disponible.");
  }
  if (!response.ok) throw new Error(statusMessage(response.status));
  return response.blob();
};

export type AssistantMode = "document" | "relational" | "combined" | "auto";
export type AssistantRelationalValue = string | number | boolean | null;

export type AssistantResponse = {
  requested_mode: AssistantMode;
  resolved_mode: Exclude<AssistantMode, "auto">;
  status: "complete" | "partial";
  answer: string;
  citations: Citation[];
  relational: null | {
    rows: Record<string, AssistantRelationalValue>[];
    sql_provenance: { query: string; row_count: number };
  };
  unavailable: ("document" | "relational")[];
};
export const queryAssistant = (prompt: string, mode: AssistantMode) =>
  request<AssistantResponse>("/assistant/query", {
    method: "POST",
    body: JSON.stringify({ prompt, mode }),
  });

// --- Platform administration (isolated session/cookie surface) ---

const platformCsrf = () =>
  document.cookie
    .split("; ")
    .find((part) => part.startsWith("platform_csrf_token="))
    ?.split("=")[1];

async function platformRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = {};
  new Headers(init.headers).forEach((value, key) => {
    headers[key] = value;
  });
  if (init.body) headers["content-type"] = "application/json";
  if (method !== "GET") headers["x-csrf-token"] = platformCsrf() ?? "";

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new Error("La API no está disponible.");
  }

  if (!response.ok) {
    const fallback = statusMessage(response.status);
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      // Non-JSON error responses use only the trusted status fallback.
    }
    throw new Error(apiErrorMessage(detail, fallback));
  }
  return response.json() as Promise<T>;
}

export const platformLogin = (email: string, password: string) =>
  platformRequest<{ authenticated: boolean }>("/platform/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
export const platformLogout = () =>
  platformRequest<{ logged_out: boolean }>("/platform/logout", {
    method: "POST",
  });

export type PlatformSummary = {
  tenant_count: number;
  active_tenant_count: number;
  platform_admin_count: number;
  active_platform_admin_count: number;
  experiment_count: number;
  document_count: number;
};
export const getPlatformSummary = () =>
  platformRequest<PlatformSummary>("/platform/summary");

export type PlatformTenantOverviewItem = {
  tenant_id: string;
  tenant_name: string;
  created_at: string;
  active_member_count: number;
  experiment_count: number;
  document_count: number;
  last_activity_at: string | null;
};
export type PlatformTenantOverviewResponse = {
  items: PlatformTenantOverviewItem[];
  total: number;
  limit: number;
  offset: number;
};
export type PlatformTenantOverviewQuery = {
  search: string;
  limit: number;
  offset: number;
};
export const getPlatformTenantOverview = (
  query: PlatformTenantOverviewQuery,
) => {
  const params = new URLSearchParams({
    search: query.search,
    limit: String(query.limit),
    offset: String(query.offset),
  });
  return platformRequest<PlatformTenantOverviewResponse>(
    `/platform/tenant-overview?${params.toString()}`,
  );
};

export type PlatformTenantDetail = {
  tenant_id: string;
  tenant_name: string;
  created_at: string;
  active_member_count: number;
  experiment_draft_count: number;
  experiment_running_count: number;
  experiment_completed_count: number;
  experiment_failed_count: number;
  document_count: number;
  last_activity_at: string | null;
};
export const getPlatformTenantDetail = (tenantId: string) =>
  platformRequest<PlatformTenantDetail>(
    `/platform/tenant-overview/${encodeURIComponent(tenantId)}`,
  );
