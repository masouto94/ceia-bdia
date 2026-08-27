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
import { DocumentsPage } from "./DocumentsPage";

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  getDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  ingestDocument: vi.fn(),
  retrieveDocuments: vi.fn(),
  downloadDocument: vi.fn(),
  getDocument: vi.fn(),
}));
const empty: api.DocumentsResponse = {
  items: [],
  total: 0,
  page: 1,
  per_page: 10,
  pages: 0,
};
const document: api.Document = {
  id: "d1",
  name: "guia.md",
  content_type: "text/markdown",
  size_bytes: 10,
  ingestion_status: "pending",
};
const page = (canMutate = true, entry = "/documents") =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <DocumentsPage canMutate={canMutate} />
    </MemoryRouter>,
  );

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DocumentsPage", () => {
  it("fetches the initial URL query and keeps table headers for an empty list", async () => {
    vi.mocked(api.getDocuments).mockResolvedValue(empty);
    page();
    await waitFor(() =>
      expect(api.getDocuments).toHaveBeenCalledWith({
        page: 1,
        per_page: 10,
        search: "",
        status: "",
        sort: "name:asc",
      }),
    );
    expect(screen.getByText("Nombre")).toBeInTheDocument();
    expect(screen.getByText("Tipo y tamaño")).toBeInTheDocument();
    expect(screen.getByText("Estado")).toBeInTheDocument();
    expect(
      screen.getByText(/No hay documentos todavía/).closest("td"),
    ).toHaveAttribute("colspan", "4");
    expect(screen.getByText("0 documentos")).toBeInTheDocument();
  });

  it("uses explicit Buscar and filter labels in Spanish", async () => {
    vi.mocked(api.getDocuments).mockResolvedValue(empty);
    page();
    await screen.findByText(/No hay documentos todavía/);
    fireEvent.change(screen.getByPlaceholderText("Buscar documentos"), {
      target: { value: "guía" },
    });
    expect(api.getDocuments).toHaveBeenCalledTimes(1);
    fireEvent.submit(
      screen.getByPlaceholderText("Buscar documentos").closest("form")!,
    );
    await waitFor(() =>
      expect(api.getDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "guía", page: 1 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /Filtros/ }));
    for (const label of [
      "Pendiente",
      "Procesando",
      "Listo",
      "Fallido",
      "Nombre A-Z",
      "Nombre Z-A",
      "Estado A-Z",
      "Estado Z-A",
    ])
      expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("restores URL filters, renders actions, and keeps viewers read-only", async () => {
    vi.mocked(api.getDocuments).mockResolvedValue({
      ...empty,
      items: [document],
      total: 1,
      pages: 1,
    });
    page(
      false,
      "/documents?page=2&per_page=20&search=guia&status=pending&sort=status%3Adesc",
    );
    await screen.findAllByText("guia.md");
    expect(api.getDocuments).toHaveBeenCalledWith({
      page: 2,
      per_page: 20,
      search: "guia",
      status: "pending",
      sort: "status:desc",
    });
    const downloadButtons = screen.getAllByRole("button", {
      name: "Descargar documento",
    });
    expect(downloadButtons).not.toHaveLength(0);
    for (const button of downloadButtons) {
      expect(button.closest(".row-actions")).toBeInTheDocument();
      expect(button.querySelector("svg")).toBeInTheDocument();
    }
    const documentCard = screen
      .getAllByText("guia.md")
      .find((element) => element.closest(".document-card"))
      ?.closest(".document-card");
    expect(
      documentCard?.querySelector("footer > .row-actions"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Ver información del documento" }),
    ).not.toHaveLength(0);
    expect(
      screen.queryByRole("button", { name: "Ingerir documento" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Archivo PDF/)).not.toBeInTheDocument();
  });

  it("clears a document-info error immediately when retrying and shows the successful response without a stale alert", async () => {
    let resolveRetry!: (value: api.DocumentDetail) => void;
    vi.mocked(api.getDocuments).mockResolvedValue({
      ...empty,
      items: [document],
      total: 1,
      pages: 1,
    });
    vi.mocked(api.getDocument)
      .mockRejectedValueOnce(new Error("No disponible"))
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRetry = resolve;
          }),
      );
    page();
    fireEvent.click(
      (
        await screen.findAllByRole("button", {
          name: "Ver información del documento",
        })
      )[0],
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("No disponible");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Cargando información…")).toBeInTheDocument();
    resolveRetry({
      ...document,
      active_chunk_count: 2,
      latest_run: {
        status: "ready",
        chunk_count: 2,
        created_at: "2026-03-30T10:00:00Z",
        error: null,
      },
    });
    expect(await screen.findByText("Chunks activos")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getAllByText("2")).toHaveLength(2);
    expect(api.getDocument).toHaveBeenCalledTimes(2);
  });

  it("retries a failed list request without removing the toolbar", async () => {
    vi.mocked(api.getDocuments)
      .mockRejectedValueOnce(new Error("falló"))
      .mockResolvedValue(empty);
    page();
    expect(await screen.findByRole("alert")).toHaveTextContent("falló");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByText(/No hay documentos todavía/);
    expect(api.getDocuments).toHaveBeenCalledTimes(2);
  });
});
