import type { QueryClient } from "@tanstack/react-query";

/**
 * Cancel in-flight fetches first, then clear the cache.
 * Prevents a late response from an old org from filling the new org's cache.
 */
export async function clearTenantSensitiveCache(queryClient: QueryClient): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
}
