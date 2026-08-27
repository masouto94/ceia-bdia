import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { DashboardPage } from "./DashboardPage";
import {
  collectDashboardExportRows,
  dashboardExportRows,
} from "./dashboardExport";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  getDashboard: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const response: api.DashboardResponse = {
  range: { from: "2025-01-01", to: "2025-01-07" },
  kpis: { total: 2, running: 1, completed: 1, results: 3 },
  daily: [
    { date: "2025-01-01", experiments: 1, results: 2, metric_average: 0.9 },
  ],
  statuses: [{ status: "completed", count: 1 }],
  items: [
    {
      id: "one",
      name: "Clasificador",
      status: "completed",
      created_at: "2025-01-01T12:00:00Z",
      result_count: 2,
      latest_metric: 0.9,
    },
  ],
  total: 1,
  page: 1,
  per_page: 10,
  pages: 1,
};

describe("DashboardPage", () => {
  it("builds structured export rows from every filtered result page", async () => {
    const secondPage = {
      ...response,
      items: [{ ...response.items[0], id: "two", name: "Regresor" }],
      page: 2,
      pages: 2,
    };
    const query: api.DashboardQuery = {
      from: "2025-01-01",
      to: "2025-01-07",
      search: "",
      status: "",
      sort: "created_at:desc",
      page: 1,
      per_page: 50,
    };
    const getPage = vi.fn().mockResolvedValueOnce(secondPage);

    await expect(
      collectDashboardExportRows({ ...response, pages: 2 }, query, getPage),
    ).resolves.toEqual([
      ["Clasificador", "Completado", "2025-01-01T12:00:00Z", 2, 0.9],
      ["Regresor", "Completado", "2025-01-01T12:00:00Z", 2, 0.9],
    ]);
    expect(getPage).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, per_page: 50 }),
    );
    expect(dashboardExportRows(response)).toContainEqual([
      "Clasificador",
      "Completado",
      "2025-01-01T12:00:00Z",
      2,
      0.9,
    ]);
  });

  it("starts exports at page one when the table is displaying a later page", async () => {
    const laterPage = {
      ...response,
      items: [{ ...response.items[0], id: "two", name: "Regresor" }],
      page: 2,
      pages: 2,
    };
    const query: api.DashboardQuery = {
      from: "2025-01-01",
      to: "2025-01-07",
      search: "",
      status: "",
      sort: "created_at:desc",
      page: 1,
      per_page: 50,
    };
    const getPage = vi
      .fn()
      .mockResolvedValueOnce({ ...response, pages: 2 })
      .mockResolvedValueOnce(laterPage);

    await expect(
      collectDashboardExportRows(laterPage, query, getPage),
    ).resolves.toHaveLength(2);
    expect(getPage.mock.calls.map(([calledQuery]) => calledQuery.page)).toEqual(
      [1, 2],
    );
  });

  it("loads the current range, exposes filters, and creates structured exports", async () => {
    vi.mocked(api.getDashboard).mockResolvedValue(response);
    render(<DashboardPage />);
    expect(
      await screen.findByRole("button", { name: "Exportar XLSX" }),
    ).toBeInTheDocument();
    expect(api.getDashboard).toHaveBeenCalledWith(
      expect.objectContaining({
        from: expect.any(String),
        to: expect.any(String),
        page: 1,
      }),
    );
    expect(screen.getByPlaceholderText("Buscar experimentos")).toHaveAttribute(
      "aria-label",
      "Buscar experimentos",
    );
    fireEvent.change(screen.getByLabelText("Buscar experimentos"), {
      target: { value: "clas" },
    });
    expect(api.getDashboard).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() =>
      expect(api.getDashboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "clas", page: 1 }),
      ),
    );
    expect(
      screen.getByRole("button", { name: "Exportar XLSX" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Exportar PDF" }),
    ).toBeInTheDocument();
  });

  it("uses the unified pagination controls and keeps the selected size in the filter draft", async () => {
    const paged = { ...response, total: 31, pages: 3 };
    vi.mocked(api.getDashboard).mockImplementation((query) =>
      Promise.resolve({ ...paged, page: query.page, per_page: query.per_page }),
    );
    render(<DashboardPage />);
    await screen.findByRole("button", { name: "Exportar XLSX" });
    fireEvent.click(screen.getByRole("button", { name: "Tabla" }));

    expect(
      screen.getByRole("navigation", { name: "Paginación del panel" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Filas por página")).toHaveValue("10");
    expect(
      screen.getByRole("button", { name: "Primera página" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Página anterior" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Última página" })).toBeEnabled();
    expect(
      screen
        .getAllByRole("option")
        .slice(-5)
        .map((option) => option.textContent),
    ).toEqual(["10", "20", "30", "40", "50"]);

    fireEvent.click(screen.getByRole("button", { name: "Última página" }));
    await waitFor(() =>
      expect(api.getDashboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3, per_page: 10 }),
      ),
    );
    expect(
      screen.getByRole("button", { name: "Página siguiente" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Última página" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Filas por página"), {
      target: { value: "20" },
    });
    await waitFor(() =>
      expect(api.getDashboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, per_page: 20 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() =>
      expect(api.getDashboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, per_page: 20 }),
      ),
    );
  });

  it("keeps filters and KPIs shared while separating chart and table content", async () => {
    vi.mocked(api.getDashboard).mockResolvedValue(response);
    render(<DashboardPage />);

    await screen.findByRole("button", { name: "Exportar XLSX" });
    expect(
      screen.getByRole("group", { name: "Vista del dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gráficos" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Tabla" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("dashboard-filters")).toBeInTheDocument();
    expect(screen.getByText("Experimentos")).toBeInTheDocument();
    expect(screen.getByText("Actividad diaria")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Tabla" }));

    expect(screen.getByRole("button", { name: "Tabla" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Gráficos" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("dashboard-filters")).toBeInTheDocument();
    expect(screen.getByText("Experimentos")).toBeInTheDocument();
    expect(screen.queryByText("Actividad diaria")).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("resets the table page on view changes without creating another request when already on page one", async () => {
    vi.mocked(api.getDashboard).mockResolvedValue(response);
    render(<DashboardPage />);
    await screen.findByRole("button", { name: "Exportar XLSX" });
    await waitFor(() => expect(api.getDashboard).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Tabla" }));
    expect(api.getDashboard).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Gráficos" }));
    expect(api.getDashboard).toHaveBeenCalledTimes(1);
  });

  it("commits a date range with one dashboard request", async () => {
    vi.mocked(api.getDashboard).mockResolvedValue(response);
    render(<DashboardPage />);
    const trigger = await screen.findByRole("button", { name: /\d.*\d/ });
    await waitFor(() => expect(api.getDashboard).toHaveBeenCalledTimes(1));

    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "Hoy" }));
    fireEvent.click(screen.getByRole("button", { name: "Actualizar" }));

    await waitFor(() => expect(api.getDashboard).toHaveBeenCalledTimes(2));
    expect(api.getDashboard).toHaveBeenLastCalledWith(
      expect.objectContaining({
        from: expect.any(String),
        to: expect.any(String),
        page: 1,
      }),
    );
  });

  it("keeps the Panel heading visible when the request fails and offers retry", async () => {
    vi.mocked(api.getDashboard).mockRejectedValueOnce(
      new Error("Sin conexión"),
    );
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Panel" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Sin conexión");
    expect(
      screen.getByRole("button", { name: "Reintentar" }),
    ).toBeInTheDocument();
  });
});
