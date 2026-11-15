import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import { AppProviders } from "../../app/providers";
import { AppThemeProvider } from "../../theme";

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: vi.fn().mockResolvedValue({
      user: { id: "u1", email: "a@b.c", display_name: "کاربر" },
      organizations: [],
    }),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "admin" }),
}));

describe("NotFoundPage", () => {
  it("renders standalone 404 for unknown top-level routes", () => {
    render(
      <AppThemeProvider>
        <AppProviders>
          <MemoryRouter initialEntries={["/no-such-page"]}>
            <App />
          </MemoryRouter>
        </AppProviders>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "صفحه یافت نشد" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "بازگشت به خانه" })).toHaveAttribute("href", "/");
  });

  it("renders tenant 404 inside shell for unknown /t/:tenantId paths", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <AppThemeProvider>
        <AppProviders>
          <MemoryRouter initialEntries={["/t/ten-1/unknown-path"]}>
            <App />
          </MemoryRouter>
        </AppProviders>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "صفحه یافت نشد" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "منوی سازمان" })).toBeInTheDocument();
  });
});
