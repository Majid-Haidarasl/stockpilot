import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { clearTenantSensitiveCache } from "./cache";
import { clearTenant } from "../tenant";

/** Org picker mount: cancel in-flight queries, clear cache, drop selected tenant. */
export function useClearTenantCacheOnOrgSwitch(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    void clearTenantSensitiveCache(queryClient);
    clearTenant();
  }, [queryClient]);
}
