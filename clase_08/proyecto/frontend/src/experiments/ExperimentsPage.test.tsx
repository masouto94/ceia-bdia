import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import * as api from "../api";
import { ExperimentsPage } from "./ExperimentsPage";

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  getExperiments: vi.fn(),
  getExperiment: vi.fn(),
  createExperiment: vi.fn(),
  updateExperiment: vi.fn(),
  appendExperimentResult: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const experiment: api.Experiment = {
  id: "e1",
  name: "Clasificador",
  status: "draft",
  creator_id: "u1",
  created_at: "2026-03-30T10:00:00Z",
  updated_at: "2026-03-30T10:00:00Z",
};
const page = (items = [experiment]): api.ExperimentsResponse => ({
  items,
  total: items.length,
  page: 1,
  per_page: 10,
  pages: 1,
});
const renderPage = (canMutate: boolean) =>
  render(
    <MemoryRouter>
      <ExperimentsPage canMutate={canMutate} />
    </MemoryRouter>,
  );

describe("ExperimentsPage", () => {
  it("renders the Personas-style toolbar and submits its draft search explicitly", async () => {
    vi.mocked(api.getExperiments).mockResolvedValue(page());
    render(
      <MemoryRouter
        initialEntries={[
          "/experiments?page=2&per_page=20&search=previo&status=running&sort=name%3Aasc",
        ]}
      >
        <ExperimentsPage canMutate={false} />
      </MemoryRouter>,
    );

    const search = await screen.findByPlaceholderText("Buscar experimentos");
    expect(search).toHaveValue("previo");
    expect(screen.getByRole("button", { name: "Filtros" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("button", { name: "Buscar" })).toBeInTheDocument();
    expect(api.getExperiments).toHaveBeenCalledWith({
      page: 2,
      per_page: 20,
      search: "previo",
      status: "running",
      archived: false,
      sort: "name:asc",
    });

    fireEvent.change(search, { target: { value: "sin enviar" } });
    expect(api.getExperiments).toHaveBeenCalledTimes(1);
    fireEvent.submit(search.closest("form")!);
    await waitFor(() =>
      expect(api.getExperiments).toHaveBeenLastCalledWith({
        page: 1,
        per_page: 20,
        search: "sin enviar",
        status: "running",
        archived: false,
        sort: "name:asc",
      }),
    );
  });

  it("renders bounded loading, empty, and viewer read-only states", async () => {
    let resolve!: (value: api.ExperimentsResponse) => void;
    vi.mocked(api.getExperiments).mockReturnValueOnce(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const view = renderPage(false);
    expect(screen.getByLabelText("Cargando experimentos")).toBeInTheDocument();
    resolve(page([]));
    expect(
      await screen.findByText(/Cuando el equipo cree uno/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Nuevo" }),
    ).not.toBeInTheDocument();
    view.unmount();

    vi.mocked(api.getExperiments).mockResolvedValueOnce(page());
    vi.mocked(api.getExperiment).mockResolvedValueOnce({
      ...experiment,
      results: [],
    });
    renderPage(false);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Ver detalle" }))[0],
    );
    expect(
      await screen.findByText("Todavía no hay resultados registrados."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Iniciar experimento" }),
    ).not.toBeInTheDocument();
  });

  it("uses the unified pagination controls and requests the selected page size", async () => {
    const paged = {
      ...page(),
      total: 31,
      pages: 3,
    };
    vi.mocked(api.getExperiments).mockImplementation((query) =>
      Promise.resolve({ ...paged, page: query.page, per_page: query.per_page }),
    );
    renderPage(false);

    expect(
      await screen.findByRole("navigation", {
        name: "Paginación de experimentos",
      }),
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
      expect(api.getExperiments).toHaveBeenLastCalledWith({
        page: 3,
        per_page: 10,
        search: "",
        status: "",
        archived: false,
        sort: "created_at:desc",
      }),
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
      expect(api.getExperiments).toHaveBeenLastCalledWith({
        page: 1,
        per_page: 20,
        search: "",
        status: "",
        archived: false,
        sort: "created_at:desc",
      }),
    );
  });

  it("creates an experiment and refreshes the first page", async () => {
    vi.mocked(api.getExperiments).mockResolvedValue(page([]));
    vi.mocked(api.createExperiment).mockResolvedValue(experiment);
    renderPage(true);
    fireEvent.click(await screen.findByRole("button", { name: "Nuevo" }));
    fireEvent.change(screen.getByLabelText("Nombre del experimento"), {
      target: { value: "  Modelo nuevo  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));
    await waitFor(() =>
      expect(api.createExperiment).toHaveBeenCalledWith("Modelo nuevo"),
    );
    await waitFor(() => expect(api.getExperiments).toHaveBeenCalledTimes(2));
  });

  it("starts a draft and exposes localized errors", async () => {
    vi.mocked(api.getExperiments).mockResolvedValue(page());
    vi.mocked(api.getExperiment).mockResolvedValue({
      ...experiment,
      results: [],
    });
    vi.mocked(api.updateExperiment).mockRejectedValueOnce(
      new Error("La transición de estado no es válida."),
    );
    renderPage(true);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Ver detalle" }))[0],
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Iniciar experimento" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La transición de estado no es válida.",
    );
    expect(api.updateExperiment).toHaveBeenCalledWith("e1", {
      status: "running",
    });
  });

  it("appends a typed result and presents provenance", async () => {
    const running = { ...experiment, status: "running" as const };
    vi.mocked(api.getExperiments).mockResolvedValue(page([running]));
    vi.mocked(api.getExperiment).mockResolvedValue({
      ...running,
      results: [
        {
          id: "r1",
          status: "completed",
          creator_id: "u1",
          created_at: "2026-03-30T11:00:00Z",
          input_summary: "datos",
          output_summary: "predicción",
          metrics: [
            {
              id: "m1",
              creator_id: "u1",
              name: "exactitud",
              value_type: "number",
              number_value: 0.92,
              text_value: null,
              boolean_value: null,
              json_value: null,
              unit: "%",
              step: 2,
              recorded_at: "2026-03-30T11:00:00Z",
            },
          ],
        },
      ],
    });
    vi.mocked(api.appendExperimentResult).mockResolvedValue(
      {} as api.ExperimentResult,
    );

    renderPage(true);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Ver detalle" }))[0],
    );
    expect(await screen.findByText("exactitud")).toBeInTheDocument();
    expect(screen.getByText(/Número · paso 2/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Resumen de salida"), {
      target: { value: "listo" },
    });
    fireEvent.change(screen.getByLabelText("Métrica opcional"), {
      target: { value: "pérdida" },
    });
    fireEvent.change(screen.getByLabelText("Valor"), {
      target: { value: "0.1" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Registrar resultado" }),
    );
    await waitFor(() =>
      expect(api.appendExperimentResult).toHaveBeenCalledWith("e1", {
        status: "completed",
        output_summary: "listo",
        metrics: [{ name: "pérdida", type: "number", value: 0.1 }],
        terminal_status: "completed",
      }),
    );
    expect(api.updateExperiment).not.toHaveBeenCalled();
  });

  it("submits terminal closure with the result instead of a second status mutation", async () => {
    const running = { ...experiment, status: "running" as const };
    vi.mocked(api.getExperiments).mockResolvedValue(page([running]));
    vi.mocked(api.getExperiment).mockResolvedValue({ ...running, results: [] });
    vi.mocked(api.appendExperimentResult).mockResolvedValue({
      id: "r2",
      status: "completed",
      creator_id: "u1",
      created_at: "2026-03-30T11:00:00Z",
      input_summary: null,
      output_summary: null,
      metrics: [],
      experiment: { ...running, status: "completed" },
    });
    renderPage(true);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Ver detalle" }))[0],
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Registrar resultado" }),
    );
    await waitFor(() =>
      expect(api.appendExperimentResult).toHaveBeenCalledWith("e1", {
        status: "completed",
        output_summary: undefined,
        metrics: [],
        terminal_status: "completed",
      }),
    );
    expect(api.updateExperiment).not.toHaveBeenCalled();
  });

  it("restores the archive scope from the URL and resets the page when changed", async () => {
    vi.mocked(api.getExperiments).mockResolvedValue(page());
    render(
      <MemoryRouter
        initialEntries={[
          "/experiments?page=2&per_page=20&search=previo&status=completed&sort=name%3Aasc&archived=true",
        ]}
      >
        <ExperimentsPage canMutate />
      </MemoryRouter>,
    );
    expect(await screen.findByLabelText("Alcance de experimentos")).toHaveValue(
      "archived",
    );
    expect(api.getExperiments).toHaveBeenLastCalledWith({
      page: 2,
      per_page: 20,
      search: "previo",
      status: "completed",
      archived: true,
      sort: "name:asc",
    });
    fireEvent.change(screen.getByLabelText("Alcance de experimentos"), {
      target: { value: "active" },
    });
    await waitFor(() =>
      expect(api.getExperiments).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, archived: false }),
      ),
    );
  });

  it("supports rename, archive confirmation, and direct restore without lifecycle actions for archived experiments", async () => {
    const archived = {
      ...experiment,
      archived_at: "2026-03-31T10:00:00Z",
      archived_by: "u1",
    };
    vi.mocked(api.getExperiments).mockResolvedValue(page([experiment]));
    vi.mocked(api.updateExperiment).mockResolvedValue(experiment);
    const view = renderPage(true);
    expect(
      await screen.findAllByRole("button", { name: "Editar nombre" }),
    ).toHaveLength(2);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Editar nombre" }))[0],
    );
    fireEvent.change(screen.getByLabelText("Nombre del experimento"), {
      target: { value: "  Renombrado  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar nombre" }));
    await waitFor(() =>
      expect(api.updateExperiment).toHaveBeenCalledWith("e1", {
        name: "Renombrado",
      }),
    );
    fireEvent.click(
      (
        await screen.findAllByRole("button", { name: "Archivar experimento" })
      )[0],
    );
    expect(
      screen.getByText(/historial y los resultados se conservan/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(api.updateExperiment).toHaveBeenCalledTimes(1);
    fireEvent.click(
      (
        await screen.findAllByRole("button", { name: "Archivar experimento" })
      )[0],
    );
    fireEvent.click(screen.getByRole("button", { name: "Archivar" }));
    await waitFor(() =>
      expect(api.updateExperiment).toHaveBeenCalledWith("e1", {
        archived: true,
      }),
    );
    view.unmount();
    vi.mocked(api.getExperiments).mockResolvedValue(page([archived]));
    renderPage(true);
    fireEvent.click(
      (
        await screen.findAllByRole("button", { name: "Restaurar experimento" })
      )[0],
    );
    await waitFor(() =>
      expect(api.updateExperiment).toHaveBeenCalledWith("e1", {
        archived: false,
      }),
    );
    expect(
      screen.queryByRole("button", { name: "Iniciar experimento" }),
    ).not.toBeInTheDocument();
  });

  it("excludes archive for running experiments and hides lifecycle controls for archived detail", async () => {
    const running = { ...experiment, status: "running" as const };
    const archived = {
      ...experiment,
      archived_at: "2026-03-31T10:00:00Z",
      archived_by: "u1",
    };
    vi.mocked(api.getExperiments).mockResolvedValue(page([running]));
    renderPage(true);
    await screen.findAllByText("Clasificador");
    expect(
      screen.queryByRole("button", { name: "Archivar experimento" }),
    ).not.toBeInTheDocument();
    cleanup();
    vi.mocked(api.getExperiments).mockResolvedValue(page([archived]));
    vi.mocked(api.getExperiment).mockResolvedValue({
      ...archived,
      results: [],
    });
    renderPage(true);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Ver detalle" }))[0],
    );
    await screen.findByText("Todavía no hay resultados registrados.");
    expect(
      screen.queryByRole("button", { name: "Iniciar experimento" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Registrar resultado" }),
    ).not.toBeInTheDocument();
  });
});
