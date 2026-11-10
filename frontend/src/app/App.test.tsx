import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { AppThemeProvider } from "./theme";

describe("App shell", () => {
  it("renders the StockPilot brand in Persian RTL shell", () => {
    render(
      <AppThemeProvider>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "StockPilot" })).toBeInTheDocument();
    expect(
      screen.getByText("سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش"),
    ).toBeInTheDocument();
  });
});
