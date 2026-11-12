import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { AppProviders } from "./providers";
import { AppThemeProvider } from "./theme";

describe("App shell", () => {
  it("renders the StockPilot brand in Persian RTL shell", () => {
    render(
      <AppThemeProvider>
        <AppProviders>
          <MemoryRouter>
            <App />
          </MemoryRouter>
        </AppProviders>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "StockPilot" })).toBeInTheDocument();
    expect(
      screen.getByText("سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش"),
    ).toBeInTheDocument();
  });
});
