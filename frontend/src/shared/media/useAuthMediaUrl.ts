import { useQuery } from "@tanstack/react-query";
import { apiFetchBlob } from "../api/client";
import { queryKeys } from "../query/keys";

/**
 * Load an authenticated media path into a cached blob: object URL.
 * Keyed under ["tenant", tenantId, "media", path] so org switch clears it.
 */
export function useAuthMediaUrl(
  tenantId: string,
  path: string | null | undefined,
): { url: string | null; isError: boolean; isPending: boolean } {
  const enabled = Boolean(tenantId && path);
  const query = useQuery({
    queryKey: queryKeys.media(tenantId, path ?? ""),
    queryFn: async ({ signal }) => {
      const blob = await apiFetchBlob(path!, { signal });
      return URL.createObjectURL(blob);
    },
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 5 * 60_000,
  });

  if (!enabled) {
    return { url: null, isError: false, isPending: false };
  }
  return {
    url: query.data ?? null,
    isError: query.isError,
    isPending: query.isPending,
  };
}
