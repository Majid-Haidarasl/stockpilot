import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { DraftOrderPage } from "./DraftOrderPage";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "T", role: "sales" }),
  setTenant: vi.fn(),
  clearTenant: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <AppThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/t/ten-1/orders/new"]}>
          <Routes>
            <Route path="/t/:tenantId/orders/new" element={<DraftOrderPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AppThemeProvider>,
  );
}

describe("DraftOrderPage stock chips", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("keeps picker usable when inventory returns 403 (no ناموجود chip)", async () => {
    fetchMock.mockImplementation(async (path: string) => {
      if (path.includes("/customers")) {
        return [{ id: "c1", tenant_id: "ten-1", name: "Buyer", phone: null, email: null, notes: null, version: 1 }];
      }
      if (path.includes("/products")) {
        return [
          {
            id: "p1",
            tenant_id: "ten-1",
            sku: "SKU-1",
            title: "کالای تست",
            unit_price: { amount: "1000", currency: "IRR" },
            is_active: true,
            stock_warning_threshold: 5,
            version: 1,
          },
        ];
      }
      if (path.includes("/inventory")) {
        throw new ApiProblemError({
          status: 403,
          code: "FORBIDDEN",
          title: "Forbidden",
        });
      }
      throw new Error(`unexpected ${path}`);
    });

    renderPage();

    const productSelect = await screen.findByLabelText("کالا");
    fireEvent.mouseDown(productSelect);
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getByRole("option", { name: /کالای تست/ })).toBeInTheDocument();
    expect(within(listbox).queryByText(/ناموجود/)).not.toBeInTheDocument();
  });

  it("marks zero-stock products as ناموجود when inventory succeeds", async () => {
    fetchMock.mockImplementation(async (path: string) => {
      if (path.includes("/customers")) {
        return [{ id: "c1", tenant_id: "ten-1", name: "Buyer", phone: null, email: null, notes: null, version: 1 }];
      }
      if (path.includes("/products")) {
        return [
          {
            id: "p1",
            tenant_id: "ten-1",
            sku: "SKU-1",
            title: "کالای تست",
            unit_price: { amount: "1000", currency: "IRR" },
            is_active: true,
            stock_warning_threshold: 5,
            version: 1,
          },
        ];
      }
      if (path.includes("/inventory") && !path.includes("/movements")) {
        return [
          {
            product_id: "p1",
            sku: "SKU-1",
            title: "کالای تست",
            warehouse_code: "main",
            on_hand: 0,
            reserved: 0,
            available: 0,
            stock_warning_threshold: 5,
            version: 0,
            has_position: false,
          },
        ];
      }
      throw new Error(`unexpected ${path}`);
    });

    renderPage();

    const productSelect = await screen.findByLabelText("کالا");
    await waitFor(() => expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/inventory"))).toBe(true));
    fireEvent.mouseDown(productSelect);
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getByRole("option", { name: /ناموجود/ })).toBeInTheDocument();
  });
});
