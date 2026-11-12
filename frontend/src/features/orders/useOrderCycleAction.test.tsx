import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
import { useOrderCycleAction } from "./useOrderCycleAction";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const orderBase = {
  id: "ord-1",
  tenant_id: "ten-1",
  customer_id: "cus-1",
  status: "DRAFT",
  version: 1,
  lines: [
    {
      id: "ln-1",
      product_id: "p-1",
      product_sku: "SKU-100",
      product_title: "برنج طارم",
      quantity: 7,
      unit_price: { amount: "1000", currency: "IRR" },
    },
  ],
  total: { amount: "7000", currency: "IRR" },
  total_is_estimate: true,
};

describe("useOrderCycleAction", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("on VERSION_CONFLICT reloads the order and does not resubmit", async () => {
    const conflict = new ApiProblemError({
      status: 409,
      code: "VERSION_CONFLICT",
      title: "Order version conflict",
    });
    const reloaded = { ...orderBase, version: 2, status: "DRAFT" };

    fetchMock
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce(reloaded);

    const { result } = renderHook(
      () =>
        useOrderCycleAction({
          tenantId: "ten-1",
          orderId: "ord-1",
          titleBySku: { "SKU-100": "برنج طارم" },
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.run("reserve", 1);
    });

    await waitFor(() => {
      expect(result.current.lastConflictCode).toBe("VERSION_CONFLICT");
    });

    // First call: reserve POST. Second: GET reload. No third auto-resubmit.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/reserve");
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/\/orders\/ord-1$/);
    expect(result.current.errorMessage).toMatch(/نسخه داده/);
  });

  it("renders stock shortfall with product name and available qty on reserve", async () => {
    const stockErr = new ApiProblemError({
      status: 409,
      code: "INSUFFICIENT_STOCK",
      title: "Insufficient stock",
      errors: [{ sku: "SKU-100", requested: 7, available: 2 }],
    });
    fetchMock.mockRejectedValueOnce(stockErr);

    const { result } = renderHook(
      () =>
        useOrderCycleAction({
          tenantId: "ten-1",
          orderId: "ord-1",
          titleBySku: { "SKU-100": "برنج طارم" },
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.run("reserve", 1);
    });

    expect(result.current.lastConflictCode).toBe("INSUFFICIENT_STOCK");
    expect(result.current.errorMessage).toContain("برنج طارم");
    expect(result.current.errorMessage).toContain("۲");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("on RESERVATION_EXPIRED reloads order so UI can show EXPIRED", async () => {
    const expired = new ApiProblemError({
      status: 409,
      code: "RESERVATION_EXPIRED",
      title: "Reservation has expired",
    });
    const reloaded = { ...orderBase, status: "EXPIRED", version: 3, total_is_estimate: false };

    fetchMock.mockRejectedValueOnce(expired).mockResolvedValueOnce(reloaded);

    const { result } = renderHook(
      () => useOrderCycleAction({ tenantId: "ten-1", orderId: "ord-1" }),
      { wrapper },
    );

    await act(async () => {
      await result.current.run("confirm", 2);
    });

    expect(result.current.lastConflictCode).toBe("RESERVATION_EXPIRED");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/\/orders\/ord-1$/);
  });

  it("retries the same action with the same Idempotency-Key", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce({ ...orderBase, status: "RESERVED", version: 2 });

    const { result } = renderHook(
      () => useOrderCycleAction({ tenantId: "ten-1", orderId: "ord-1" }),
      { wrapper },
    );

    await act(async () => {
      await result.current.run("reserve", 1);
    });
    const firstKey = (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >;

    await act(async () => {
      await result.current.retry("reserve", 1);
    });
    const secondKey = (fetchMock.mock.calls[1][1] as RequestInit).headers as Record<
      string,
      string
    >;

    expect(firstKey["Idempotency-Key"]).toBe(secondKey["Idempotency-Key"]);
  });
});
