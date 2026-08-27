import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import * as apiClient from "./api";
import {
  confirmRecovery,
  getSession,
  login,
  logout,
  register,
  type Session,
  apiErrorMessage,
  getPlatformSummary,
} from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  getSession: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  requestRecovery: vi.fn(),
  confirmRecovery: vi.fn(),
  logout: vi.fn(),
  createMember: vi.fn(),
  getMembers: vi.fn(),
  updateMember: vi.fn(),
  getAuditEvents: vi.fn(),
  getPlatformSummary: vi.fn(),
}));
afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
  vi.clearAllMocks();
});
const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
};
const adminSession: Session = {
  user_id: "admin",
  tenant_id: "a548e27f-0606-4e86-9cf8-bc8af0e2159d",
  tenant_name: "Laboratorio de datos",
  role: "admin",
  capabilities: ["members:manage"],
};

describe("application routes", () => {
  it("redirects anonymous users from protected routes to login", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/dashboard");
    expect(
      await screen.findByRole("heading", { name: /ingresar/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /volver al inicio/i }),
    ).toHaveAttribute("href", "http://localhost:4321");
  });

  it("keeps a newly registered administrator on the protected dashboard after the session commits", async () => {
    const initialSession = deferred<Session>();
    vi.mocked(getSession)
      .mockReturnValueOnce(initialSession.promise)
      .mockResolvedValueOnce(adminSession);
    vi.mocked(register).mockResolvedValueOnce(undefined);
    renderAt("/register");

    fireEvent.change(await screen.findByLabelText("Nombre del equipo"), {
      target: { value: "Laboratorio" },
    });
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "admin@equipo.edu" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear espacio" }));

    expect(
      await screen.findByRole("heading", { name: "Panel" }),
    ).toBeInTheDocument();
    await act(async () => {
      initialSession.reject(new Error("unauthenticated"));
      await initialSession.promise.catch(() => undefined);
    });
    expect(screen.getByRole("heading", { name: "Panel" })).toBeInTheDocument();
  });

  it("blocks registration with mismatched passwords and sends only the existing API arguments when they match", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/register");

    fireEvent.change(await screen.findByLabelText("Nombre del equipo"), {
      target: { value: "Laboratorio" },
    });
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "admin@equipo.edu" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "otra-contraseña" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear espacio" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Las contraseñas no coinciden.",
    );
    expect(register).not.toHaveBeenCalled();

    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(register).mockResolvedValueOnce(undefined);
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear espacio" }));

    expect(register).toHaveBeenCalledWith(
      "admin@equipo.edu",
      "contraseña-segura",
      "Laboratorio",
    );
  });

  it("uses the recovery link token without rendering the manual code input", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    vi.mocked(confirmRecovery).mockResolvedValueOnce(undefined);
    renderAt("/reset-password?token=opaque-token");

    expect(
      await screen.findByRole("heading", { name: "Guardar contraseña" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Código de recuperación"),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));

    expect(confirmRecovery).toHaveBeenCalledTimes(1);
    expect(confirmRecovery).toHaveBeenCalledWith(
      "opaque-token",
      "contraseña-segura",
    );
    expect(
      await screen.findByRole("heading", { name: "Ingresar" }),
    ).toBeInTheDocument();
  });

  it.each(["/reset-password", "/reset-password?token="])(
    "keeps %s on the confirmation form with a manual code fallback",
    async (path) => {
      vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
      renderAt(path);

      expect(
        await screen.findByRole("heading", { name: "Guardar contraseña" }),
      ).toBeInTheDocument();
      expect(
        screen.getByLabelText("Código de recuperación"),
      ).toBeInTheDocument();
    },
  );

  it("keeps an invalid linked-token API error on the confirmation form in Spanish", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    vi.mocked(confirmRecovery).mockRejectedValueOnce(
      new Error("El enlace de recuperación no es válido o venció."),
    );
    renderAt("/reset-password?token=opaque-token");

    fireEvent.change(await screen.findByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El enlace de recuperación no es válido o venció.",
    );
    expect(
      screen.getByRole("heading", { name: "Guardar contraseña" }),
    ).toBeInTheDocument();
  });

  it("keeps the manual recovery confirmation route and validation fallback", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/recovery/confirm");

    fireEvent.change(await screen.findByLabelText("Código de recuperación"), {
      target: { value: "token" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "otra-contraseña" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Las contraseñas no coinciden.",
    );
    expect(confirmRecovery).not.toHaveBeenCalled();

    vi.mocked(confirmRecovery).mockResolvedValueOnce(undefined);
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));

    expect(confirmRecovery).toHaveBeenCalledWith("token", "contraseña-segura");
  });

  it("keeps sign-out pending behind an accessible confirmation dialog", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    const pendingLogout = deferred<void>();
    vi.mocked(logout).mockReturnValueOnce(pendingLogout.promise);
    renderAt("/dashboard");

    fireEvent.click(
      await screen.findByRole("button", { name: "Cerrar sesión" }),
    );
    expect(
      screen.getByRole("alertdialog", { name: "¿Querés cerrar la sesión?" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(logout).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    const confirm = screen.getByRole("button", { name: "Confirmar" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    expect(logout).toHaveBeenCalledTimes(1);
    expect(confirm).toBeDisabled();
    await act(async () => pendingLogout.resolve());
  });

  it("keeps a newly logged-in administrator on the protected dashboard after the session commits", async () => {
    const initialSession = deferred<Session>();
    vi.mocked(getSession)
      .mockReturnValueOnce(initialSession.promise)
      .mockResolvedValueOnce(adminSession);
    vi.mocked(login).mockResolvedValueOnce(undefined);
    renderAt("/login");

    fireEvent.change(await screen.findByLabelText("Correo electrónico"), {
      target: { value: "admin@equipo.edu" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-segura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(
      await screen.findByRole("heading", { name: "Panel" }),
    ).toBeInTheDocument();
    await act(async () => {
      initialSession.reject(new Error("unauthenticated"));
      await initialSession.promise.catch(() => undefined);
    });
    expect(screen.getByRole("heading", { name: "Panel" })).toBeInTheDocument();
  });

  it.each(["/login", "/register", "/recovery"])(
    "redirects authenticated users from %s to the dashboard",
    async (path) => {
      vi.mocked(getSession).mockResolvedValueOnce(adminSession);
      renderAt(path);
      expect(
        await screen.findByRole("heading", { name: "Panel" }),
      ).toBeInTheDocument();
    },
  );

  it("keeps recovery confirmation available to authenticated users", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    renderAt("/recovery/confirm");
    expect(
      await screen.findByRole("heading", { name: "Guardar contraseña" }),
    ).toBeInTheDocument();
  });

  it("shows the generic menu and viewer read-only member controls", async () => {
    vi.mocked(getSession).mockResolvedValueOnce({
      user_id: "user",
      tenant_id: "tenant",
      tenant_name: "Laboratorio de consulta",
      role: "viewer",
      capabilities: [],
    });

    vi.mocked(apiClient.getMembers).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      per_page: 10,
      pages: 1,
    });
    renderAt("/users");
    expect(
      await screen.findByText("No hay personas que coincidan con los filtros."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /agregar persona/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Experimentos" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Personas" }),
    ).not.toBeInTheDocument();
  });

  it("shows the audit route and navigation only to administrators", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(apiClient.getMembers).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      per_page: 50,
      pages: 1,
    });
    vi.mocked(apiClient.getAuditEvents).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      per_page: 25,
      pages: 1,
    });
    renderAt("/audit");
    expect(
      await screen.findByRole("heading", { name: "Auditoría" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Auditoría" })).toBeInTheDocument();

    cleanup();
    vi.mocked(getSession).mockResolvedValueOnce({
      ...adminSession,
      role: "member",
      capabilities: [],
    });
    renderAt("/audit");
    expect(
      await screen.findByRole("heading", { name: "Panel" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Auditoría" }),
    ).not.toBeInTheDocument();
  });
});

describe("users directory", () => {
  const membersResponse = {
    items: [
      {
        user_id: "member-1",
        email: "ana@equipo.edu",
        role: "member" as const,
        status: "active" as const,
        password_setup_required: true,
      },
    ],
    total: 1,
    page: 2,
    per_page: 20,
    pages: 3,
  };

  it("serializes the members directory query and renders its responsive directory labels", async () => {
    const getMembers = vi.mocked(apiClient.getMembers);
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    getMembers.mockResolvedValueOnce(membersResponse);
    const { container } = renderAt(
      "/users?page=2&per_page=20&search=ana%40equipo.edu&role=member&status=active&sort=email%3Adesc",
    );
    await screen.findAllByText("ana@equipo.edu");
    expect(getMembers).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
        per_page: 20,
        search: "ana@equipo.edu",
        role: "member",
        status: "active",
        sort: "email:desc",
      }),
    );
    expect(
      (await screen.findAllByText("ana@equipo.edu")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Integrante").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Activo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Contraseña pendiente").length).toBeGreaterThan(
      0,
    );
    expect(container.querySelector("table")).toBeInTheDocument();
    expect(container.querySelector(".member-cards")).toBeInTheDocument();
    expect(
      container.querySelector(".pagination-page-size > label + select"),
    ).toBeInTheDocument();
  });

  it("uses URL filters, opens details, handles loading/error/retry, and creates a valid member", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    const pending = deferred<typeof membersResponse>();
    vi.mocked(
      (apiClient as typeof apiClient & { getMembers: typeof pending.promise })
        .getMembers,
    ).mockReturnValueOnce(pending.promise);
    renderAt("/users?page=3&search=ana");
    expect(await screen.findByText(/cargando personas/i)).toBeInTheDocument();
    await act(async () => pending.reject(new Error("Sin conexión")));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin conexión");
    vi.mocked(apiClient.getMembers).mockResolvedValueOnce(membersResponse);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(
      (await screen.findAllByText("ana@equipo.edu")).length,
    ).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole("button", { name: "Ver detalles" })[0]);
    expect(
      screen.getByRole("dialog", { name: "Detalles de la persona" }),
    ).toHaveTextContent("Contraseña pendiente");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    fireEvent.click(screen.getByRole("button", { name: "Nuevo" }));
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "invalido" },
    });
    fireEvent.blur(screen.getByLabelText("Correo electrónico"));
    expect(
      screen.getByText("Ingresá un correo electrónico válido."),
    ).toBeInTheDocument();
    expect(apiClient.createMember).not.toHaveBeenCalled();
    vi.mocked(apiClient.createMember).mockResolvedValueOnce(undefined);
    vi.mocked(apiClient.getMembers).mockResolvedValueOnce(membersResponse);
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "bea@equipo.edu" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agregar persona" }));
    expect(apiClient.createMember).toHaveBeenCalledWith(
      "bea@equipo.edu",
      "viewer",
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Podrá establecer su contraseña desde recuperación.",
    );
  });

  it("disables self-deactivation", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(apiClient.getMembers).mockResolvedValueOnce({
      ...membersResponse,
      items: [
        {
          ...membersResponse.items[0],
          user_id: adminSession.user_id,
        },
      ],
    });
    renderAt("/users");

    const deactivateButtons = await screen.findAllByRole("button", {
      name: "Desactivar a ana@equipo.edu",
    });
    expect(deactivateButtons).toHaveLength(2);
    deactivateButtons.forEach((button) => expect(button).toBeDisabled());
  });

  it("uses an ordered, spaced role-edit footer and protects role updates", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(apiClient.getMembers)
      .mockResolvedValueOnce(membersResponse)
      .mockResolvedValueOnce({
        ...membersResponse,
        items: [{ ...membersResponse.items[0], role: "viewer" }],
      });
    vi.mocked(apiClient.updateMember).mockResolvedValueOnce({
      membership_id: "member-1",
      user_id: "member-1",
      role: "viewer",
      active: true,
    });
    renderAt("/users?page=2&per_page=20");

    fireEvent.click(
      (
        await screen.findAllByRole("button", {
          name: "Editar rol de ana@equipo.edu",
        })
      )[0],
    );
    const dialog = screen.getByRole("dialog", { name: "Editar rol" });
    const footer = dialog.querySelector(".dialog-footer");
    expect(footer).toHaveClass("dialog-footer");
    expect(
      Array.from(footer?.querySelectorAll("button") ?? []).map(
        (button) => button.textContent,
      ),
    ).toEqual(["Cancelar", "Guardar cambios"]);
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveClass(
      "button-outline",
    );
    expect(screen.getByRole("button", { name: "Guardar cambios" })).toHaveClass(
      "button-primary",
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(
      screen.queryByRole("dialog", { name: "Editar rol" }),
    ).not.toBeInTheDocument();
    expect(apiClient.updateMember).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getAllByRole("button", {
        name: "Editar rol de ana@equipo.edu",
      })[0],
    );
    fireEvent.change(screen.getByLabelText("Rol"), {
      target: { value: "viewer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(apiClient.updateMember).toHaveBeenCalledWith("member-1", {
      role: "viewer",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "El rol fue actualizado.",
    );
  });

  it("confirms destructive deactivation and non-destructive reactivation before one guarded mutation", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(apiClient.getMembers)
      .mockResolvedValueOnce(membersResponse)
      .mockResolvedValueOnce({
        ...membersResponse,
        items: [{ ...membersResponse.items[0], status: "inactive" }],
      });
    vi.mocked(apiClient.updateMember)
      .mockRejectedValueOnce(
        new Error("El espacio debe conservar una administración."),
      )
      .mockResolvedValueOnce({
        membership_id: "member-1",
        user_id: "member-1",
        role: "member",
        active: true,
      });
    renderAt("/users");

    fireEvent.click(
      (
        await screen.findAllByRole("button", {
          name: "Desactivar a ana@equipo.edu",
        })
      )[0],
    );
    const deactivateDialog = screen.getByRole("alertdialog", {
      name: "¿Querés desactivar a ana@equipo.edu?",
    });
    expect(deactivateDialog).toHaveTextContent(
      "ana@equipo.edu dejará de tener acceso",
    );
    expect(screen.getByRole("button", { name: "Desactivar" })).toHaveClass(
      "button-destructive",
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(apiClient.updateMember).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Desactivar a ana@equipo.edu" })[0],
    );
    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El espacio debe conservar una administración.",
    );

    fireEvent.click(
      screen.getAllByRole("button", { name: "Desactivar a ana@equipo.edu" })[0],
    );
    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));
    const reactivate = (
      await screen.findAllByRole("button", {
        name: "Reactivar a ana@equipo.edu",
      })
    )[0];
    fireEvent.click(reactivate);
    const reactivateDialog = screen.getByRole("alertdialog", {
      name: "¿Querés reactivar a ana@equipo.edu?",
    });
    expect(reactivateDialog).toHaveTextContent(
      "ana@equipo.edu recuperará el acceso",
    );
    expect(screen.getByRole("button", { name: "Reactivar" })).toHaveClass(
      "button-primary",
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(apiClient.updateMember).toHaveBeenCalledTimes(2);

    fireEvent.click(
      screen.getAllByRole("button", { name: "Reactivar a ana@equipo.edu" })[0],
    );
    const confirm = screen.getByRole("button", { name: "Reactivar" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    expect(apiClient.updateMember).toHaveBeenLastCalledWith("member-1", {
      active: true,
    });
    expect(apiClient.updateMember).toHaveBeenCalledTimes(3);
  });
});

describe("auth presentation and theme", () => {
  it("normalizes structured invalid-email responses into a useful Spanish message", () => {
    expect(
      apiErrorMessage([
        {
          type: "value_error",
          loc: ["body", "email"],
          msg: "value is not a valid email address",
        },
      ]),
    ).toBe("Ingresá un correo electrónico válido.");
  });

  it("shows the workspace name instead of its tenant UUID in the header", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    renderAt("/dashboard");
    expect(
      await screen.findByText("Espacio de trabajo: Laboratorio de datos"),
    ).toBeInTheDocument();
    expect(screen.queryByText(adminSession.tenant_id)).not.toBeInTheDocument();
  });

  it.each([
    ["/login", "nombre@equipo.edu", "Ingresá tu contraseña", "Ingresar"],
    ["/register", "nombre@equipo.edu", "Mínimo 8 caracteres", "Crear espacio"],
    ["/recovery", "nombre@equipo.edu", null, "Enviar instrucciones"],
    ["/recovery/confirm", null, "Mínimo 8 caracteres", "Guardar contraseña"],
  ])(
    "uses the required %s labels and placeholders",
    async (path, email, password, submit) => {
      vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
      renderAt(path);
      if (email)
        expect(await screen.findByPlaceholderText(email)).toBeInTheDocument();
      if (password)
        expect(screen.getByPlaceholderText(password)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: submit })).toBeInTheDocument();
    },
  );

  it("toggles each password field visibility independently and restores its masked type", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/register");

    const password = await screen.findByLabelText("Contraseña");
    const confirmation = screen.getByLabelText("Confirmar contraseña");
    expect(password).toHaveAttribute("type", "password");
    expect(confirmation).toHaveAttribute("type", "password");

    fireEvent.click(
      screen.getAllByRole("button", { name: "Mostrar contraseña" })[0],
    );
    expect(password).toHaveAttribute("type", "text");
    expect(confirmation).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Ocultar contraseña" }));
    expect(password).toHaveAttribute("type", "password");
  });

  it("uses workspace terminology, distributed auth links, and a non-pill login action", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    const { container } = renderAt("/login");
    expect(
      await screen.findByText(/Espacio de Experimentos/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ingresar" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Crear una cuenta" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Recuperar contraseña" }),
    ).toBeInTheDocument();
    expect(container.querySelector(".auth-links")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ingresar" })).toHaveClass(
      "auth-submit",
    );
  });

  it("renders the three access options as one labeled navigation group", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/login");
    const options = await screen.findByRole("navigation", {
      name: "Opciones de acceso",
    });
    expect(options.querySelectorAll("a")).toHaveLength(3);
  });

  it("cross-links to the isolated platform login only from the tenant login screen", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/login");
    const platformLink = await screen.findByRole("link", {
      name: /entrá acá/i,
    });
    expect(platformLink).toHaveAttribute("href", "/platform");
    // Outside the "Opciones de acceso" nav — it must not inflate that group's link count.
    expect(
      screen.getByRole("navigation", { name: "Opciones de acceso" }),
    ).not.toContainElement(platformLink);

    cleanup();
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt("/register");
    await screen.findByRole("heading", { name: "Crear espacio" });
    expect(
      screen.queryByRole("link", { name: /entrá acá/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the accessible theme toggle in the authenticated header", async () => {
    vi.mocked(getSession).mockResolvedValueOnce({
      user_id: "user",
      tenant_id: "tenant",
      tenant_name: "Laboratorio de consulta",
      role: "viewer",
      capabilities: [],
    });

    renderAt("/dashboard");
    expect(
      await screen.findByRole("button", { name: /activar tema oscuro/i }),
    ).toBeInTheDocument();
  });

  it("initializes from system preference and persists an accessible theme toggle", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    renderAt("/login");
    const toggle = await screen.findByRole("button", {
      name: /activar tema claro/i,
    });
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(toggle);
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(localStorage.getItem("student-project-theme")).toBe("light");
    expect(
      screen.getByRole("button", { name: /activar tema oscuro/i }),
    ).toHaveAttribute("aria-pressed", "false");
  });
});

describe("auth field-local validation", () => {
  const renderAnonymous = async (path: string) => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    renderAt(path);
    await screen.findByRole("heading");
  };

  it("shows the email error only after blur directly below the field and clears it on correction", async () => {
    await renderAnonymous("/login");
    const email = screen.getByLabelText("Correo electrónico");
    expect(
      screen.queryByText("Ingresá tu correo electrónico."),
    ).not.toBeInTheDocument();
    fireEvent.blur(email);
    const error = screen.getByText("Ingresá tu correo electrónico.");
    expect(email.nextElementSibling).toBe(error);
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAttribute("aria-describedby", "login-email-error");
    fireEvent.change(email, { target: { value: "ana@equipo.edu" } });
    expect(
      screen.queryByText("Ingresá tu correo electrónico."),
    ).not.toBeInTheDocument();
    expect(email).not.toHaveAttribute("aria-invalid");
    expect(email).not.toHaveAttribute("aria-describedby");
  });

  it("prevents invalid email submission, focuses it, and does not call the API", async () => {
    await renderAnonymous("/login");
    const email = screen.getByLabelText("Correo electrónico");
    fireEvent.change(email, { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(
      screen.getByText("Ingresá un correo electrónico válido."),
    ).toBeInTheDocument();
    expect(document.activeElement).toBe(email);
    expect(login).not.toHaveBeenCalled();
    expect(email.closest("form")).toHaveAttribute("novalidate");
  });

  it("validates register fields on blur and revalidates a touched confirmation when its password changes", async () => {
    await renderAnonymous("/register");
    const tenant = screen.getByLabelText("Nombre del equipo");
    const password = screen.getByLabelText("Contraseña");
    const confirmation = screen.getByLabelText("Confirmar contraseña");
    fireEvent.blur(tenant);
    fireEvent.blur(password);
    fireEvent.change(confirmation, { target: { value: "otra" } });
    fireEvent.blur(confirmation);
    expect(
      screen.getByText("Ingresá el nombre del equipo."),
    ).toBeInTheDocument();
    expect(screen.getByText("Ingresá tu contraseña.")).toBeInTheDocument();
    expect(
      screen.getByText("Las contraseñas no coinciden."),
    ).toBeInTheDocument();
    fireEvent.change(password, { target: { value: "corta" } });
    expect(
      screen.getByText("La contraseña debe tener al menos 8 caracteres."),
    ).toBeInTheDocument();
    fireEvent.change(password, { target: { value: "contraseña-segura" } });
    fireEvent.change(confirmation, { target: { value: "contraseña-segura" } });
    expect(
      screen.queryByText("Las contraseñas no coinciden."),
    ).not.toBeInTheDocument();
  });

  it("validates recovery request email and all recovery confirmation fields", async () => {
    await renderAnonymous("/recovery");
    fireEvent.blur(screen.getByLabelText("Correo electrónico"));
    expect(
      screen.getByText("Ingresá tu correo electrónico."),
    ).toBeInTheDocument();
    cleanup();
    await renderAnonymous("/recovery/confirm");
    fireEvent.blur(screen.getByLabelText("Código de recuperación"));
    fireEvent.blur(screen.getByLabelText("Contraseña"));
    fireEvent.blur(screen.getByLabelText("Confirmar contraseña"));
    expect(
      screen.getByText("Ingresá el código de recuperación."),
    ).toBeInTheDocument();
    expect(screen.getByText("Ingresá tu contraseña.")).toBeInTheDocument();
    expect(screen.getByText("Repetí la nueva contraseña.")).toBeInTheDocument();
  });

  it("validates the required login password and keeps transport errors form-level", async () => {
    await renderAnonymous("/login");
    fireEvent.blur(screen.getByLabelText("Contraseña"));
    expect(screen.getByText("Ingresá tu contraseña.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "ana@equipo.edu" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña" },
    });
    vi.mocked(login).mockRejectedValueOnce(new Error("Servicio no disponible"));
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    const error = await screen.findByText("Servicio no disponible");
    expect(error).toHaveClass("error");
    expect(error.closest(".field")).toBeNull();
  });

  it("does not validate a password field merely because its visibility toggle is clicked", async () => {
    await renderAnonymous("/login");
    fireEvent.click(screen.getByRole("button", { name: "Mostrar contraseña" }));
    expect(
      screen.queryByText("Ingresá tu contraseña."),
    ).not.toBeInTheDocument();
  });
});

describe("platform route separation", () => {
  it("routes /platform to the isolated platform surface instead of the tenant app", async () => {
    vi.mocked(getSession).mockRejectedValueOnce(new Error("unauthenticated"));
    vi.mocked(getPlatformSummary).mockRejectedValueOnce(
      new Error("Platform access denied."),
    );
    renderAt("/platform/summary");
    expect(
      await screen.findByText(/administración de plataforma/i),
    ).toBeInTheDocument();
    // Tenant chrome (workspace name/nav) never renders on the isolated platform route.
    expect(screen.queryByText("Espacio de experimentos")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Espacio de trabajo:/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Experimentos" }),
    ).not.toBeInTheDocument();
  });

  it("does not let a tenant session grant access to the platform surface", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(adminSession);
    vi.mocked(getPlatformSummary).mockRejectedValueOnce(
      new Error("Platform access denied."),
    );
    renderAt("/platform/summary");
    expect(
      await screen.findByRole("heading", { name: "Ingresar" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/acceso exclusivo para administradores de plataforma/i),
    ).toBeInTheDocument();
  });
});
