import type { Query, QueryClient } from "@tanstack/react-query";

function isMediaQuery(query: Query): boolean {
  const key = query.queryKey;
  return key[0] === "tenant" && key[2] === "media";
}

function revokeIfBlob(data: unknown): void {
  if (typeof data === "string" && data.startsWith("blob:")) {
    URL.revokeObjectURL(data);
  }
}

/** Revoke blob: object URLs for tenant media queries (call before removeQueries). */
export function revokeTenantMediaObjectUrls(queryClient: QueryClient): void {
  for (const query of queryClient.getQueryCache().getAll()) {
    if (isMediaQuery(query)) {
      revokeIfBlob(query.state.data);
    }
  }
}

/**
 * When a media query is GC'd or removed, revoke its object URL so blobs do not leak.
 * Safe to call once per QueryClient lifetime.
 */
export function setupMediaUrlRevocation(queryClient: QueryClient): () => void {
  return queryClient.getQueryCache().subscribe((event) => {
    if (event?.type === "removed" && isMediaQuery(event.query)) {
      revokeIfBlob(event.query.state.data);
    }
  });
}
