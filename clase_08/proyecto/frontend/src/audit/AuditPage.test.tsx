import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { AuditPage } from "./AuditPage";

vi.mock("../api", () => ({ getAuditEvents: vi.fn(), getMembers: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function HistoryNavigation({ target }: { target: string }) {
  const navigate = useNavigate();
  return <button onClick={() => navigate(target)}>Navigate</button>;
}

const response: api.AuditEventsResponse = {
  items: [
    {
      id: "audit-1",
      occurred_at: "2026-03-30T12:00:00Z",
      actor: { user_id: "u1", email: "ana@example.test" },
      action: "document.upload",
      outcome: "success",
      resource: "document:1",
      detail: { filename: "report.pdf", token: "must-not-render" },
      source: "audit",
    },
    {
      id: "status-1",
      occurred_at: "2026-03-30T11:00:00Z",
      actor: null,
      action: "experiment.status_transition",
      outcome: "success",
      resource: "experiment:2",
      detail: { previous_status: "draft", next_status: "running" },
      source: "experiment_status",
    },
    {
      id: "ingestion-1",
      occurred_at: "2026-03-30T10:00:00Z",
      actor: null,
      action: "document.ingest.completed",
      outcome: "success",
      resource: "document:3",
      detail: { chunk_count: 3 },
      source: "ingestion",
    },
  ],
  total: 11,
  page: 2,
  per_page: 20,
  pages: 3,
};

describe("AuditPage", () => {
  it("restores URL filters, normalizes every source, and renders safe details", async () => {
    vi.mocked(api.getMembers).mockResolvedValue({
      items: [
        {
          user_id: "u1",
          email: "ana@example.test",
          role: "member",
          status: "active",
          password_setup_required: false,
        },
      ],
      total: 1,
      page: 1,
      per_page: 50,
      pages: 1,
    });
    vi.mocked(api.getAuditEvents).mockResolvedValue(response);
    const { container } = render(
      <MemoryRouter
        initialEntries={[
          "/audit?from=2026-03-20&to=2026-03-30&search=report&action=document.upload&outcome=success&actor_id=u1&page=2&per_page=20",
        ]}
      >
        <AuditPage />
      </MemoryRouter>,
    );
    expect(await screen.findAllByText("Subida de documento")).not.toHaveLength(
      0,
    );
    expect(screen.getAllByText("Sistema").length).toBeGreaterThan(0);
    expect(container.querySelector("table")).toBeInTheDocument();
    expect(container.querySelector(".audit-cards")).toBeInTheDocument();
    expect(api.getAuditEvents).toHaveBeenCalledWith(
      expect.objectContaining({
        from: "2026-03-20",
        to: "2026-03-30",
        search: "report",
        action: "document.upload",
        outcome: "success",
        actor_id: "u1",
        page: 2,
        per_page: 20,
      }),
    );
    fireEvent.click(
      screen.getAllByRole("button", { name: /ver detalles/i })[0],
    );
    expect(
      screen.getByRole("dialog", { name: /detalles del evento/i }),
    ).toHaveTextContent("report.pdf");
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("synchronizes visible drafts and the request when browser history changes", async () => {
    vi.mocked(api.getMembers).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      per_page: 50,
      pages: 1,
    });
    vi.mocked(api.getAuditEvents).mockResolvedValue(response);
    render(
      <MemoryRouter
        initialEntries={["/audit?from=2026-01-01&to=2026-01-31&search=initial"]}
      >
        <HistoryNavigation target="/audit?from=2026-02-01&to=2026-02-28&search=history" />
        <AuditPage />
      </MemoryRouter>,
    );
    expect(await screen.findByDisplayValue("2026-01-01")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Navigate" }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("2026-02-01")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("2026-02-28")).toBeInTheDocument();
    expect(screen.getByDisplayValue("history")).toBeInTheDocument();
    expect(api.getAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({
        from: "2026-02-01",
        to: "2026-02-28",
        search: "history",
      }),
    );
  });

  it("loads every member page including inactive historical actors without duplicates", async () => {
    vi.mocked(api.getAuditEvents).mockResolvedValue(response);
    vi.mocked(api.getMembers)
      .mockResolvedValueOnce({
        items: Array.from({ length: 50 }, (_, index) => ({
          user_id: `user-${index}`,
          email: `user-${index}@example.test`,
          role: "member" as const,
          status: "active" as const,
          password_setup_required: false,
        })),
        total: 52,
        page: 1,
        per_page: 50,
        pages: 2,
      })
      .mockResolvedValueOnce({
        items: [
          {
            user_id: "user-49",
            email: "user-49@example.test",
            role: "member",
            status: "active",
            password_setup_required: false,
          },
          {
            user_id: "inactive-user",
            email: "inactive@example.test",
            role: "viewer",
            status: "inactive",
            password_setup_required: false,
          },
        ],
        total: 52,
        page: 2,
        per_page: 50,
        pages: 2,
      });
    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("option", { name: "inactive@example.test" }),
    ).toBeInTheDocument();
    expect(api.getMembers).toHaveBeenNthCalledWith(1, {
      page: 1,
      per_page: 50,
      search: "",
      role: "",
      status: "",
      sort: "email:asc",
    });
    expect(api.getMembers).toHaveBeenNthCalledWith(2, {
      page: 2,
      per_page: 50,
      search: "",
      role: "",
      status: "",
      sort: "email:asc",
    });
    expect(
      screen.getAllByRole("option", { name: "user-49@example.test" }),
    ).toHaveLength(1);
  });

  it("uses inclusive seven-day defaults and validates a maximum 31-day range", async () => {
    vi.mocked(api.getMembers).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      per_page: 50,
      pages: 1,
    });
    vi.mocked(api.getAuditEvents)
      .mockRejectedValueOnce(new Error("Sin conexión"))
      .mockResolvedValueOnce({ ...response, items: [] });
    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin conexión");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(/no hay eventos/i)).toBeInTheDocument();
    const firstQuery = vi.mocked(api.getAuditEvents).mock.calls[0][0];
    expect(firstQuery.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(firstQuery.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: "2026-01-31" },
    });
    fireEvent.click(screen.getByRole("button", { name: /aplicar filtros/i }));
    await waitFor(() =>
      expect(api.getAuditEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ from: "2026-01-01", to: "2026-01-31" }),
      ),
    );
    const validRequestCount = vi.mocked(api.getAuditEvents).mock.calls.length;
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: "2026-02-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: /aplicar filtros/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /máximo 31 días/i,
    );
    expect(api.getAuditEvents).toHaveBeenCalledTimes(validRequestCount);
  });
});
