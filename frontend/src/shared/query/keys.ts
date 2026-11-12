/** TanStack Query key factories — every tenant-scoped key includes tenant_id. */

export const queryKeys = {
  me: () => ["me"] as const,
  products: (tenantId: string) => ["tenant", tenantId, "products"] as const,
  customers: (tenantId: string) => ["tenant", tenantId, "customers"] as const,
  inventory: (tenantId: string) => ["tenant", tenantId, "inventory"] as const,
  inventoryMovements: (tenantId: string) =>
    ["tenant", tenantId, "inventory", "movements"] as const,
};

export function assertTenantInKey(key: readonly unknown[], tenantId: string): boolean {
  return key.includes(tenantId);
}
