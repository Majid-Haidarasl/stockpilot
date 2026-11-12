import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
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

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/t/ten-1/dashboard"]}>
        <Routes>
          <Route path="/t/:tenantId/dashboard" element={<DashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage states", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("shows loading then empty-ish counts when API returns zeros", async () => {
    let resolveFetch: (value: unknown) => void = () => undefined;
    fetchMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();

    resolveFetch({
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
    fetchMock.mockRejectedValueOnce(
      new ApiProblemError({
        status: 500,
        code: "HTTP_ERROR",
        title: "Server error",
        detail: "شکست موقت",
      }),
    );
    renderPage();
    expect(await screen.findByText(/شکست موقت/)).toBeInTheDocument();
  });
});
