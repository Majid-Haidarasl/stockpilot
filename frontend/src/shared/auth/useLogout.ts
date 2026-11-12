import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { logoutRequest } from "../api/client";
import { mapApiError } from "../api/mapApiError";
import { clearTenantSensitiveCache } from "../query/cache";
import { clearTenant } from "../tenant";

export function useLogout() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      await clearTenantSensitiveCache(queryClient);
      clearTenant();
      const result = await logoutRequest();
      if (result.keycloak_logout_url) {
        window.location.href = result.keycloak_logout_url;
        return;
      }
      window.location.href = "/";
    } catch (err) {
      setError(mapApiError(err));
      setPending(false);
    }
  }, [queryClient]);

  return { logout, pending, error };
}
