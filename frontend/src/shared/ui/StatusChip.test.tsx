import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppThemeProvider } from "../../theme";
import { StatusChip } from "./StatusChip";

describe("StatusChip", () => {
  it("exposes Persian label in accessible name and visible text", () => {
    render(
      <AppThemeProvider>
        <StatusChip status="RESERVED" label="رزروشده" />
      </AppThemeProvider>,
    );

    expect(screen.getByLabelText("وضعیت: رزروشده")).toBeInTheDocument();
    expect(screen.getByText("رزروشده")).toBeInTheDocument();
  });

  it("renders distinct labels for shipped vs cancelled", () => {
    const { rerender } = render(
      <AppThemeProvider>
        <StatusChip status="SHIPPED" label="ارسال‌شده" />
      </AppThemeProvider>,
    );
    expect(screen.getByLabelText("وضعیت: ارسال‌شده")).toBeInTheDocument();

    rerender(
      <AppThemeProvider>
        <StatusChip status="CANCELLED" label="لغوشده" />
      </AppThemeProvider>,
    );
    expect(screen.getByLabelText("وضعیت: لغوشده")).toBeInTheDocument();
  });
});
