import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  apiFetch,
  isApiProblemError,
  mapApiError,
  type Order,
} from "../../shared/api";
import { createIdempotentAction } from "../../shared/mutations/idempotentAction";
import { queryKeys } from "../../shared/query/keys";

export type CycleActionName = "reserve" | "confirm" | "cancel" | "ship";

type Options = {
  tenantId: string;
  orderId: string;
  titleBySku?: Record<string, string>;
};

/**
 * Cycle mutations without optimistic updates.
 * Retries reuse the same Idempotency-Key; VERSION_CONFLICT / RESERVATION_EXPIRED
 * reload the order and do not auto-resubmit.
 */
export function useOrderCycleAction({ tenantId, orderId, titleBySku }: Options) {
  const queryClient = useQueryClient();
  const controllers = useRef(
    new Map<CycleActionName, ReturnType<typeof createIdempotentAction>>(),
  );
  const [pendingAction, setPendingAction] = useState<CycleActionName | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastConflictCode, setLastConflictCode] = useState<string | null>(null);

  function controllerFor(action: CycleActionName) {
    let ctrl = controllers.current.get(action);
    if (!ctrl) {
      ctrl = createIdempotentAction(`orders.${action}:${orderId}`);
      controllers.current.set(action, ctrl);
    }
    return ctrl;
  }

  async function invalidateOrderQueries() {
    await queryClient.invalidateQueries({ queryKey: queryKeys.order(tenantId, orderId) });
    await queryClient.invalidateQueries({
      queryKey: queryKeys.orderTimeline(tenantId, orderId),
    });
    await queryClient.invalidateQueries({
      queryKey: ["tenant", tenantId, "orders"],
    });
  }

  async function reloadOrder(): Promise<Order | undefined> {
    await invalidateOrderQueries();
    return queryClient.fetchQuery({
      queryKey: queryKeys.order(tenantId, orderId),
      queryFn: () =>
        apiFetch<Order>(`/api/v1/tenants/${tenantId}/orders/${orderId}`),
    });
  }

  async function run(
    action: CycleActionName,
    expectedVersion: number,
    options: { retry?: boolean } = {},
  ): Promise<Order | null> {
    const retry = options.retry ?? false;
    setErrorMessage(null);
    setLastConflictCode(null);
    const ctrl = controllerFor(action);
    if (retry) {
      ctrl.retry(expectedVersion);
    } else {
      ctrl.begin(expectedVersion);
    }
    const { headers, body } = ctrl.buildRequest();
    setPendingAction(action);
    try {
      const updated = await apiFetch<Order>(
        `/api/v1/tenants/${tenantId}/orders/${orderId}/${action}`,
        {
          method: "POST",
          headers,
          body: JSON.stringify(body),
        },
      );
      ctrl.clear();
      queryClient.setQueryData(queryKeys.order(tenantId, orderId), updated);
      await invalidateOrderQueries();
      return updated;
    } catch (err) {
      if (isApiProblemError(err)) {
        const code = err.problem.code;
        setLastConflictCode(code);
        setErrorMessage(mapApiError(err, { titleBySku }));
        if (code === "VERSION_CONFLICT" || code === "RESERVATION_EXPIRED") {
          // Reload fresh order; do not auto-resubmit.
          ctrl.clear();
          await reloadOrder();
          return null;
        }
      } else {
        setErrorMessage(mapApiError(err, { titleBySku }));
      }
      return null;
    } finally {
      setPendingAction(null);
    }
  }

  return {
    pendingAction,
    errorMessage,
    lastConflictCode,
    clearError: () => {
      setErrorMessage(null);
      setLastConflictCode(null);
    },
    run,
    /** Explicit user retry of the same action (same Idempotency-Key). */
    retry: (action: CycleActionName, expectedVersion: number) =>
      run(action, expectedVersion, { retry: true }),
  };
}
