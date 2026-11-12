import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { clearTenantSensitiveCache } from "./cache";
import { assertTenantInKey, queryKeys } from "./keys";

describe("tenant query cache", () => {
  it("puts tenant_id in every tenant-scoped query key", () => {
    const tenantId = "tenant-aftab";
    expect(assertTenantInKey(queryKeys.products(tenantId), tenantId)).toBe(true);
    expect(assertTenantInKey(queryKeys.customers(tenantId), tenantId)).toBe(true);
    expect(assertTenantInKey(queryKeys.inventory(tenantId), tenantId)).toBe(true);
    expect(assertTenantInKey(queryKeys.inventoryMovements(tenantId), tenantId)).toBe(true);
  });

  it("cancels in-flight queries before clearing on org switch", async () => {
    const queryClient = new QueryClient();
    const cancelQueries = vi.spyOn(queryClient, "cancelQueries").mockResolvedValue(undefined);
    const clear = vi.spyOn(queryClient, "clear");

    queryClient.setQueryData(queryKeys.products("tenant-a"), [{ id: "1" }]);
    expect(queryClient.getQueryData(queryKeys.products("tenant-a"))).toBeTruthy();

    await clearTenantSensitiveCache(queryClient);

    expect(cancelQueries).toHaveBeenCalledTimes(1);
    expect(clear).toHaveBeenCalledTimes(1);
    expect(cancelQueries.mock.invocationCallOrder[0]).toBeLessThan(clear.mock.invocationCallOrder[0]!);
    expect(queryClient.getQueryData(queryKeys.products("tenant-a"))).toBeUndefined();
  });
});
