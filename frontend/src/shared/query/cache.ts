import type { QueryClient, Query } from "@tanstack/react-query";
import { revokeTenantMediaObjectUrls } from "./mediaCache";

function isTenantScopedQuery(query: Query): boolean {
  return query.queryKey[0] === "tenant";
}

/**
 * Cancel in-flight tenant fetches first, then drop tenant-scoped cache.
 * Leaves `me` (and other non-tenant keys) intact so OrgPicker can load orgs.
 * Prevents a late response from an old org from filling the new org's cache.
 * Revokes authenticated media blob URLs before removal (no cross-tenant leak).
 */
export async function clearTenantSensitiveCache(queryClient: QueryClient): Promise<void> {
  await queryClient.cancelQueries({ predicate: isTenantScopedQuery });
  revokeTenantMediaObjectUrls(queryClient);
  queryClient.removeQueries({ predicate: isTenantScopedQuery });
}
