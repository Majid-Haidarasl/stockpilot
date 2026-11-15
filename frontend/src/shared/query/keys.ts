/** TanStack Query key factories — every tenant-scoped key includes tenant_id. */

export const queryKeys = {
  me: () => ["me"] as const,
  products: (tenantId: string) => ["tenant", tenantId, "products"] as const,
  customers: (tenantId: string) => ["tenant", tenantId, "customers"] as const,
  inventory: (tenantId: string) => ["tenant", tenantId, "inventory"] as const,
  inventoryMovements: (tenantId: string) =>
    ["tenant", tenantId, "inventory", "movements"] as const,
  orders: (tenantId: string, status?: string | null) =>
    ["tenant", tenantId, "orders", status ?? "all"] as const,
  /** Dashboard recent-orders strip — separate from full orders list cache. */
  recentOrders: (tenantId: string, limit: number) =>
    ["tenant", tenantId, "orders", "recent", limit] as const,
  order: (tenantId: string, orderId: string) =>
    ["tenant", tenantId, "orders", "detail", orderId] as const,
  orderTimeline: (tenantId: string, orderId: string) =>
    ["tenant", tenantId, "orders", "timeline", orderId] as const,
  dashboard: (tenantId: string, from: string, to: string) =>
    ["tenant", tenantId, "dashboard", from, to] as const,
  members: (tenantId: string) => ["tenant", tenantId, "members"] as const,
  productImages: (tenantId: string, productId: string) =>
    ["tenant", tenantId, "products", productId, "images"] as const,
  /** Authenticated media blob object URLs (thumbnail/file paths). */
  media: (tenantId: string, path: string) =>
    ["tenant", tenantId, "media", path] as const,
};

export function assertTenantInKey(key: readonly unknown[], tenantId: string): boolean {
  return key.includes(tenantId);
}
