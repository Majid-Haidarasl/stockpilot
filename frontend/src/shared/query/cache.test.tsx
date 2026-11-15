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

  it("cancels tenant-scoped queries before removing them; preserves me", async () => {
    const queryClient = new QueryClient();
    const cancelQueries = vi.spyOn(queryClient, "cancelQueries");
    const removeQueries = vi.spyOn(queryClient, "removeQueries");

    queryClient.setQueryData(queryKeys.products("tenant-a"), [{ id: "1" }]);
    queryClient.setQueryData(queryKeys.me(), { user: { id: "u1" }, organizations: [] });
    expect(queryClient.getQueryData(queryKeys.products("tenant-a"))).toBeTruthy();

    await clearTenantSensitiveCache(queryClient);

    expect(cancelQueries).toHaveBeenCalledTimes(1);
    expect(removeQueries).toHaveBeenCalledTimes(1);
    expect(cancelQueries.mock.invocationCallOrder[0]).toBeLessThan(
      removeQueries.mock.invocationCallOrder[0]!,
    );
    expect(queryClient.getQueryData(queryKeys.products("tenant-a"))).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.me())).toEqual({
      user: { id: "u1" },
      organizations: [],
    });
  });

  it("removes tenant media blob keys on org switch / logout clear", async () => {
    const queryClient = new QueryClient();
    const revoke = vi.fn();
    // jsdom may not define URL.revokeObjectURL — install a stub for this test.
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revoke,
    });
    const mediaKey = queryKeys.media("tenant-a", "/api/v1/tenants/tenant-a/images/x/thumbnail");
    queryClient.setQueryData(mediaKey, "blob:http://localhost/fake-a");
    queryClient.setQueryData(
      queryKeys.media("tenant-b", "/api/v1/tenants/tenant-b/images/y/thumbnail"),
      "blob:http://localhost/fake-b",
    );
    queryClient.setQueryData(queryKeys.me(), { user: { id: "u1" }, organizations: [] });

    await clearTenantSensitiveCache(queryClient);

    expect(queryClient.getQueryData(mediaKey)).toBeUndefined();
    expect(
      queryClient.getQueryData(
        queryKeys.media("tenant-b", "/api/v1/tenants/tenant-b/images/y/thumbnail"),
      ),
    ).toBeUndefined();
    expect(revoke).toHaveBeenCalled();
    expect(queryClient.getQueryData(queryKeys.me())).toBeTruthy();
  });
});
