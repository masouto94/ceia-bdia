import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PlatformApp } from "./PlatformApp";
import { ThemeProvider } from "../theme";
import {
  getPlatformSummary,
  getPlatformTenantOverview,
  getPlatformTenantDetail,
  platformLogin,
  platformLogout,
  type PlatformSummary,
  type PlatformTenantOverviewResponse,
} from "../api";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  getPlatformSummary: vi.fn(),
  getPlatformTenantOverview: vi.fn(),
  getPlatformTenantDetail: vi.fn(),
  platformLogin: vi.fn(),
  platformLogout: vi.fn(),
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
  vi.clearAllMocks();
});

// Mirrors the exact production mount point declared in App.tsx
// (`<Route path="/platform/*" element={<PlatformApp />} />`) so relative
// routes inside PlatformApp resolve against the same ancestor context.
const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <Routes>
          <Route path="/platform/*" element={<PlatformApp />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  );

const summary: PlatformSummary = {
  tenant_count: 4,
  active_tenant_count: 3,
  platform_admin_count: 2,
  active_platform_admin_count: 1,
  experiment_count: 42,
  document_count: 17,
};

const tenantOverview: PlatformTenantOverviewResponse = {
  items: [
    {
      tenant_id: "11111111-1111-1111-1111-111111111111",
      tenant_name: "Alpha",
      created_at: "2026-01-01T00:00:00Z",
      active_member_count: 3,
      experiment_count: 5,
      document_count: 2,
      last_activity_at: "2026-02-01T00:00:00Z",
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
};

describe("PlatformApp — access control", () => {
  it("shows a loading state before the session check resolves", async () => {
    vi.mocked(getPlatformSummary).mockReturnValueOnce(new Promise(() => {}));
    renderAt("/platform/summary");
    expect(screen.getByText(/cargando sesión de plataforma/i)).toBeInTheDocument();
  });

  it("redirects an anonymous visitor to the platform login screen", async () => {
    vi.mocked(getPlatformSummary).mockRejectedValueOnce(new Error("Platform access denied."));
    renderAt("/platform/summary");
    expect(await screen.findByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
    expect(
      screen.getByText(/acceso exclusivo para administradores de plataforma/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /volver al inicio/i }),
    ).toHaveAttribute("href", "http://localhost:4321");
  });

  it("shows a denial/error message instead of tenant data when the summary call fails after login", async () => {
    vi.mocked(getPlatformSummary).mockRejectedValueOnce(new Error("Platform access denied."));
    renderAt("/platform/tenants");
    expect(await screen.findByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
  });
});

describe("PlatformApp — authenticated navigation and content", () => {
  it("renders only platform navigation items, never tenant controls", async () => {
    vi.mocked(getPlatformSummary).mockResolvedValue(summary);
    renderAt("/platform/summary");
    expect(await screen.findByRole("heading", { name: "Resumen de plataforma" })).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: /navegación de plataforma/i });
    expect(nav).toHaveTextContent("Resumen");
    expect(nav).toHaveTextContent("Espacios");

    for (const tenantLabel of [
      "Personas",
      "Experimentos",
      "Documentos",
      "Asistente",
      "Auditoría",
    ]) {
      expect(nav).not.toHaveTextContent(tenantLabel);
    }
    expect(screen.queryByRole("button", { name: /subir documento/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /crear experimento/i })).not.toBeInTheDocument();
  });

  it("shows only the aggregate fields returned by the backend, with no fabricated fields", async () => {
    vi.mocked(getPlatformSummary).mockResolvedValue(summary);
    renderAt("/platform/summary");
    await screen.findByRole("heading", { name: "Resumen de plataforma" });

    expect(screen.getByText("Espacios de trabajo")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Espacios activos")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Administradores de plataforma")).toBeInTheDocument();
    expect(screen.getByText("Administradores activos")).toBeInTheDocument();
    expect(screen.getByText("Experimentos")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Documentos")).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument();
  });

  it("lists tenant aggregates only (no members/documents/content) and opens a bounded detail view", async () => {
    vi.mocked(getPlatformSummary).mockResolvedValue(summary);
    vi.mocked(getPlatformTenantOverview).mockResolvedValue(tenantOverview);
    vi.mocked(getPlatformTenantDetail).mockResolvedValue({
      tenant_id: tenantOverview.items[0].tenant_id,
      tenant_name: "Alpha",
      created_at: "2026-01-01T00:00:00Z",
      active_member_count: 3,
      experiment_draft_count: 1,
      experiment_running_count: 2,
      experiment_completed_count: 2,
      experiment_failed_count: 0,
      document_count: 2,
      last_activity_at: "2026-02-01T00:00:00Z",
    });
    renderAt("/platform/tenants");
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Miembros activos" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Alpha" }));
    expect(getPlatformTenantDetail).toHaveBeenCalledWith(tenantOverview.items[0].tenant_id);
    expect(await screen.findByText("Experimentos en curso")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alpha" })).toBeInTheDocument();
  });

  it("logs out through the CSRF-protected endpoint and returns to the login screen", async () => {
    vi.mocked(getPlatformSummary).mockResolvedValue(summary);
    vi.mocked(platformLogout).mockResolvedValueOnce({ logged_out: true });
    renderAt("/platform/summary");
    await screen.findByRole("heading", { name: "Resumen de plataforma" });

    fireEvent.click(screen.getByRole("button", { name: /cerrar sesión/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirmar" }));

    expect(platformLogout).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
  });

  it("submits login credentials through the isolated platform endpoint", async () => {
    vi.mocked(getPlatformSummary)
      .mockRejectedValueOnce(new Error("Platform access denied."))
      .mockResolvedValueOnce(summary);
    vi.mocked(platformLogin).mockResolvedValueOnce({ authenticated: true });
    renderAt("/platform/login");

    fireEvent.change(await screen.findByLabelText("Correo electrónico"), {
      target: { value: "admin@platform.local" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "super-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(platformLogin).toHaveBeenCalledWith("admin@platform.local", "super-secret");
    expect(await screen.findByRole("heading", { name: "Resumen de plataforma" })).toBeInTheDocument();
  });

  it("cross-links back to the tenant login screen from the platform login", async () => {
    vi.mocked(getPlatformSummary).mockRejectedValueOnce(new Error("Platform access denied."));
    renderAt("/platform/login");
    const tenantLink = await screen.findByRole("link", { name: /entrá acá/i });
    expect(tenantLink).toHaveAttribute("href", "/login");
  });
});
