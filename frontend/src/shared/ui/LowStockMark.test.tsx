import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppThemeProvider } from "../../theme";
import { LowStockMark, LOW_STOCK_LABEL } from "./LowStockMark";

describe("LowStockMark", () => {
  it("renders warning text and does not rely on color alone", () => {
    render(
      <AppThemeProvider>
        <LowStockMark />
      </AppThemeProvider>,
    );
    expect(screen.getByText(LOW_STOCK_LABEL)).toBeInTheDocument();
  });

  it("renders nothing when show is false", () => {
    const { container } = render(
      <AppThemeProvider>
        <LowStockMark show={false} />
      </AppThemeProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
