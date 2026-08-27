import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { AssistantPage } from "./AssistantPage";

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  queryAssistant: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AssistantPage", () => {
  it("renders partial evidence and safe provenance", async () => {
    vi.mocked(api.queryAssistant).mockResolvedValue({
      requested_mode: "combined",
      resolved_mode: "combined",
      status: "partial",
      answer: "Respuesta sustentada.",
      unavailable: ["document"],
      citations: [],
      relational: {
        rows: [{ name: "Prueba" }],
        sql_provenance: {
          query: "SELECT name FROM public.assistant_experiments",
          row_count: 1,
        },
      },
    });
    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText("Fuente de respuesta"), {
      target: { value: "combined" },
    });
    fireEvent.change(screen.getByLabelText("Consulta"), {
      target: { value: "estado actual" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(
      await screen.findByText("Respuesta sustentada."),
    ).toBeInTheDocument();
    expect(screen.getByText("Respuesta parcial")).toBeInTheDocument();
    expect(
      screen.getByText(/evidencia documental no estuvo disponible/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 filas consultadas/)).toBeInTheDocument();
    expect(api.queryAssistant).toHaveBeenCalledWith(
      "estado actual",
      "combined",
    );
  });

  it("shows a safe unavailable state", async () => {
    vi.mocked(api.queryAssistant).mockRejectedValue(
      new Error("El asistente no está disponible para esta consulta."),
    );
    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText("Consulta"), {
      target: { value: "consulta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El asistente no está disponible",
    );
  });
});
