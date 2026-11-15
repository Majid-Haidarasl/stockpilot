import { useQuery } from "@tanstack/react-query";
import { apiFetch, type InventoryItem } from "../api";
import { queryKeys } from "./keys";

export type StockAvailability = {
  available: number;
  on_hand: number;
  has_position: boolean;
};

/**
 * Tenant-scoped inventory map for stock chips.
 * On 403/error: query fails → callers treat as "no stock data" and hide chips
 * without blocking the page.
 */
export function useInventoryStockMap(tenantId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.inventory(tenantId),
    queryFn: () => apiFetch<InventoryItem[]>(`/api/v1/tenants/${tenantId}/inventory`),
    enabled: Boolean(tenantId) && enabled,
    retry: false,
  });
}

export function inventoryToStockMap(
  items: InventoryItem[] | undefined,
): Map<string, StockAvailability> {
  const map = new Map<string, StockAvailability>();
  for (const item of items ?? []) {
    map.set(item.product_id, {
      available: item.available,
      on_hand: item.on_hand,
      has_position: item.has_position !== false,
    });
  }
  return map;
}

export function isOutOfStock(stock: StockAvailability | undefined): boolean {
  if (!stock) return false;
  return stock.available <= 0;
}
