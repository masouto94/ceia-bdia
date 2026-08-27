import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DateRangePicker } from "./DateRangePicker";

afterEach(cleanup);

const range = { from: "2025-01-01", to: "2025-01-07" };
const presets = [
  "Hoy",
  "Ayer",
  "Últimos 7 días",
  "Últimos 14 días",
  "Últimos 30 días",
  "Esta semana",
  "Semana pasada",
  "Este mes",
  "Mes pasado",
];

describe("DateRangePicker", () => {
  it("renders the faithful desktop picker with presets, two months, and actions", () => {
    render(<DateRangePicker range={range} onApply={vi.fn()} />);
    const trigger = screen.getByRole("button", {
      name: /1 ene 2025.*7 ene 2025/i,
    });
    expect(trigger).toHaveClass("w-full", "sm:w-auto");
    fireEvent.click(trigger);

    presets.forEach((preset) => {
      expect(screen.getByRole("button", { name: preset })).toBeVisible();
    });
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelectorAll(".rdp-month"),
    ).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Actualizar" })).toBeVisible();
  });

  it("keeps the desktop layout compact through fixed width contracts", () => {
    render(<DateRangePicker range={range} onApply={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("button", { name: /1 ene 2025.*7 ene 2025/i }),
    );

    expect(
      screen
        .getByTestId("date-range-picker-body")
        .closest('[data-slot="popover-content"]'),
    ).toHaveClass("w-[46rem]", "max-w-[calc(100vw-2rem)]");
    expect(screen.getByTestId("date-boundary-from-container")).toHaveClass(
      "w-52",
      "shrink-0",
    );
    expect(screen.getByTestId("date-boundary-to-container")).toHaveClass(
      "w-52",
      "shrink-0",
    );
    expect(screen.getByTestId("date-range-picker-preset-sidebar")).toHaveClass(
      "w-40",
      "shrink-0",
    );
    expect(screen.getByRole("button", { name: "Últimos 30 días" })).toHaveClass(
      "whitespace-nowrap",
    );
    expect(screen.getByTestId("date-range-picker-calendar")).toHaveClass(
      "[--cell-size:--spacing(7.5)]",
    );
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-months"),
    ).toHaveClass("gap-15");
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-button_previous"),
    ).toHaveClass("inline-flex", "bg-background", "text-foreground");
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-button_next"),
    ).toHaveClass("inline-flex", "bg-background", "text-foreground");
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-month"),
    ).toHaveClass("w-[calc(var(--cell-size)*7)]", "flex-none");
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-weekday"),
    ).toHaveClass("p-0", "text-center");
    expect(
      screen
        .getByTestId("date-range-picker-calendar")
        .querySelector(".rdp-day"),
    ).toHaveClass("size-(--cell-size)", "flex-none");
  });

  it("maps the DVEM update range to yyyy-MM-dd strings", () => {
    const onApply = vi.fn();
    render(<DateRangePicker range={range} onApply={onApply} />);
    fireEvent.click(
      screen.getByRole("button", { name: /1 ene 2025.*7 ene 2025/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Hoy" }));
    fireEvent.click(screen.getByRole("button", { name: "Actualizar" }));

    expect(onApply).toHaveBeenCalledWith({
      from: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      to: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    });
  });
});
