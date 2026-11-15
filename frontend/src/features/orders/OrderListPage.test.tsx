import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { OrderListPage } from "./OrderListPage";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "sales" }),
}));

const meResponse = {
  user: { id: "u1", email: "a@b.c", display_name: "کاربر" },
  organizations: [],
};

describe("OrderListPage", () => {
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

  it("renders StatusChip and a real link to the order detail", async () => {
    const orderId = "abcdef12-3456-7890-abcd-ef1234567890";
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (p.includes("/me")) return Promise.resolve(meResponse);
      if (p.includes("/customers")) {
        return Promise.resolve([{ id: "c1", tenant_id: "ten-1", name: "مشتری تست", phone: null, email: null, notes: null, version: 1 }]);
      }
      if (p.includes("/orders")) {
        return Promise.resolve([
          {
            id: orderId,
            tenant_id: "ten-1",
            customer_id: "c1",
            status: "RESERVED",
            version: 1,
            created_at: "2024-03-20T12:00:00.000Z",
          },
        ]);
      }
      return Promise.resolve([]);
    });

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AppThemeProvider>
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={["/t/ten-1/orders"]}>
            <Routes>
              <Route path="/t/:tenantId/orders" element={<OrderListPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </AppThemeProvider>,
    );

    expect(await screen.findByLabelText("وضعیت: رزروشده")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: /abcdef12/i });
    expect(link).toHaveAttribute("href", `/t/ten-1/orders/${orderId}`);
  });
});
