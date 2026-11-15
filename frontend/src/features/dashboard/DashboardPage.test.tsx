import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { DashboardPage } from "./DashboardPage";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "viewer" }),
}));

const meResponse = {
  user: { id: "u1", email: "a@b.c", display_name: "کاربر" },
  organizations: [],
};

function mockApi(handler: (path: string) => Promise<unknown> | unknown) {
  fetchMock.mockImplementation((path: unknown) => {
    const p = typeof path === "string" ? path : "";
    if (p.includes("/me")) return Promise.resolve(meResponse);
    return Promise.resolve(handler(p));
  });
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <AppThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/t/ten-1/dashboard"]}>
          <Routes>
            <Route path="/t/:tenantId/dashboard" element={<DashboardPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AppThemeProvider>,
  );
}

describe("DashboardPage states", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it("shows loading then empty-ish counts when API returns zeros", async () => {
    let resolveDash: (value: unknown) => void = () => undefined;
    const dashPromise = new Promise((resolve) => {
      resolveDash = resolve;
    });

    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (p.includes("/me")) return Promise.resolve(meResponse);
      return dashPromise;
    });

    renderPage();
    expect(await screen.findByRole("status")).toBeInTheDocument();

    resolveDash({
      order_counts_by_status: {
        DRAFT: 0,
        RESERVED: 0,
        CONFIRMED: 0,
        SHIPPED: 0,
        CANCELLED: 0,
        EXPIRED: 0,
      },
      shipped_total: { amount: "0", currency: "IRR" },
      low_stock: [],
      range_from: new Date().toISOString(),
      range_to: new Date().toISOString(),
    });

    expect(await screen.findByText(/هنوز سفارشی ثبت نشده است/)).toBeInTheDocument();
    expect(screen.getByText(/کالایی زیر آستانه هشدار نیست/)).toBeInTheDocument();
  });

  it("shows error state when the dashboard request fails", async () => {
    mockApi(() => {
      throw new ApiProblemError({
        status: 500,
        code: "HTTP_ERROR",
        title: "Server error",
        detail: "شکست موقت",
      });
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/شکست موقت/)).toBeInTheDocument();
    });
  });
});
