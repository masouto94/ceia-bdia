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

vi.mock("./DateRangePicker", () => ({
  DateRangePicker: ({
    onApply,
  }: {
    onApply: (range: { from: string; to: string }) => void;
  }) => (
    <>
      <button onClick={() => onApply({ from: "2024-01-01", to: "2024-12-31" })}>
        Apply 366 days
      </button>
      <button onClick={() => onApply({ from: "2024-01-01", to: "2025-01-01" })}>
        Apply 367 days
      </button>
      <button onClick={() => onApply({ from: "2026-02-01", to: "2026-01-31" })}>
        Apply reversed
      </button>
    </>
  ),
}));
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
  kpis: { total: 0, running: 0, completed: 0, results: 0 },
  daily: [],
  statuses: [],
  items: [],
  total: 0,
  page: 1,
  per_page: 10,
  pages: 1,
};

describe("DashboardPage date range validation", () => {
  it("accepts 366 inclusive dates and blocks invalid ranges without another dashboard or export request", async () => {
    vi.mocked(api.getDashboard).mockResolvedValue(response);
    render(<DashboardPage />);
    await screen.findByRole("button", { name: "Exportar XLSX" });
    expect(api.getDashboard).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Apply 366 days" }));
    await waitFor(() => expect(api.getDashboard).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: "Apply 367 days" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      /máximo de 366 días inclusivos/i,
    );
    expect(api.getDashboard).toHaveBeenCalledTimes(2);
    expect(
      screen.getByRole("button", { name: "Exportar XLSX" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Apply reversed" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/fecha final/i);
    expect(api.getDashboard).toHaveBeenCalledTimes(2);
  });
});
