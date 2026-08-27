import { fireEvent, render, screen } from "@testing-library/react";
import { Info } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { RowActions } from "./RowActions";

describe("RowActions", () => {
  it("shows labelled tooltips only while their icon actions are hovered or focused", () => {
    const onClick = vi.fn();
    render(
      <RowActions
        actions={[
          { label: "Ver información", icon: Info, onClick },
          { label: "Procesando", icon: Info, onClick, busy: true },
        ]}
      />,
    );

    const info = screen.getByRole("button", { name: "Ver información" });
    const processing = screen.getByRole("button", { name: "Procesando" });
    expect(info).toHaveClass("row-action-button");
    expect(info).toHaveTextContent("");
    expect(info.querySelector("svg")).toBeInTheDocument();
    expect(info).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.mouseEnter(info);
    const hoveredTooltip = screen.getByRole("tooltip", {
      name: "Ver información",
    });
    expect(info).toHaveAttribute("aria-describedby", hoveredTooltip.id);
    fireEvent.mouseLeave(info);
    expect(info).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.focus(info);
    const focusedTooltip = screen.getByRole("tooltip", {
      name: "Ver información",
    });
    expect(info).toHaveAttribute("aria-describedby", focusedTooltip.id);
    fireEvent.keyDown(info, { key: "Escape" });
    expect(info).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.focus(processing);
    const processingTooltip = screen.getByRole("tooltip", {
      name: "Procesando",
    });
    expect(processingTooltip.id).not.toBe(focusedTooltip.id);
    expect(processing).toHaveAttribute(
      "aria-describedby",
      processingTooltip.id,
    );
    fireEvent.blur(processing);
    expect(processing).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.click(info);
    fireEvent.click(processing);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(processing).toBeDisabled();
  });
});
